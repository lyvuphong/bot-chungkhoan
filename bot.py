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

# --- 2. HÀM XỬ LÝ DỮ LIỆU (CÓ CACHING ĐỂ CHỐNG RATE LIMIT) ---

@st.cache_data(ttl=600, show_spinner=False) # Lưu bộ nhớ đệm 10 phút
def fetch_stock_data_cached(symbol):
    """Hàm tải dữ liệu có bộ nhớ đệm để tránh gọi Yahoo quá nhiều"""
    try:
        if not symbol.endswith(".VN"): symbol += ".VN"
        ticker = yf.Ticker(symbol)
        
        # 1. Lấy lịch sử giá (History)
        # Thử 3 lần nếu bị lỗi mạng
        df = pd.DataFrame()
        for attempt in range(3):
            try:
                df = ticker.history(period="2y")
                if not df.empty: break
                time.sleep(1) # Nghỉ 1s nếu lỗi
            except:
                time.sleep(1)
        
        if df.empty: return None, None, "Không lấy được dữ liệu giá."

        # 2. Lấy thông tin cơ bản (Info)
        # Info hay bị Rate Limit nhất, nên tách riêng và try-catch kỹ
        info = {}
        try:
            info = ticker.info
        except:
            pass # Nếu lỗi Info, vẫn trả về Giá để phân tích kỹ thuật

        return df, info, None
    except Exception as e:
        return None, None, str(e)

def analyze_single_stock(symbol):
    """Phân tích chi tiết 1 mã từ dữ liệu đã Cache"""
    # Gọi hàm Cache ở trên
    df_raw, info, err = fetch_stock_data_cached(symbol)
    
    if err: return None, err
    
    try:
        df = df_raw.copy() # Copy để không ảnh hưởng Cache
        
        # Tính chỉ báo
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['SMA_200'] = ta.sma(df['Close'], length=200)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        macd = ta.macd(df['Close'])
        df['MACD'] = macd['MACD_12_26_9']
        df['MACD_Signal'] = macd['MACDs_12_26_9']
        df['MACD_Hist'] = macd['MACDh_12_26_9']

        latest = df.iloc[-1]
        
        # Chấm điểm Kỹ thuật
        tech_score = 0
        tech_reasons = []
        
        if latest['Close'] > latest['SMA_20']: tech_score += 10; tech_reasons.append("Giá > MA20 (Ngắn hạn Tăng)")
        if latest['SMA_20'] > latest['SMA_50']: tech_score += 15; tech_reasons.append("MA20 > MA50 (Trung hạn Tăng)")
        if latest['Close'] > latest['SMA_200']: tech_score += 10; tech_reasons.append("Trên MA200 (Dài hạn Tăng)")
        if 50 <= latest['RSI'] <= 70: tech_score += 5; tech_reasons.append("RSI vùng mua mạnh")
        if latest['MACD'] > latest['MACD_Signal']: tech_score += 10; tech_reasons.append("MACD cắt lên Signal")
        
        # Chấm điểm Cơ bản
        fund_score = 0
        fund_reasons = []
        metrics = {}
        
        if info:
            metrics = {
                "P/E": info.get('trailingPE', 0),
                "P/B": info.get('priceToBook', 0),
                "ROE": info.get('returnOnEquity', 0),
                "Div Yield": info.get('dividendYield', 0),
                "Sector": info.get('sector', "N/A")
            }
            
            pe = metrics['P/E']
            roe = metrics['ROE']
            div = metrics['Div Yield']
            
            if pe and 5 < pe < 20: fund_score += 15; fund_reasons.append("P/E hấp dẫn (5-20)")
            if roe and roe > 0.15: fund_score += 20; fund_reasons.append(f"ROE xuất sắc ({round(roe*100,1)}%)")
            if div and div > 0.03: fund_score += 15; fund_reasons.append(f"Cổ tức tốt ({round(div*100,1)}%)")
        
        total_score = tech_score + fund_score
        
        # Plan
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
        return None, f"Lỗi xử lý: {str(e)}"

# --- 3. VẼ BIỂU ĐỒ ---
def plot_detailed_chart(data):
    df = data['DF']
    fig = make_subplots(rows=3, cols=1, shared_xaxes=True, row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.03)

    # Chart 1
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    if 'SMA_50' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)
    
    # Plan
    fig.add_hline(y=data['Entry'], line_dash="dot", line_color="gray", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="green", row=1, col=1)

    # Chart 2
    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    # Chart 3
    if 'MACD' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD'], line=dict(color='#2962ff'), name='MACD'), row=3, col=1)
        fig.add_trace(go.Scatter(x=df.index, y=df['MACD_Signal'], line=dict(color='#ff6d00'), name='Signal'), row=3, col=1)
        fig.add_trace(go.Bar(x=df.index, y=df['MACD_Hist'], marker_color='gray', name='Hist'), row=3, col=1)

    fig.update_layout(height=800, xaxis_rangeslider_visible=False, template="plotly_white", title=f"Biểu đồ kỹ thuật: {data['Symbol']}")
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🤖 AI STOCK ANALYST PRO (CACHED)")

tab1, tab2 = st.tabs(["🔍 TRA CỨU & ĐÁNH GIÁ", "⚡ BỘ LỌC THỊ TRƯỜNG"])

# ================= TAB 1: TRA CỨU =================
with tab1:
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        symbol_input = st.text_input("Nhập mã cổ phiếu (Ví dụ: MPC, VCB):", "").upper()
    with col_btn:
        st.write("") 
        st.write("") 
        btn_check = st.button("🔎 PHÂN TÍCH", type="primary", use_container_width=True)

    if btn_check and symbol_input:
        # Xóa cache cũ nếu muốn làm mới (Optional)
        # st.cache_data.clear() 
        
        with st.spinner(f"Đang tải dữ liệu {symbol_input} (Có Cache)..."):
            data, err = analyze_single_stock(symbol_input)
            
            if err:
                st.error(f"⚠️ {err}. Hãy thử lại sau 30s hoặc nhập mã khác.")
            elif data:
                # HIỂN THỊ KẾT QUẢ
                st.markdown(f"### 📊 Báo Cáo Thẩm Định: {data['Symbol']}")
                score = data['Total_Score']
                color = "green" if score >= 75 else "orange" if score >= 50 else "red"
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá", f"{int(data['Price']):,} đ")
                c1.metric("Tổng Điểm", f"{score}/100")
                c2.metric("Kỹ Thuật", f"{data['Tech_Score']}/50")
                c3.metric("Cơ Bản", f"{data['Fund_Score']}/50")
                rating = "MUA MẠNH" if score >= 80 else "MUA" if score >= 60 else "THEO DÕI"
                c4.markdown(f"<h3 style='color:{color}; text-align:center'>{rating}</h3>", unsafe_allow_html=True)
                
                st.markdown("---")
                col_tech, col_fund = st.columns(2)
                
                with col_tech:
                    st.subheader("📈 Kỹ Thuật & Plan")
                    for r in data['Tech_Reasons']: st.success(f"✅ {r}")
                    st.info(f"**ENTRY:** {int(data['Entry']):,} | **SL:** {int(data['SL']):,} | **TP:** {int(data['TP']):,}")

                with col_fund:
                    st.subheader("🏢 Tài Chính")
                    m = data['Metrics']
                    if m:
                        c_f1, c_f2 = st.columns(2)
                        c_f1.metric("P/E", round(m.get('P/E',0), 2) if m.get('P/E') else "-")
                        c_f2.metric("P/B", round(m.get('P/B',0), 2) if m.get('P/B') else "-")
                        c_f1.metric("ROE", f"{round(m.get('ROE',0)*100, 1)}%" if m.get('ROE') else "-")
                        c_f2.metric("Div Yield", f"{round(m.get('Div Yield',0)*100, 1)}%" if m.get('Div Yield') else "-")
                        st.caption(f"Ngành: {m.get('Sector','-')}")
                        for r in data['Fund_Reasons']: st.success(f"💎 {r}")
                    else:
                        st.warning("Dữ liệu tài chính tạm thời không khả dụng (Rate Limit).")

                st.markdown("---")
                plot_detailed_chart(data)

# ================= TAB 2: BỘ LỌC =================
with tab2:
    def get_stock_universe(sector_choice):
        banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB"]
        securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "VIX"]
        real_estate = ["VHM", "VIC", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "KBC", "IDC"]
        steel = ["HPG", "HSG", "NKG"]
        seafood = ["VHC", "ANV", "MPC", "IDI", "CMX"]
        vn30 = ["MWG", "FPT", "PNJ", "MSN", "GAS", "VNM", "REE", "GMD"]
        
        selected = []
        if "QUÉT TOÀN BỘ" in str(sector_choice):
            selected = list(set(banks + securities + real_estate + steel + seafood + vn30))
        else:
            if "Ngân hàng" in str(sector_choice): selected += banks
            if "Chứng khoán" in str(sector_choice): selected += securities
            if "Bất động sản" in str(sector_choice): selected += real_estate
            if "Thép" in str(sector_choice): selected += steel
            if "Thủy sản" in str(sector_choice): selected += seafood
            if "VN30" in str(sector_choice): selected += vn30
        return [f"{s}.VN" for s in list(set(selected))]

    def analyze_scan(symbol):
        # Dùng lại hàm cached để quét nhanh
        df, info, err = fetch_stock_data_cached(symbol)
        if err or df is None: return None
        
        try:
            latest = df.iloc[-1]
            # Tính nhanh không cần chỉ báo phức tạp để nhẹ máy
            sma20 = df['Close'].rolling(20).mean().iloc[-1]
            score = 0
            if latest['Close'] > sma20: score += 50
            if latest['Volume'] > df['Volume'].tail(20).mean(): score += 30
            
            pe = 0
            if info: pe = info.get('trailingPE', 0)

            return {
                "Mã": symbol.replace(".VN",""), 
                "Giá": latest['Close'], 
                "Điểm": score, 
                "P/E": round(pe,1) if pe else 0
            }
        except: return None

    c1, c2 = st.columns([3, 1])
    with c1:
        sectors = st.multiselect("Ngành:", ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"], default=["QUÉT TOÀN BỘ"])
    with c2:
        min_s = st.slider("Điểm min:", 0, 100, 40)
        btn_scan = st.button("🚀 CHẠY BỘ LỌC")

    if btn_scan:
        symbols = get_stock_universe(sectors)
        bar = st.progress(0)
        res = []
        for i, s in enumerate(symbols):
            d = analyze_scan(s)
            if d and d['Điểm'] >= min_s: res.append(d)
            bar.progress((i+1)/len(symbols))
            
        if res:
            df_s = pd.DataFrame(res).sort_values(by="Điểm", ascending=False)
            st.dataframe(df_s, use_container_width=True)
        else:
            st.warning("Không tìm thấy mã nào.")
