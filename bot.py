import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH TRANG (FULL SCREEN) ---
st.set_page_config(
    page_title="Pro Stock Dashboard",
    layout="wide",
    page_icon="📊",
    initial_sidebar_state="expanded"
)

# --- 2. CSS TÙY CHỈNH (ĐỂ GIỐNG WEB HTML BẠN GỬI) ---
st.markdown("""
<style>
    /* Tổng thể */
    .main {
        background-color: #f0f2f6;
    }
    
    /* Style cho các Card (Khối thông tin) */
    div.css-1r6slb0, div.stMetric {
        background-color: white;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 0 4px 6px rgba(0,0,0,0.05);
        transition: transform 0.2s;
    }
    div.stMetric:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 8px rgba(0,0,0,0.1);
    }
    
    /* Tiêu đề */
    h1, h2, h3 {
        font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        color: #0e1117;
    }
    
    /* Nút bấm Gradient đẹp mắt */
    div.stButton > button {
        background: linear-gradient(90deg, #4b6cb7 0%, #182848 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 1rem;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    div.stButton > button:hover {
        opacity: 0.9;
        transform: scale(1.02);
    }
    
    /* Bảng dữ liệu */
    div[data-testid="stDataFrame"] {
        border: 1px solid #e0e0e0;
        border-radius: 10px;
        background: white;
        padding: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. LOGIC XỬ LÝ DỮ LIỆU (GIỮ NGUYÊN CORE MẠNH NHẤT) ---
def get_stock_universe(sector_choice):
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    steel = ["HPG", "HSG", "NKG", "VGS"]
    seafood = ["VHC", "ANV", "FMC", "MPC", "IDI", "CMX"]
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]
    midcap = ["DGC", "CSV", "DPM", "DCM", "DGW", "FRT", "PET", "PC1", "GEG", "HAH", "VOS", "PVT", "TNG", "GIL", "PVS", "PVD", "DBC", "HAG", "PAN"]

    selected_symbols = []
    if "QUÉT TOÀN BỘ" in str(sector_choice):
        selected_symbols = list(set(banks + securities + real_estate + steel + seafood + vn30_other + midcap))
    else:
        if "Ngân hàng" in str(sector_choice): selected_symbols += banks
        if "Chứng khoán" in str(sector_choice): selected_symbols += securities
        if "Bất động sản" in str(sector_choice): selected_symbols += real_estate
        if "Thép" in str(sector_choice): selected_symbols += steel
        if "Thủy sản" in str(sector_choice): selected_symbols += seafood
        if "VN30" in str(sector_choice): selected_symbols += vn30_other

    return [f"{sym}.VN" for sym in list(set(selected_symbols))]

def analyze_stock_final(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or df.empty or len(df) < 50: return None

        try:
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
        except: return None

        latest = df.iloc[-1]
        score = 0
        reasons = []

        # 1. Trend
        close = latest['Close']
        sma20 = latest.get('SMA_20', 0)
        sma50 = latest.get('SMA_50', 0)
        rsi = latest.get('RSI_14', 50)

        if close > sma20: score += 20
        if sma20 > sma50: score += 20
        if 50 <= rsi <= 70: score += 10
        
        # 2. Tích lũy
        df_last = df.tail(20)
        fluctuation = (df_last['High'].max() - df_last['Low'].min()) / df_last['Low'].min()
        if fluctuation < 0.15: 
            score += 30
            reasons.append("Nền chặt")
        elif fluctuation < 0.25:
            score += 15
            
        # 3. Dòng tiền
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol: 
            score += 20
            reasons.append("Tiền vào")

        # Plan Trade
        entry = close
        support = df['Low'].tail(20).min()
        risk_pct = (entry - support) / entry
        stop_loss = entry * 0.93 if risk_pct > 0.07 else support
        risk_amt = entry - stop_loss
        if risk_amt <= 0: risk_amt = entry * 0.05
        take_profit = entry + (risk_amt * 2)

        # Info tài chính (Lấy nhanh)
        pe, eps, roe = 0, 0, 0
        if score >= 50:
            try:
                info = ticker.info
                pe = info.get('trailingPE', 0)
                eps = info.get('trailingEps', 0)
                roe = info.get('returnOnEquity', 0)
            except: pass

        rating = "THEO DÕI"
        if score >= 70: rating = "MUA"
        if score >= 85: rating = "MUA MẠNH"

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": close,
            "Điểm": score,
            "Xếp hạng": rating,
            "Giá Mua": entry,
            "Cắt Lỗ": stop_loss,
            "Chốt Lời": take_profit,
            "P/E": round(pe, 1) if pe else 0, 
            "EPS": eps if eps else 0,
            "ROE": round(roe*100, 1) if roe else 0,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }
    except: return None

# --- 4. BIỂU ĐỒ PRO DASHBOARD ---
def plot_chart_dashboard(data):
    df = data['Dataframe']
    symbol = data['Mã']
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.03, row_heights=[0.75, 0.25])

    # Nến Nhật
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Price'), row=1, col=1)
    
    # Đường MA
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='#ff9f43', width=1.5), name='MA20'), row=1, col=1)
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='#2e86de', width=1.5), name='MA50'), row=1, col=1)

    # Vùng Plan Trade
    fig.add_hline(y=data['Giá Mua'], line_dash="dot", line_color="gray", row=1, col=1)
    fig.add_hline(y=data['Cắt Lỗ'], line_dash="dash", line_color="#ff4757", annotation_text="STOP", row=1, col=1)
    fig.add_hline(y=data['Chốt Lời'], line_dash="dash", line_color="#1dd1a1", annotation_text="TARGET", row=1, col=1)

    # Volume
    colors = ['#ff4757' if row['Open'] > row['Close'] else '#1dd1a1' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    # Tinh chỉnh giao diện Chart cho giống Web
    fig.update_layout(
        title=dict(text=f"🔥 {symbol} - Technical Analysis", font=dict(size=20)),
        margin=dict(l=10, r=10, t=40, b=10),
        height=500,
        showlegend=False,
        plot_bgcolor='white',
        paper_bgcolor='white',
        xaxis_rangeslider_visible=False
    )
    fig.update_xaxes(showgrid=True, gridcolor='#f1f2f6')
    fig.update_yaxes(showgrid=True, gridcolor='#f1f2f6')
    
    st.plotly_chart(fig, use_container_width=True)

# --- 5. LAYOUT DASHBOARD CHÍNH ---
with st.sidebar:
    st.markdown("### ⚙️ Control Panel")
    sectors = ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"]
    choice = st.multiselect("Chọn ngành:", sectors, default=["QUÉT TOÀN BỘ"])
    min_score = st.slider("Điểm lọc (Score)", 0, 100, 50)
    st.markdown("---")
    btn_scan = st.button("RUN SCANNER ⚡", type="primary", use_container_width=True)
    st.info("💡 Mẹo: Chọn 'QUÉT TOÀN BỘ' để AI tìm kiếm cơ hội tốt nhất trên thị trường.")

# Header
c1, c2 = st.columns([3, 1])
with c1:
    st.title("🚀 MARKET DASHBOARD PRO")
    st.caption("AI-Powered Stock Analysis & Trading Signals")
with c2:
    st.metric("VN-INDEX (Live)", "1,162.5", "+5.2 (0.4%)") # Ví dụ placeholder

if btn_scan:
    symbols = get_stock_universe(choice)
    st.toast("System Initializing...", icon="🔄")
    
    progress_bar = st.progress(0)
    results = []
    
    # Placeholder cho Log chạy ngầm (để giao diện sạch)
    with st.empty():
        for i, sym in enumerate(symbols):
            st.caption(f"Scanning: {sym}...")
            time.sleep(0.02) # Fast mode
            data = analyze_stock_final(sym)
            if data and data['Điểm'] >= min_score:
                results.append(data)
            progress_bar.progress((i+1)/len(symbols))
        st.write("") # Clear log text

    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        
        # --- SECTION 1: TOP 4 CARDS (GIỐNG DASHBOARD) ---
        st.markdown("### 🌟 Top Performers")
        cols = st.columns(4)
        for i in range(4):
            if i < len(df_res):
                item = df_res.iloc[i]
                with cols[i]:
                    st.metric(
                        label=item['Mã'],
                        value=f"{int(item['Giá']):,}đ",
                        delta=f"Score: {item['Điểm']}"
                    )
        
        st.markdown("---")

        # --- SECTION 2: CHART & INFO (SPLIT VIEW) ---
        c_chart, c_info = st.columns([2, 1])
        
        with c_info:
            st.markdown("### 📊 Market Data")
            # Selectbox chọn mã để soi
            selected_stock = st.selectbox("Chọn mã xem chi tiết:", df_res['Mã'].tolist())
            
            # Lấy data mã đã chọn
            stock_data = next(x for x in results if x['Mã'] == selected_stock)
            
            # Hiển thị thông tin dạng thẻ dọc
            st.info(f"**Tín hiệu: {stock_data['Xếp hạng']}**")
            st.write(f"**🎯 Target:** {int(stock_data['Chốt Lời']):,}")
            st.write(f"**🛑 Stoploss:** {int(stock_data['Cắt Lỗ']):,}")
            st.write(f"**📈 P/E:** {stock_data['P/E']}")
            st.write(f"**💰 EPS:** {stock_data['EPS']}")
            
            with st.expander("Lý do AI chọn?"):
                st.write(stock_data['Lý do'])

        with c_chart:
            plot_chart_dashboard(stock_data)

        # --- SECTION 3: FULL DATA TABLE ---
        st.markdown("### 📋 Opportunity Scanner")
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'Giá Mua', 'Chốt Lời', 'Cắt Lỗ', 'P/E', 'Lý do']],
            use_container_width=True,
            column_config={
                "Điểm": st.column_config.ProgressColumn("AI Score", min_value=0, max_value=100, format="%d"),
                "Giá": st.column_config.NumberColumn(format="%d"),
                "Giá Mua": st.column_config.NumberColumn(format="%d"),
                "Chốt Lời": st.column_config.NumberColumn(format="%d"),
                "Cắt Lỗ": st.column_config.NumberColumn(format="%d"),
            },
            height=400
        )
    else:
        st.warning("No opportunities found based on current criteria.")
