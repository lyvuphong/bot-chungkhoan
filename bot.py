import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Pro AI Stock Terminal",
    layout="wide",
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: white; border-radius: 5px; padding: 10px 20px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #e3f2fd; color: #1976d2; border: 1px solid #1976d2;
    }
    div[data-testid="stMetric"] {
        background-color: white; border: 1px solid #ddd; padding: 15px; border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM XỬ LÝ DỮ LIỆU ---

def get_financial_metrics(ticker):
    """Lấy chỉ số tài chính cơ bản"""
    try:
        info = ticker.info
        metrics = {
            "P/E": info.get('trailingPE', 0),
            "Forward P/E": info.get('forwardPE', 0),
            "EPS": info.get('trailingEps', 0),
            "P/B": info.get('priceToBook', 0),
            "ROE": info.get('returnOnEquity', 0),
            "ROA": info.get('returnOnAssets', 0),
            "Div Yield": info.get('dividendYield', 0),
            "Market Cap": info.get('marketCap', 0),
            "Sector": info.get('sector', "N/A")
        }
        return metrics
    except:
        return None

def analyze_single_stock(symbol):
    """Phân tích chi tiết 1 mã"""
    try:
        if not symbol.endswith(".VN"): symbol += ".VN"
        ticker = yf.Ticker(symbol)
        
        # 1. Lấy dữ liệu giá
        df = ticker.history(period="2y") # Lấy 2 năm để vẽ chart đẹp
        if df.empty: return None, "Không tìm thấy dữ liệu giá."

        # 2. Tính chỉ báo kỹ thuật
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['SMA_200'] = ta.sma(df['Close'], length=200)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        # MACD
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        df['MACD_Hist'] = macd['MACDh_12_26_9']

        latest = df.iloc[-1]
        
        # 3. Chấm điểm Kỹ thuật (50đ)
        tech_score = 0
        tech_reasons = []
        
        # Trend
        if latest['Close'] > latest['SMA_20']: tech_score += 10; tech_reasons.append("Giá trên MA20 (Ngắn hạn Tăng)")
        if latest['SMA_20'] > latest['SMA_50']: tech_score += 15; tech_reasons.append("MA20 > MA50 (Trung hạn Tăng)")
        if latest['Close'] > latest['SMA_200']: tech_score += 10; tech_reasons.append("Uptrend dài hạn (Trên MA200)")
        
        # Momentum
        if 50 <= latest['RSI'] <= 70: tech_score += 5; tech_reasons.append("RSI vùng mua mạnh")
        if latest['MACD'] > latest['MACD_Signal']: tech_score += 10; tech_reasons.append("MACD cắt lên tín hiệu")
        
        # 4. Chấm điểm Cơ bản (50đ)
        fund_score = 0
        fund_reasons = []
        metrics = get_financial_metrics(ticker)
        
        if metrics:
            pe = metrics['P/E'] if metrics['P/E'] else 0
            roe = metrics['ROE'] if metrics['ROE'] else 0
            div = metrics['Div Yield'] if metrics['Div Yield'] else 0
            
            # Định giá P/E (Giả định chung, tùy ngành sẽ khác)
            if 5 < pe < 20: fund_score += 15; fund_reasons.append("P/E hấp dẫn (5-20)")
            elif pe > 0 and pe <= 5: fund_score += 10; fund_reasons.append("P/E rất thấp")
            
            # Hiệu quả
            if roe > 0.15: fund_score += 20; fund_reasons.append(f"ROE xuất sắc ({round(roe*100,1)}%)")
            elif roe > 0.10: fund_score += 10; fund_reasons.append("ROE ổn định")
            
            # Cổ tức
            if div > 0.03: fund_score += 15; fund_reasons.append(f"Cổ tức tốt ({round(div*100,1)}%)")

        total_score = tech_score + fund_score
        
        # 5. Plan
        entry = latest['Close']
        support = df['Low'].tail(20).min()
        stop_loss = support if (entry - support)/entry < 0.08 else entry * 0.93
        take_profit = entry + (entry - stop_loss) * 2

        return {
            "Symbol": symbol.replace(".VN", ""),
            "Price": latest['Close'],
            "Tech_Score": tech_score,
            "Fund_Score": fund_score,
            "Total_Score": total_score,
            "Tech_Reasons": tech_reasons,
            "Fund_Reasons": fund_reasons,
            "Metrics": metrics,
            "Entry": entry,
            "SL": stop_loss,
            "TP": take_profit,
            "DF": df
        }, None

    except Exception as e:
        return None, str(e)

# --- 3. VẼ BIỂU ĐỒ NÂNG CAO ---
def plot_detailed_chart(data):
    df = data['DF']
    
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, 
                        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # Chart 1: Giá + MA + Plan
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='black', width=1), name='MA200'), row=1, col=1)
    
    # Plan Lines
    fig.add_hline(y=data['Entry'], line_dash="dot", line_color="gray", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="green", row=1, col=1)

    # Chart 2: Volume
    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    # Chart 3: MACD
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2962ff'), name='MACD'), row=3, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#ff6d00'), name='Signal'), row=3, col=1)
    fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color='gray', name='Hist'), row=3, col=1)

    fig.update_layout(height=800, xaxis_rangeslider_visible=False, template="plotly_white", title=f"Biểu đồ kỹ thuật: {data['Symbol']}")
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🤖 AI STOCK ANALYST PRO")

# TẠO 2 TAB
tab1, tab2 = st.tabs(["🔍 TRA CỨU & ĐÁNH GIÁ", "⚡ BỘ LỌC THỊ TRƯỜNG"])

# ================= TAB 1: TRA CỨU MÃ RIÊNG LẺ =================
with tab1:
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        symbol_input = st.text_input("Nhập mã cổ phiếu (Ví dụ: FPT, VCB, HPG):", "").upper()
    with col_btn:
        st.write("") # Spacer
        st.write("") 
        btn_check = st.button("🔎 PHÂN TÍCH NGAY", type="primary", use_container_width=True)

    if btn_check and symbol_input:
        with st.spinner(f"Đang thẩm định toàn diện mã {symbol_input}..."):
            data, err = analyze_single_stock(symbol_input)
            
            if err:
                st.error(f"Lỗi: {err}")
            elif data:
                # --- PHẦN 1: SCORECARD ---
                st.markdown(f"### 📊 Báo Cáo Thẩm Định: {data['Symbol']}")
                
                # Hiển thị điểm số dạng Gauge (Cần tính % để chọn màu)
                score = data['Total_Score']
                score_color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Hiện Tại", f"{int(data['Price']):,} đ")
                c1.metric("Tổng Điểm AI", f"{score}/100")
                
                c2.metric("Điểm Kỹ Thuật", f"{data['Tech_Score']}/50")
                c3.metric("Điểm Cơ Bản", f"{data['Fund_Score']}/50")
                
                rating = "MUA MẠNH" if score >= 80 else "MUA" if score >= 60 else "THEO DÕI"
                c4.markdown(f"<h3 style='color:{score_color}; text-align:center'>{rating}</h3>", unsafe_allow_html=True)
                
                st.markdown("---")

                # --- PHẦN 2: CHI TIẾT ---
                col_tech, col_fund = st.columns(2)
                
                with col_tech:
                    st.subheader("📈 Phân Tích Kỹ Thuật")
                    for r in data['Tech_Reasons']:
                        st.success(f"✅ {r}")
                    if data['Tech_Score'] < 25:
                        st.warning("⚠️ Xu hướng kỹ thuật đang yếu")
                    
                    st.info(f"**PLAN:**\n- Mua: {int(data['Entry']):,}\n- SL: {int(data['SL']):,}\n- TP: {int(data['TP']):,}")

                with col_fund:
                    st.subheader("🏢 Sức Khỏe Tài Chính")
                    m = data['Metrics']
                    if m:
                        c_f1, c_f2 = st.columns(2)
                        c_f1.metric("P/E", round(m['P/E'], 2) if m['P/E'] else "-")
                        c_f2.metric("P/B", round(m['P/B'], 2) if m['P/B'] else "-")
                        c_f1.metric("ROE", f"{round(m['ROE']*100, 1)}%" if m['ROE'] else "-")
                        c_f2.metric("Cổ tức", f"{round(m['Div Yield']*100, 1)}%" if m['Div Yield'] else "-")
                        
                        st.caption(f"Ngành: {m['Sector']}")
                        for r in data['Fund_Reasons']:
                            st.success(f"💎 {r}")
                    else:
                        st.warning("Không lấy được dữ liệu tài chính.")

                # --- PHẦN 3: CHART ---
                st.markdown("---")
                plot_detailed_chart(data)

# ================= TAB 2: BỘ LỌC (GIỮ NGUYÊN TÍNH NĂNG CŨ) =================
with tab2:
    # (Copy lại logic bộ lọc cũ vào đây để code gọn)
    # Hàm lấy danh sách
    def get_stock_universe(sector_choice):
        banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
        securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
        real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
        steel = ["HPG", "HSG", "NKG", "VGS"]
        seafood = ["VHC", "ANV", "FMC", "MPC", "IDI", "CMX"]
        vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]
        midcap = ["DGC", "CSV", "DPM", "DCM", "DGW", "FRT", "PET", "PC1", "GEG", "HAH", "VOS", "PVT", "TNG", "GIL", "PVS", "PVD", "DBC", "HAG", "PAN"]
        
        selected = []
        if "QUÉT TOÀN BỘ" in str(sector_choice):
            selected = list(set(banks + securities + real_estate + steel + seafood + vn30_other + midcap))
        else:
            if "Ngân hàng" in str(sector_choice): selected += banks
            if "Chứng khoán" in str(sector_choice): selected += securities
            if "Bất động sản" in str(sector_choice): selected += real_estate
            if "Thép" in str(sector_choice): selected += steel
            if "Thủy sản" in str(sector_choice): selected += seafood
            if "VN30" in str(sector_choice): selected += vn30_other
        return [f"{s}.VN" for s in list(set(selected))]

    # Hàm phân tích nhanh cho bộ lọc
    def analyze_scan(symbol):
        try:
            ticker = yf.Ticker(symbol)
            df = ticker.history(period="6mo")
            if len(df) < 50: return None
            
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            latest = df.iloc[-1]
            
            score = 0
            if latest['Close'] > latest['SMA_20']: score += 20
            if latest['SMA_20'] > latest['SMA_50']: score += 20
            if latest['Volume'] > df['Volume'].tail(20).mean(): score += 20
            
            # Tính nhanh Plan
            entry = latest['Close']
            sl = df['Low'].tail(20).min()
            tp = entry + (entry - sl)*2
            
            if score >= 40:
                try:
                    info = ticker.info
                    pe = info.get('trailingPE', 0)
                except: pe = 0
            else: pe = 0

            return {
                "Mã": symbol.replace(".VN",""), "Giá": entry, "Điểm": score, 
                "P/E": round(pe,1) if pe else 0, "TP": tp, "SL": sl
            }
        except: return None

    # UI Bộ lọc
    c1, c2 = st.columns([3, 1])
    with c1:
        sectors = st.multiselect("Ngành:", ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"], default=["QUÉT TOÀN BỘ"])
    with c2:
        min_s = st.slider("Điểm min:", 0, 100, 50)
        btn_scan = st.button("🚀 CHẠY BỘ LỌC")

    if btn_scan:
        symbols = get_stock_universe(sectors)
        bar = st.progress(0)
        res = []
        for i, s in enumerate(symbols):
            time.sleep(0.05)
            d = analyze_scan(s)
            if d and d['Điểm'] >= min_s: res.append(d)
            bar.progress((i+1)/len(symbols))
            
        if res:
            df_s = pd.DataFrame(res).sort_values(by="Điểm", ascending=False)
            st.dataframe(
                df_s, use_container_width=True,
                column_config={
                    "Điểm": st.column_config.ProgressColumn("Score", max_value=100),
                    "Giá": st.column_config.NumberColumn(format="%d"),
                    "TP": st.column_config.NumberColumn(format="%d"),
                    "SL": st.column_config.NumberColumn(format="%d"),
                }
            )
        else:
            st.warning("Không tìm thấy mã nào.")
