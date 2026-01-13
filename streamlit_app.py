import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(page_title="Vũ Phong Stock AI", page_icon="📈", layout="wide")

# --- DANH SÁCH MÃ CỨNG (ĐỂ CHẠY ỔN ĐỊNH TRÊN CLOUD) ---
# Đây là Top 40 cổ phiếu thanh khoản cao nhất, đại diện thị trường
TOP_STOCKS = [
    'HPG', 'SSI', 'VND', 'STB', 'DIG', 'NVL', 'DXG', 'SHB', 'VPB', 'VIX',
    'MBB', 'GEX', 'TCB', 'ACB', 'MWG', 'VHM', 'PDR', 'VCI', 'HSG', 'MSN',
    'VNM', 'CTG', 'TPB', 'VIC', 'FPT', 'HDB', 'VRE', 'DGC', 'KBC', 'VGC',
    'DGW', 'FRT', 'GVR', 'POW', 'HCM', 'BID', 'PLX', 'VHC', 'ANV', 'DPM'
]

# --- SIDEBAR ---
st.sidebar.title("⚙️ Cấu hình Bot")
st.sidebar.caption("Chế độ: Server Quốc tế (Yahoo Finance)")

min_vol = st.sidebar.number_input("Volume tối thiểu", 50000, step=10000, value=100000)
rsi_min = st.sidebar.slider("RSI Min (Vùng mua)", 0, 50, 30)
rsi_max = st.sidebar.slider("RSI Max (Vùng bán)", 60, 100, 75)

st.title("📈 Vũ Phong Stock AI - Screener Pro")
st.info("💡 Hệ thống sử dụng dữ liệu Yahoo Finance để đảm bảo tính ổn định trên Streamlit Cloud.")

# --- CORE FUNCTIONS ---

@st.cache_data(ttl=300) # Cache 5 phút
def get_stock_data_yfinance(symbol):
    """
    Hàm lấy dữ liệu bao sân: Tự động xử lý Multi-index của Yahoo
    """
    try:
        # Thêm đuôi .VN
        ticker = f"{symbol}.VN"
        
        # Tải dữ liệu 1 năm
        df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
        
        if df.empty:
            return None

        # --- QUAN TRỌNG: CHUẨN HÓA DỮ LIỆU ---
        # Yahoo bản mới trả về MultiIndex (Price, Ticker), cần san phẳng
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
            
        # Đổi tên cột về chữ thường để code dễ xử lý
        df.columns = [c.lower() for c in df.columns]
        
        # Kiểm tra đủ cột không
        required_cols = ['close', 'volume']
        if not all(col in df.columns for col in required_cols):
            return None
            
        return df
    except Exception as e:
        return None

def analyze_stock(symbol):
    df = get_stock_data_yfinance(symbol)
    
    if df is None or len(df) < 50: # Cần ít nhất 50 phiên
        return None
    
    # Tính toán chỉ số
    try:
        # RSI
        rsi_indicator = RSIIndicator(close=df['close'], window=14)
        df['RSI'] = rsi_indicator.rsi()
        
        # MA
        sma50 = SMAIndicator(close=df['close'], window=50)
        df['MA50'] = sma50.sma_indicator()
        
        sma200 = SMAIndicator(close=df['close'], window=200)
        df['MA200'] = sma200.sma_indicator()
        
        # Lấy giá trị phiên gần nhất
        last = df.iloc[-1]
        
        # --- LOGIC LỌC ---
        # 1. Kiểm tra Volume
        avg_vol = df['volume'].tail(20).mean()
        if avg_vol < min_vol:
            return None
            
        # 2. Kiểm tra RSI
        current_rsi = last['RSI']
        if not (rsi_min <= current_rsi <= rsi_max):
            return None
            
        # 3. Xu hướng (Optional: Chỉ lấy mã nằm trên MA50)
        # if last['close'] < last['MA50']: return None 

        return {
            'Mã': symbol,
            'Giá': last['close'] * 1000 if last['close'] < 500 else last['close'], # Fix lỗi đơn vị nghìn đồng
            'RSI': round(current_rsi, 2),
            'MA50': round(last['MA50'], 0) if not pd.isna(last['MA50']) else 0,
            'Vol TB': int(avg_vol),
            'Trạng thái': '🟢 Mua/Nắm giữ' if current_rsi < 60 else '🟡 Cẩn trọng'
        }
    except Exception as e:
        return None

# --- MAIN APP FLOW ---

if st.button("🚀 BẮT ĐẦU QUÉT", type="primary"):
    
    results = []
    progress_text = "Đang quét thị trường..."
    my_bar = st.progress(0, text=progress_text)
    
    # Container hiển thị log chạy
    log_col = st.empty()
    
    for i, ticker in enumerate(TOP_STOCKS):
        # Update progress
        percent = (i + 1) / len(TOP_STOCKS)
        my_bar.progress(percent, text=f"Đang phân tích: {ticker} ({i+1}/{len(TOP_STOCKS)})")
        
        # Phân tích
        data = analyze_stock(ticker)
        if data:
            results.append(data)
            
    my_bar.empty()
    
    if results:
        st.success(f"✅ Tìm thấy {len(results)} mã cổ phiếu tiềm năng!")
        
        df_results = pd.DataFrame(results)
        
        # Hiển thị bảng đẹp
        st.dataframe(
            df_results.style.background_gradient(subset=['RSI'], cmap='RdYlGn_r')
                      .format("{:,.0f}", subset=['Giá', 'Vol TB', 'MA50']),
            use_container_width=True,
            height=400
        )
        
        # --- BIỂU ĐỒ ---
        st.markdown("### 🔎 Soi chi tiết")
        selected = st.selectbox("Chọn mã xem chart:", df_results['Mã'])
        
        if selected:
            df_chart = get_stock_data_yfinance(selected)
            if df_chart is not None:
                fig = go.Figure(data=[go.Candlestick(x=df_chart.index,
                    open=df_chart['open'], high=df_chart['high'],
                    low=df_chart['low'], close=df_chart['close'])])
                fig.update_layout(title=f"Biểu đồ {selected}", xaxis_rangeslider_visible=False, height=500)
                st.plotly_chart(fig, use_container_width=True)
                
    else:
        st.warning("⚠️ Không tìm thấy mã nào! Hãy thử mở rộng khoảng RSI (ví dụ: 30-80).")

st.markdown("---")
st.caption("Developed by Expert Investor & IT Specialist.")
