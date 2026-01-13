import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH GIAO DIỆN PRO ---
st.set_page_config(
    page_title="AI Stock Terminal (Trade Plan)", 
    layout="wide", 
    page_icon="🎯",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH ---
st.markdown("""
<style>
    .main {background-color: #f8f9fa;}
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e6e9ef;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
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

# --- 3. HÀM PHÂN TÍCH & LẬP KẾ HOẠCH ---
def analyze_stock_final(symbol):
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or df.empty or len(df) < 50:
            return None, "No Data"

        # Tính chỉ báo
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

        # --- LẬP KẾ HOẠCH TRADE (PLAN) ---
        entry_price = close
        
        # Stoploss: Giá thấp nhất 20 phiên gần nhất (Hỗ trợ cứng)
        support_level = df['Low'].tail(20).min()
        
        # Nếu hỗ trợ quá xa (>7%), siết lại còn 7% để quản trị rủi ro
        risk_percent = (entry_price - support_level) / entry_price
        if risk_percent > 0.07:
            stop_loss = entry_price * 0.93 # Cắt lỗ 7%
        else:
            stop_loss = support_level
            
        # Target: Tỷ lệ R:R = 1:2 (Lãi gấp đôi lỗ)
        risk_amount = entry_price - stop_loss
        if risk_amount <= 0: risk_amount = entry_price * 0.05 # Fallback
        
        take_profit = entry_price + (risk_amount * 2)

        # 4. Tài chính (Info) - Chỉ lấy nếu điểm cao
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
            "Giá Mua": entry_price,
            "Cắt Lỗ": stop_loss,
            "Chốt Lời": take_profit,
            "P/E": round(pe, 1) if pe else 0, 
            "EPS": eps if eps else 0,
            "ROE": round(roe*100, 1) if roe else 0,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }, "OK"

    except Exception:
        return None, "Error"

# --- 4. VẼ BIỂU ĐỒ PLAN ---
def plot_chart_pro(data):
    df = data['Dataframe']
    symbol = data['Mã']
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Nến
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
    
    # MA
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    
    # --- VẼ ĐƯỜNG PLAN ---
    # Đường Mua
    fig.add_hline(y=data['Giá Mua'], line_dash="dot", line_color="gray", annotation_text="ENTRY", row=1, col=1)
    # Đường Cắt Lỗ (Đỏ)
    fig.add_hline(y=data['Cắt Lỗ'], line_dash="dash", line_color="red", annotation_text=f"STOPLOSS: {int(data['Cắt Lỗ']):,}", row=1, col=1)
    # Đường Chốt Lời (Xanh)
    fig.add_hline(y=data['Chốt Lời'], line_dash="dash", line_color="#00CC96", annotation_text=f"TARGET: {int(data['Chốt Lời']):,}", row=1, col=1)

    # Volume
    colors = ['red' if row['Open'] - row['Close'] >= 0 else 'green' for index, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

    fig.update_layout(
        title=f"🎯 Kế hoạch giao dịch: {symbol} (R:R = 1:2)",
        xaxis_rangeslider_visible=False,
        height=600,
        template="plotly_white",
        margin=dict(l=50, r=50, t=50, b=50),
        legend=dict(orientation="h", y=1, x=0)
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.title("🎯 AI TRADING BOT")
    st.markdown("---")
    sectors = ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"]
    choice = st.multiselect("Chọn ngành:", sectors, default=["QUÉT TOÀN BỘ"])
    min_score = st.slider("Điểm tối thiểu", 0, 100, 40)
    st.markdown("---")
    btn_scan = st.button("🚀 TÌM ĐIỂM MUA BÁN", type="primary", use_container_width=True)

st.title("📊 BẢNG TÍN HIỆU & KẾ HOẠCH GIAO DỊCH")
st.caption("Hệ thống tự động tính toán điểm Cắt lỗ & Chốt lời theo tỷ lệ Risk/Reward.")

if btn_scan:
    symbols = get_stock_universe(choice)
    st.toast(f"Đang tính toán Trade Plan cho {len(symbols)} mã...", icon="🤖")
    
    progress_bar = st.progress(0)
    results = []
    
    for i, sym in enumerate(symbols):
        time.sleep(0.05)
        data, msg = analyze_stock_final(sym)
        if data and data['Điểm'] >= min_score:
            results.append(data)
        progress_bar.progress((i+1)/len(symbols))
        
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        
        # --- DASHBOARD TOP 3 ---
        cols = st.columns(3)
        for idx, col in enumerate(cols):
            if idx < len(df_res):
                item = df_res.iloc[idx]
                col.metric(
                    label=f"{item['Mã']} (Target: {int(item['Chốt Lời']):,})",
                    value=f"{int(item['Giá']):,} đ",
                    delta=f"Lãi dự kiến: +{round((item['Chốt Lời']-item['Giá'])/item['Giá']*100, 1)}%"
                )

        # --- BẢNG CHI TIẾT ---
        st.markdown("### 📋 Danh Sách & Điểm Vào Lệnh")
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'Giá Mua', 'Cắt Lỗ', 'Chốt Lời', 'P/E', 'Lý do']],
            use_container_width=True,
            column_config={
                "Giá": st.column_config.NumberColumn(format="%d"),
                "Giá Mua": st.column_config.NumberColumn(format="%d", help="Vùng giá mua khuyến nghị"),
                "Cắt Lỗ": st.column_config.NumberColumn(format="%d", help="Thủng giá này phải bán ngay"),
                "Chốt Lời": st.column_config.NumberColumn(format="%d", help="Mục tiêu chốt lời (R:R 1:2)"),
                "Điểm": st.column_config.ProgressColumn("Score", format="%d", min_value=0, max_value=100),
            },
            height=500
        )
        
        # --- BIỂU ĐỒ PLAN ---
        st.divider()
        st.markdown("### 🎯 Soi Kế Hoạch Giao Dịch")
        c1, c2 = st.columns([1, 3])
        with c1:
            selected = st.selectbox("Chọn mã để xem Plan:", df_res['Mã'].tolist())
            row = df_res[df_res['Mã'] == selected].iloc[0]
            st.info(f"**PLAN: {selected}**")
            st.success(f"🎯 Target: {int(row['Chốt Lời']):,}")
            st.error(f"🛑 Stoploss: {int(row['Cắt Lỗ']):,}")
            st.warning(f"⚖️ Tỷ lệ R:R: 1:2")
            
        with c2:
            item = next((x for x in results if x['Mã'] == selected), None)
            if item: plot_chart_pro(item)
            
    else:
        st.warning("Không tìm thấy mã nào! Hãy giảm điểm lọc.")
