import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH GIAO DIỆN PRO ---
st.set_page_config(
    page_title="AI Stock Terminal", 
    layout="wide", 
    page_icon="📈",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH (GIAO DIỆN ĐẸP) ---
st.markdown("""
<style>
    /* Chỉnh Font và màu nền */
    .main {background-color: #f8f9fa;}
    h1 {color: #1f77b4; font-family: 'Helvetica', sans-serif;}
    
    /* Style cho các thẻ Metric */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    
    /* Chỉnh bảng dữ liệu */
    div[data-testid="stDataFrame"] {
        border-radius: 10px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. KHO DỮ LIỆU ---
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

# --- 3. HÀM PHÂN TÍCH (LOGIC ỔN ĐỊNH) ---
def analyze_stock_final(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or df.empty or len(df) < 50:
            return None, "No Data"

        # Tính chỉ báo (Thủ công để tránh lỗi)
        try:
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
        except:
            return None, "Calc Error"

        latest = df.iloc[-1]
        
        # --- CHẤM ĐIỂM ---
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

        # 4. Tài chính (Info)
        pe, eps, roe = 0, 0, 0
        if score >= 40:
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
            "P/E": round(pe, 1) if pe else 0, 
            "EPS": eps if eps else 0,
            "ROE": round(roe*100, 1) if roe else 0,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }, "OK"

    except Exception:
        return None, "Error"

# --- 4. VẼ BIỂU ĐỒ PRO (DARK THEME & SUBPLOTS) ---
def plot_chart_pro(data):
    df = data['Dataframe']
    symbol = data['Mã']
    
    # Tạo biểu đồ 2 ngăn (Giá ở trên, Vol ở dưới)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Nến
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name='Giá'
    ), row=1, col=1)
    
    # MA
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='#00F0FF', width=1), name='MA50'), row=1, col=1)

    # Volume (Tô màu xanh/đỏ)
    colors = ['red' if row['Open'] - row['Close'] >= 0 else 'green' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

    # Layout đẹp
    fig.update_layout(
        title=f"📈 Phân tích kỹ thuật: {symbol} (Score: {data['Điểm']})",
        xaxis_rangeslider_visible=False,
        height=600,
        template="plotly_white", # Nền trắng sạch sẽ
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", y=1, x=0, xanchor="left", yanchor="bottom")
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.image("https://cdn-icons-png.flaticon.com/512/10452/10452445.png", width=80)
    st.title("AI TRADING BOT")
    st.markdown("---")
    
    st.subheader("⚙️ Cấu Hình Quét")
    sectors = ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"]
    choice = st.multiselect("Chọn ngành:", sectors, default=["QUÉT TOÀN BỘ"])
    
    min_score = st.slider("Điểm tối thiểu", 0, 100, 40)
    
    st.markdown("---")
    btn_scan = st.button("🚀 KÍCH HOẠT HỆ THỐNG", type="primary", use_container_width=True)
    st.caption("v2.5 Stable - Developed by VuPhong")

# HEADER TRANG CHÍNH
st.title("📊 BẢNG ĐIỀU KHIỂN TÍN HIỆU THỊ TRƯỜNG")
st.markdown("Hệ thống phân tích tự động dựa trên **Price Action** và **Dòng tiền thông minh**.")

if btn_scan:
    symbols = get_stock_universe(choice)
    
    # Hiển thị Toast thông báo bắt đầu
    st.toast(f"Đang khởi động AI Scanner cho {len(symbols)} mã...", icon="🤖")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    # Container để hiện log gọn gàng
    with st.expander("Show Logs (Nhật ký quét)", expanded=False):
        log_container = st.container()
    
    for i, sym in enumerate(symbols):
        status_text.caption(f"🤖 AI đang phân tích: **{sym}** ({i+1}/{len(symbols)})")
        time.sleep(0.05) # Tránh chặn IP nhẹ
        
        data, msg = analyze_stock_final(sym)
        
        if data:
            if data['Điểm'] >= min_score:
                results.append(data)
                log_container.write(f"🟢 {sym}: Đạt chuẩn ({data['Điểm']}đ)")
            else:
                log_container.write(f"⚪ {sym}: Điểm thấp ({data['Điểm']}đ)")
        
        progress_bar.progress((i+1)/len(symbols))
        
    status_text.empty()
    st.toast("Quét hoàn tất!", icon="✅")

    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        
        # --- TOP 3 HIGHLIGHTS (DASHBOARD) ---
        st.markdown("### 🏆 Top Cổ Phiếu Tiềm Năng Nhất")
        top_cols = st.columns(3)
        for idx, col in enumerate(top_cols):
            if idx < len(df_res):
                item = df_res.iloc[idx]
                col.metric(
                    label=f"{item['Mã']} ({item['Xếp hạng']})",
                    value=f"{int(item['Giá']):,} đ",
                    delta=f"Score: {item['Điểm']}/100"
                )

        # --- BẢNG DỮ LIỆU CHUYÊN NGHIỆP ---
        st.markdown("### 📋 Danh Sách Chi Tiết")
        
        # Cấu hình bảng hiển thị đẹp mắt
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'ROE', 'Lý do']],
            use_container_width=True,
            column_config={
                "Giá": st.column_config.NumberColumn(format="%d đ"),
                "EPS": st.column_config.NumberColumn(format="%d"),
                "P/E": st.column_config.NumberColumn(format="%.1f"),
                "ROE": st.column_config.NumberColumn(format="%.1f %%"),
                "Điểm": st.column_config.ProgressColumn(
                    "Sức mạnh AI",
                    format="%d",
                    min_value=0,
                    max_value=100,
                    help="Điểm số càng cao, tín hiệu mua càng mạnh",
                ),
                "Xếp hạng": st.column_config.TextColumn(
                    "Khuyến nghị",
                ),
            },
            height=400
        )
        
        # --- BIỂU ĐỒ TƯƠNG TÁC ---
        st.divider()
        st.markdown("### 📈 Phân Tích Kỹ Thuật (Interactive Chart)")
        
        c1, c2 = st.columns([1, 3])
        with c1:
            stock_list = df_res['Mã'].tolist()
            selected = st.selectbox("🔍 Chọn mã để soi Chart:", stock_list)
            
            # Hiện chỉ số cơ bản bên cạnh chart
            sel_data = df_res[df_res['Mã'] == selected].iloc[0]
            st.info(f"**{selected}**")
            st.write(f"**P/E:** {sel_data['P/E']}")
            st.write(f"**EPS:** {sel_data['EPS']}")
            st.write(f"**ROE:** {sel_data['ROE']}%")
            
        with c2:
            item = next((x for x in results if x['Mã'] == selected), None)
            if item: plot_chart_pro(item)
            
    else:
        st.warning("Không tìm thấy mã nào! Hãy thử giảm điểm lọc xuống.")
