import streamlit as st
import pandas as pd
import time
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go

# --- CẤU HÌNH IMPORT AN TOÀN ---
# 1. Thử import Vnstock
try:
    from vnstock import listing_companies, stock_historical_data
    VNSTOCK_AVAILABLE = True
except ImportError:
    VNSTOCK_AVAILABLE = False
    # Không báo lỗi ngay, sẽ xử lý logic fallback bên dưới

# 2. Import Yfinance (Dự phòng cấp 2)
import yfinance as yf

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Vũ Phong Stock AI",
    page_icon="📈",
    layout="wide"
)

# --- HEADER ---
st.title("📈 Vũ Phong Stock AI - Screener Pro")
st.markdown("---")

# --- SIDEBAR ---
st.sidebar.header("⚙️ Bộ lọc")
market_scope = st.sidebar.selectbox("Nguồn dữ liệu", ["VN30", "HOSE Top 50"])
min_volume = st.sidebar.number_input("Vol tối thiểu", value=50000, step=10000)
rsi_min = st.sidebar.slider("RSI Min", 30, 50, 30) # Nới rộng mặc định để dễ ra kết quả test
rsi_max = st.sidebar.slider("RSI Max", 60, 90, 80)

# --- CORE FUNCTIONS ---

@st.cache_data(ttl=3600)
def get_tickers_safe(scope):
    """Lấy danh sách mã: Ưu tiên API -> Fallback Hardcode"""
    # Danh sách cứng (Backup list)
    vn30_backup = ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
                   'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
                   'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE']
    
    if scope == "VN30":
        return vn30_backup
    
    # Nếu chọn HOSE Top 50, thử gọi API
    if VNSTOCK_AVAILABLE:
        try:
            df = listing_companies(live=True)
            if df is not None and not df.empty:
                return df[df['exchange'] == 'HOSE']['ticker'].head(50).tolist()
        except Exception:
            pass # Lỗi thì xuống dùng backup
            
    return vn30_backup # Trả về VN30 nếu mọi thứ thất bại

def get_price_data(symbol):
    """
    Lấy dữ liệu giá:
    - Ưu tiên 1: Vnstock (Dữ liệu chuẩn VN)
    - Ưu tiên 2: Yfinance (Nếu Vnstock lỗi/bị chặn IP)
    """
    df = None
    
    # Cách 1: Thử Vnstock
    if VNSTOCK_AVAILABLE:
        try:
            end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
            start_date = (pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d')
            df = stock_historical_data(symbol=symbol, start_date=start_date, end_date=end_date, resolution='1D')
        except Exception:
            df = None
            
    # Cách 2: Nếu Vnstock thất bại, dùng Yfinance
    if df is None or df.empty:
        try:
            # Yfinance cần thêm đuôi .VN cho cổ phiếu Việt Nam
            yf_symbol = f"{symbol}.VN"
            df_yf = yf.download(yf_symbol, period="1y", interval="1d", progress=False)
            if not df_yf.empty:
                # Chuẩn hóa format cột cho giống vnstock
                df = df_yf.reset_index()
                df.columns = df.columns.str.lower()
                # Yfinance trả về: Date, Open, High, Low, Close, Volume
                df = df.rename(columns={'date': 'time'})
        except Exception:
            pass
            
    return df

def analyze_stock(symbol):
    try:
        df = get_price_data(symbol)
        
        if df is None or len(df) < 50: # Cần ít nhất 50 nến
            return None

        # Đảm bảo dữ liệu dạng số (Yfinance đôi khi trả về object)
        cols = ['close', 'volume']
        for col in cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')
            
        # Tính chỉ báo
        df['MA50'] = SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['MA200'] = SMAIndicator(close=df['close'], window=200).sma_indicator()
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        last = df.iloc[-1]
        
        # Xử lý trường hợp MA200 chưa đủ dữ liệu (NaN)
        ma200_val = last['MA200'] if not pd.isna(last['MA200']) else last['MA50']
        
        is_uptrend = last['close'] > ma200_val
        is_rsi_ok = rsi_min <= last['RSI'] <= rsi_max
        is_liquid = last['volume'] >= min_volume

        if is_uptrend and is_liquid and is_rsi_ok:
            return {
                'Mã': symbol,
                'Giá': last['close'],
                'RSI': round(last['RSI'], 2),
                'MA50': round(last['MA50'], 0),
                'Vol': int(last['volume'])
            }
        return None
    except Exception as e:
        return None

# --- MAIN APP ---

if st.button("🚀 Quét Thị Trường", type="primary"):
    with st.spinner("Đang khởi tạo..."):
        tickers = get_tickers_safe(market_scope)
        
    st.info(f"Đang phân tích {len(tickers)} mã ({'Nguồn: Đa kênh'})...")
    
    bar = st.progress(0)
    results = []
    
    # Placeholder để hiện mã đang chạy
    status = st.empty()
    
    for i, ticker in enumerate(tickers):
        bar.progress((i+1)/len(tickers))
        status.text(f"Checking {ticker}...")
        
        data = analyze_stock(ticker)
        if data:
            results.append(data)
            
        # Không cần sleep nếu dùng yfinance, nhưng giữ nhẹ để UI mượt
        time.sleep(0.01) 
        
    status.empty()
    bar.empty()
    
    if results:
        st.success(f"✅ Tìm thấy {len(results)} mã tiềm năng!")
        df_res = pd.DataFrame(results)
        
        # Format hiển thị
        st.dataframe(
            df_res.style.background_gradient(subset=['RSI'], cmap='Greens')
                        .format("{:.0f}", subset=['Giá', 'MA50', 'Vol']),
            use_container_width=True
        )
        
        # Vẽ biểu đồ
        st.write("### 🔎 Soi biểu đồ")
        pick = st.selectbox("Chọn mã:", df_res['Mã'])
        if pick:
            df_chart = get_price_data(pick)
            if df_chart is not None:
                fig = go.Figure(data=[go.Candlestick(x=df_chart['time'],
                    open=df_chart['open'], high=df_chart['high'],
                    low=df_chart['low'], close=df_chart['close'])])
                fig.update_layout(title=f"Chart {pick}", xaxis_rangeslider_visible=False)
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("⚠️ Không tìm thấy mã nào. Hãy thử giảm RSI Min xuống 30 để kiểm tra hệ thống.")
