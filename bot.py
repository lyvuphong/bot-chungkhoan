import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import *
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Trading Pro", layout="wide", page_icon="📈")
st.markdown("""<style>.stMetric {background-color: #f0f2f6; padding: 10px; border-radius: 10px;}</style>""", unsafe_allow_html=True)

st.title("📈 HỆ THỐNG TRUY VẤN & PHÂN TÍCH CỔ PHIẾU AI")
st.caption("Developed by VuPhong | Data: VNStock | Strategy: Trend + Momentum")

# --- 2. HÀM DATA & XỬ LÝ ---
@st.cache_data(ttl=3600)
def get_symbol_list():
    # Danh sách VN100 + Các mã hot (Mở rộng để bắt nhiều cơ hội hơn)
    return [
        "FPT", "MWG", "HPG", "VCB", "TCB", "MBB", "ACB", "STB", "VIP", "VRE",
        "VHM", "VIC", "MSN", "GAS", "POW", "PLX", "VNM", "SAB", "GVR", "KDH",
        "PDR", "SSI", "VCI", "HCM", "VND", "DGC", "DXG", "NKG", "HSG", "DBC",
        "FRT", "PNJ", "REE", "GEX", "VGC", "IDC", "KBC", "SZC", "PC1", "HDG",
        "ANV", "VHC", "FTS", "BSI", "CTS", "DIG", "CEO", "NVL", "HDB", "TPB",
        "DGW", "HAH", "VOS", "PVD", "PVS", "PVT", "VIX", "ORS", "TCH", "HUT"
    ]

def analyze_stock_ultimate(symbol):
    try:
        # Lấy dữ liệu dài hơn để vẽ chart (1 năm)
        df = stock_historical_data(symbol, "2025-01-01", "2026-01-13", "1D", "stock")
        if df is None or len(df) < 100: return None
        
        # Chỉ báo kỹ thuật
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        # Lấy nến mới nhất
        latest = df.iloc[-1]
        
        # --- HỆ THỐNG CHẤM ĐIỂM (SCORING) ---
        score = 0
        reasons = []
        
        # 1. Trend (40đ)
        if latest['close'] > latest['MA20']: score += 20
        if latest['MA20'] > latest['MA50']: 
            score += 20
            reasons.append("Uptrend")
            
        # 2. RSI (30đ)
        if 45 <= latest['RSI'] <= 70: 
            score += 30
            reasons.append("RSI Khỏe")
        elif latest['RSI'] > 70:
            score += 10
            reasons.append("RSI Nóng")
            
        # 3. Thanh khoản (30đ) - So với hôm qua
        if latest['volume'] > df.iloc[-2]['volume']:
            score += 30
            reasons.append("Tiền vào")
            
        return {
            "Mã": symbol,
            "Giá": int(latest['close']),
            "RSI": round(latest['RSI'], 1),
            "Điểm AI": score,
            "Tín hiệu": ", ".join(reasons) if reasons else "Yếu",
            "Dataframe": df # Lưu lại data để vẽ chart sau
        }
    except:
        return None

# --- 3. VẼ BIỂU ĐỒ NẾN ---
def plot_chart(df, symbol):
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        vertical_spacing=0.05, row_heights=[0.7, 0.3])

    # Nến
    fig.add_trace(go.Candlestick(x=df.index, open=df['open'], high=df['high'],
                low=df['low'], close=df['close'], name='Giá'), row=1, col=1)
    
    # MA20, MA50
    fig.add_trace(go.Scatter(x=df.index, y=df['MA20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['MA50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)

    # Volume
    fig.add_trace(go.Bar(x=df.index, y=df['volume'], name='Vol', marker_color='teal'), row=2, col=1)

    fig.update_layout(title=f"Biểu đồ kỹ thuật: {symbol}", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BẢNG ĐIỀU KHIỂN")
    # Cho phép chỉnh điểm thấp xuống để test
    min_score = st.slider("Điểm lọc tối thiểu", 0, 100, 50) 
    st.info("💡 Mẹo: Hạ điểm xuống 50 nếu thị trường xấu để tìm cơ hội hồi phục.")
    
    btn_scan = st.button("QUÉT THỊ TRƯỜNG NGAY 🚀", type="primary")

# LOGIC CHẠY
if btn_scan:
    symbols = get_symbol_list()
    status = st.status("🤖 AI đang phân tích dữ liệu thị trường...", expanded=True)
    
    valid_stocks = []
    
    # Thanh tiến trình
    progress_bar = status.progress(0)
    for i, sym in enumerate(symbols):
        res = analyze_stock_ultimate(sym)
        if res and res['Điểm AI'] >= min_score:
            valid_stocks.append(res)
        progress_bar.progress((i+1)/len(symbols))
        
    status.update(label="✅ Đã hoàn tất phân tích!", state="complete", expanded=False)

    if valid_stocks:
        # Sắp xếp mã điểm cao nhất lên đầu
        df_show = pd.DataFrame(valid_stocks).sort_values(by="Điểm AI", ascending=False)
        
        # 1. Hiển thị Metrics Top 3
        st.subheader("🏆 TOP 3 CỔ PHIẾU MẠNH NHẤT")
        cols = st.columns(3)
        for idx, col in enumerate(cols):
            if idx < len(df_show):
                stock = df_show.iloc[idx]
                col.metric(
                    label=f"{stock['Mã']} ({stock['Tín hiệu']})",
                    value=f"{stock['Giá']:,} VNĐ",
                    delta=f"AI Score: {stock['Điểm AI']}/100"
                )
        
        # 2. Bảng chi tiết
        st.subheader("📋 DANH SÁCH KHUYẾN NGHỊ")
        st.dataframe(
            df_show[['Mã', 'Giá', 'RSI', 'Điểm AI', 'Tín hiệu']].style.background_gradient(subset=['Điểm AI'], cmap='Greens'),
            use_container_width=True
        )
        
        # 3. Soi biểu đồ chi tiết
        st.divider()
        st.subheader("🔍 SOI CHART CHI TIẾT")
        selected_stock = st.selectbox("Chọn mã để xem biểu đồ:", df_show['Mã'].tolist())
        
        # Tìm data của mã được chọn để vẽ
        stock_data = next(item for item in valid_stocks if item["Mã"] == selected_stock)
        plot_chart(stock_data['Dataframe'], selected_stock)
        
    else:
        st.warning(f"Không tìm thấy mã nào > {min_score} điểm. Hãy thử hạ tiêu chuẩn lọc ở thanh bên trái!")
else:
    st.info("👈 Bấm nút 'QUÉT THỊ TRƯỜNG NGAY' ở bên trái để bắt đầu.")
