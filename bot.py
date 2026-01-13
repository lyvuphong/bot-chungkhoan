import streamlit as st
import pandas as pd
# SỬA ĐỔI QUAN TRỌNG: Import cụ thể từng hàm để tránh lỗi "not defined"
try:
    from vnstock import listing_companies, stock_historical_data
except ImportError:
    # Fallback nếu thư viện lỗi import
    st.error("Lỗi thư viện vnstock. Đang sử dụng chế độ dự phòng.")
    
from ta.trend import SMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
import time

# --- CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="Vũ Phong Stock AI - Investment Screener",
    page_icon="📈",
    layout="wide"
)

# --- PHẦN HEADER & GIỚI THIỆU ---
st.title("📈 Vũ Phong Stock AI - Công cụ lọc Cổ phiếu Chiến lược")
st.markdown("""
**Triết lý đầu tư:** Tăng trưởng bền vững & Kỹ thuật chuẩn xác.
*Công cụ hỗ trợ lọc cổ phiếu theo phương pháp CANSLIM kết hợp Technical Analysis.*
""")

# --- SIDEBAR: CẤU HÌNH BỘ LỌC ---
st.sidebar.header("⚙️ Tham số bộ lọc")

market_scope = st.sidebar.selectbox("Phạm vi lọc", ["VN30", "HOSE (Top Liquidity)"])

st.sidebar.subheader("Tiêu chí Kỹ thuật")
min_volume = st.sidebar.number_input("Volume trung bình tối thiểu", value=50000, step=10000)
rsi_min = st.sidebar.slider("RSI tối thiểu (Vùng mua)", 30, 50, 40)
rsi_max = st.sidebar.slider("RSI tối đa (Tránh đu đỉnh)", 60, 90, 70)

st.sidebar.markdown("---")
st.sidebar.info("Tips: RSI trong khoảng 40-70 thường cho điểm mua an toàn trong xu hướng tăng.")

# --- HÀM XỬ LÝ DỮ LIỆU ---

@st.cache_data(ttl=3600)
def get_tickers(scope):
    """
    Hàm lấy danh sách mã chứng khoán an toàn.
    Nếu API lỗi, tự động trả về danh sách cứng (Hardcoded) để App không bị crash.
    """
    # Danh sách dự phòng (Fallback list) - Top thanh khoản HOSE
    backup_tickers = [
        'HPG', 'SSI', 'VND', 'STB', 'DIG', 'NVL', 'DXG', 'SHB', 'VPB', 'VIX',
        'MBB', 'GEX', 'TCB', 'ACB', 'MWG', 'VHM', 'PDR', 'VCI', 'HSG', 'MSN',
        'VNM', 'CTG', 'TPB', 'VIC', 'FPT', 'HDB', 'VRE', 'DGC', 'KBC', 'VGC',
        'DGW', 'FRT', 'GVR', 'POW', 'HCM', 'BID', 'PLX', 'VHC', 'ANV', 'DPM'
    ]
    
    vn30_tickers = [
        'ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
        'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
        'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'
    ]

    try:
        if scope == "VN30":
            return vn30_tickers
        else:
            # Cố gắng gọi API
            try:
                df = listing_companies(live=True)
                hose_df = df[df['exchange'] == 'HOSE']
                # Lấy 50 mã đầu tiên để demo nhanh
                return hose_df['ticker'].head(50).tolist()
            except Exception as e:
                # Nếu API lỗi (do mạng hoặc do thư viện), dùng danh sách dự phòng
                print(f"API Error: {e}. Switching to backup list.")
                return backup_tickers
                
    except Exception as e:
        st.warning(f"Không lấy được dữ liệu trực tuyến: {e}. Đang dùng dữ liệu offline.")
        return backup_tickers

def analyze_stock(symbol):
    try:
        # Lấy dữ liệu 1 năm
        df = stock_historical_data(symbol=symbol, 
                                   start_date=(pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d'), 
                                   end_date=pd.Timestamp.now().strftime('%Y-%m-%d'), 
                                   resolution='1D')
        
        if df is None or df.empty or len(df) < 200:
            return None

        # Tính chỉ báo
        df['MA50'] = SMAIndicator(close=df['close'], window=50).sma_indicator()
        df['MA200'] = SMAIndicator(close=df['close'], window=200).sma_indicator()
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        last = df.iloc[-1]
        avg_vol = df['volume'].tail(20).mean()

        # Logic lọc
        is_uptrend = (last['close'] > last['MA200']) and (last['MA50'] > last['MA200'])
        is_liquid = avg_vol >= min_volume
        is_rsi_ok = rsi_min <= last['RSI'] <= rsi_max

        if is_uptrend and is_liquid and is_rsi_ok:
            return {
                'Mã CK': symbol,
                'Giá hiện tại': last['close'],
                'RSI (14)': round(last['RSI'], 2),
                'MA50': round(last['MA50'], 0),
                'MA200': round(last['MA200'], 0),
                'Vol TB 20': int(avg_vol),
                'Xu hướng': 'Tăng'
            }
        return None
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---

if st.button("🚀 Bắt đầu Lọc Cổ phiếu", type="primary"):
    with st.spinner("Đang khởi tạo dữ liệu thị trường..."):
        tickers = get_tickers(market_scope)
    
    if not tickers:
        st.error("Hệ thống đang bảo trì dữ liệu mã. Vui lòng quay lại sau.")
    else:
        st.write(f"Đang phân tích {len(tickers)} mã cổ phiếu ({market_scope})...")
        
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        for i, ticker in enumerate(tickers):
            progress = (i + 1) / len(tickers)
            progress_bar.progress(progress)
            status_text.text(f"Scanning: {ticker}...")
            
            data = analyze_stock(ticker)
            if data:
                results.append(data)
            
            # Delay cực nhỏ để UI mượt hơn
            time.sleep(0.05)

        progress_bar.empty()
        status_text.empty()

        if results:
            st.success(f"Tìm thấy {len(results)} cổ phiếu tiềm năng!")
            df_results = pd.DataFrame(results)
            
            st.dataframe(
                df_results.style.format({
                    "Giá hiện tại": "{:,.0f}", 
                    "MA50": "{:,.0f}",
                    "MA200": "{:,.0f}",
                    "Vol TB 20": "{:,.0f}"
                }).background_gradient(subset=['RSI (14)'], cmap='Greens'),
                use_container_width=True
            )
            
            st.markdown("### 📊 Phân tích chi tiết")
            selected_ticker = st.selectbox("Chọn mã để xem biểu đồ:", df_results['Mã CK'])
            
            if selected_ticker:
                with st.spinner(f"Đang vẽ biểu đồ {selected_ticker}..."):
                    try:
                        df_chart = stock_historical_data(symbol=selected_ticker, 
                                    start_date=(pd.Timestamp.now() - pd.DateOffset(months=6)).strftime('%Y-%m-%d'), 
                                    end_date=pd.Timestamp.now().strftime('%Y-%m-%d'))
                        
                        if df_chart is not None and not df_chart.empty:
                            fig = go.Figure(data=[go.Candlestick(x=df_chart['time'],
                                            open=df_chart['open'], high=df_chart['high'],
                                            low=df_chart['low'], close=df_chart['close'], name="Giá")])
                            
                            fig.update_layout(title=f"Biểu đồ kỹ thuật {selected_ticker}", xaxis_rangeslider_visible=False)
                            st.plotly_chart(fig, use_container_width=True)
                        else:
                            st.warning("Không tải được dữ liệu biểu đồ.")
                    except Exception as e:
                        st.error(f"Lỗi vẽ biểu đồ: {e}")

        else:
            st.warning("Không tìm thấy mã nào. Hãy thử nới rộng khoảng RSI (ví dụ: 30-80).")

# --- FOOTER ---
st.markdown("---")
st.caption("Developed by Expert Investor & IT Specialist using Streamlit & Vnstock.")
