import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="AI Stock Sniper Pro",
    layout="wide",
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    div[data-testid="stMetric"] {
        background-color: white; border: 1px solid #ddd; padding: 10px; border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: white; border-radius: 5px; padding: 10px 20px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #e3f2fd; color: #1976d2; border: 1px solid #1976d2;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM XỬ LÝ DỮ LIỆU (CACHED) ---

@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_data_cached(symbol):
    try:
        if not symbol.endswith(".VN"): symbol += ".VN"
        ticker = yf.Ticker(symbol)
        
        df = pd.DataFrame()
        # Thử lại 3 lần nếu mạng lỗi
        for _ in range(3):
            try:
                df = ticker.history(period="1y") # Lấy 1 năm để tính chỉ báo
                if not df.empty: break
                time.sleep(1)
            except: time.sleep(1)
        
        if df.empty: return None, None, "Không có dữ liệu giá"

        # Lấy Info (Thử 1 lần, lỗi thì bỏ qua)
        info = {}
        try: info = ticker.info
        except: pass

        return df, info, None
    except Exception as e:
        return None, None, str(e)

def calculate_trade_plan(df, current_price):
    """Tính toán Điểm Mua, Cắt Lỗ, Chốt Lời"""
    # 1. Tìm hỗ trợ gần nhất (Đáy 20 phiên)
    support_level = df['Low'].tail(20).min()
    
    # 2. Tính rủi ro
    risk_pct = (current_price - support_level) / current_price
    
    # 3. Logic Stoploss: Nếu hỗ trợ xa hơn 7%, siết SL về 7%
    if risk_pct > 0.07:
        stop_loss = current_price * 0.93
    else:
        stop_loss = support_level
        
    # 4. Logic Take Profit: Tỷ lệ R:R = 1:2 (Lãi gấp đôi Lỗ)
    risk_amt = current_price - stop_loss
    if risk_amt <= 0: risk_amt = current_price * 0.05 # Fallback nếu lỗi
    take_profit = current_price + (risk_amt * 2)
    
    return int(stop_loss), int(take_profit)

def analyze_single_stock(symbol):
    df_raw, info, err = fetch_stock_data_cached(symbol)
    if err: return None, err
    
    try:
        df = df_raw.copy()
        
        # Chỉ báo
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        latest = df.iloc[-1]
        
        # Chấm điểm
        score = 0
        reasons = []
        
        if latest['Close'] > latest['SMA_20']: score += 20; reasons.append("Giá trên MA20")
        if latest['SMA_20'] > latest['SMA_50']: score += 20; reasons.append("Trend Tăng (MA20>MA50)")
        if 50 <= latest['RSI'] <= 70: score += 10; reasons.append("RSI Sức mạnh")
        if latest['Volume'] > df['Volume'].tail(20).mean(): score += 20; reasons.append("Tiền vào")
        
        # Cơ bản
        pe = info.get('trailingPE', 0) if info else 0
        if pe and 5 < pe < 20: score += 15; reasons.append("Định giá P/E tốt")
        
        # Trade Plan
        sl, tp = calculate_trade_plan(df, latest['Close'])
        
        # Khuyến nghị
        recommendation = "THEO DÕI"
        if score >= 80: recommendation = "MUA MẠNH"
        elif score >= 60: recommendation = "MUA"
        elif score < 40: recommendation = "BÁN"

        return {
            "Symbol": symbol.replace(".VN", ""),
            "Price": latest['Close'],
            "Score": score,
            "Rec": recommendation,
            "SL": sl,
            "TP": tp,
            "PE": round(pe, 1) if pe else 0,
            "Reasons": ", ".join(reasons),
            "DF": df
        }, None
    except Exception as e:
        return None, str(e)

# --- 3. VẼ BIỂU ĐỒ PLAN ---
def plot_trade_chart(data):
    df = data['DF']
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)

    # Nến
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    
    # CÁC ĐƯỜNG KẺ PLAN (Quan trọng)
    fig.add_hline(y=data['Price'], line_dash="dot", line_color="gray", annotation_text="ENTRY", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", annotation_text=f"STOP: {data['SL']:,}", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="#00CC96", annotation_text=f"TARGET: {data['TP']:,}", row=1, col=1)

    # Volume
    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_white", title=f"Kế hoạch giao dịch: {data['Symbol']}")
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🎯 AI STOCK SNIPER PRO")

tab1, tab2 = st.tabs(["🔍 TRA CỨU & PLAN", "⚡ BỘ LỌC THỊ TRƯỜNG"])

# ================= TAB 1: TRA CỨU =================
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        symbol_input = st.text_input("Nhập mã (VD: SSI, FPT):", "").upper()
    with col2:
        st.write("")
        st.write("")
        btn_analyze = st.button("LẬP KẾ HOẠCH", type="primary", use_container_width=True)

    if btn_analyze and symbol_input:
        with st.spinner("AI đang tính toán điểm vào lệnh..."):
            data, err = analyze_single_stock(symbol_input)
            if data:
                # 1. SCORE CARD
                score = data['Score']
                color = "green" if score >= 80 else "orange" if score >= 60 else "red"
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá Hiện Tại", f"{int(data['Price']):,} đ")
                c2.metric("Điểm Sức Mạnh", f"{score}/100")
                c3.metric("P/E", data['PE'])
                c4.markdown(f"<div style='text-align:center; color:{color}; font-weight:bold; font-size:20px; padding:10px; border:1px solid {color}; border-radius:5px'>{data['Rec']}</div>", unsafe_allow_html=True)
                
                # 2. TRADE PLAN (Điểm Mua/Bán)
                st.markdown("---")
                st.subheader("📋 KẾ HOẠCH GIAO DỊCH (Risk/Reward 1:2)")
                
                col_plan1, col_plan2, col_plan3 = st.columns(3)
                col_plan1.success(f"🎯 **CHỐT LỜI (Target):**\n# {data['TP']:,} đ")
                col_plan2.info(f"🔵 **ĐIỂM MUA (Entry):**\n# {int(data['Price']):,} đ")
                col_plan3.error(f"🛑 **CẮT LỖ (Stoploss):**\n# {data['SL']:,} đ")
                
                st.caption(f"💡 Lý do khuyến nghị: {data['Reasons']}")
                
                # 3. CHART
                plot_trade_chart(data)
            elif err:
                st.error(f"Lỗi: {err}")

# ================= TAB 2: BỘ LỌC =================
with tab2:
    def get_symbols(sector):
        # Danh sách rút gọn demo
        vn30 = ["FPT", "MWG", "HPG", "VCB", "TCB", "VPB", "MBB", "ACB", "STB", "MSN", "GAS", "VNM", "VIC", "VHM", "VRE", "SSI", "POW", "PLX", "SAB", "GVR"]
        mid = ["DGC", "VHC", "ANV", "FRT", "DGW", "PC1", "GEG", "HDG", "PVS", "PVD", "KBC", "IDC", "SZC", "DIG", "CEO", "DXG", "NKG", "HSG", "HHV", "LCG"]
        return [f"{s}.VN" for s in (vn30 + mid)]

    def scan_market(symbols, min_score):
        res = []
        bar = st.progress(0)
        for i, s in enumerate(symbols):
            # Dùng lại hàm phân tích ở trên
            d, e = analyze_single_stock(s)
            if d and d['Score'] >= min_score:
                res.append(d)
            bar.progress((i+1)/len(symbols))
        return res

    c1, c2 = st.columns([3,1])
    with c1:
        st.info("Quét nhanh 40 mã hot nhất (VN30 + Midcap)")
    with c2:
        min_s = st.slider("Điểm tối thiểu:", 0, 100, 60)
        btn_scan = st.button("🚀 QUÉT TÍN HIỆU")

    if btn_scan:
        syms = get_symbols("ALL")
        results = scan_market(syms, min_s)
        
        if results:
            df_res = pd.DataFrame(results).sort_values(by="Score", ascending=False)
            
            # Hiển thị bảng có cột Khuyến nghị, SL, TP
            st.dataframe(
                df_res[['Symbol', 'Price', 'Score', 'Rec', 'SL', 'TP', 'PE']],
                use_container_width=True,
                column_config={
                    "Score": st.column_config.ProgressColumn("Điểm", max_value=100),
                    "Price": st.column_config.NumberColumn("Giá Mua", format="%d"),
                    "SL": st.column_config.NumberColumn("Cắt Lỗ", format="%d"),
                    "TP": st.column_config.NumberColumn("Chốt Lời", format="%d"),
                    "Rec": "Khuyến Nghị"
                }
            )
        else:
            st.warning("Không tìm thấy mã nào.")
