import streamlit as st
import pandas as pd
from vnstock import *
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

# Nhóm VN30 hay toàn thị trường
market_scope = st.sidebar.selectbox("Phạm vi lọc", ["VN30", "HOSE (Top 50 Liquidity)"])

# Các tham số kỹ thuật
st.sidebar.subheader("Tiêu chí Kỹ thuật")
min_volume = st.sidebar.number_input("Volume trung bình tối thiểu", value=50000, step=10000)
rsi_min = st.sidebar.slider("RSI tối thiểu (Vùng mua)", 30, 50, 40)
rsi_max = st.sidebar.slider("RSI tối đa (Tránh đu đỉnh)", 60, 90, 70)

st.sidebar.markdown("---")
st.sidebar.info("Tips: RSI trong khoảng 40-70 thường cho điểm mua an toàn trong xu hướng tăng.")

# --- HÀM XỬ LÝ DỮ LIỆU (CACHING ĐỂ TĂNG TỐC) ---

@st.cache_data(ttl=3600) # Cache dữ liệu danh sách mã trong 1 giờ
def get_tickers(scope):
    try:
        if scope == "VN30":
            # Danh sách VN30 cứng (vì API lấy rổ chỉ số đôi khi ko ổn định)
            # Bạn có thể cập nhật danh sách này hoặc dùng hàm listing_companies lọc nhóm
            return ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 
                    'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 
                    'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE']
        else:
            # Lấy top 50 mã thanh khoản tốt nhất HOSE để demo (tránh timeout)
            df = listing_companies(live=True)
            hose_df = df[df['exchange'] == 'HOSE']
            return hose_df['ticker'].head(50).tolist()
    except Exception as e:
        st.error(f"Lỗi lấy danh sách mã: {e}")
        return []

def analyze_stock(symbol):
    """Phân tích kỹ thuật cho 1 mã cổ phiếu"""
    try:
        # Lấy dữ liệu 1 năm
        df = stock_historical_data(symbol=symbol, 
                                   start_date=(pd.Timestamp.now() - pd.DateOffset(years=1)).strftime('%Y-%m-%d'), 
                                   end_date=pd.Timestamp.now().strftime('%Y-%m-%d'), 
                                   resolution='1D')
        
        if df is None or len(df) < 200:
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
    tickers = get_tickers(market_scope)
    
    if not tickers:
        st.error("Không lấy được danh sách cổ phiếu. Vui lòng thử lại sau.")
    else:
        st.write(f"Đang phân tích {len(tickers)} mã cổ phiếu trong danh mục {market_scope}...")
        
        # Thanh tiến trình
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        results = []
        
        for i, ticker in enumerate(tickers):
            # Update tiến trình
            progress = (i + 1) / len(tickers)
            progress_bar.progress(progress)
            status_text.text(f"Đang phân tích: {ticker}...")
            
            data = analyze_stock(ticker)
            if data:
                results.append(data)
            
            # Delay nhẹ để tránh bị chặn API
            time.sleep(0.1)

        progress_bar.empty()
        status_text.empty()

        if results:
            st.success(f"Tìm thấy {len(results)} cổ phiếu tiềm năng!")
            df_results = pd.DataFrame(results)
            
            # Hiển thị bảng dữ liệu có sort
            st.dataframe(
                df_results.style.format({
                    "Giá hiện tại": "{:,.0f}", 
                    "MA50": "{:,.0f}",
                    "MA200": "{:,.0f}",
                    "Vol TB 20": "{:,.0f}"
                }).background_gradient(subset=['RSI (14)'], cmap='Greens'),
                use_container_width=True
            )
            
            # --- VẼ BIỂU ĐỒ KHI CHỌN MÃ ---
            st.markdown("### 📊 Phân tích chi tiết")
            selected_ticker = st.selectbox("Chọn mã để xem biểu đồ:", df_results['Mã CK'])
            
            if selected_ticker:
                with st.spinner(f"Đang vẽ biểu đồ {selected_ticker}..."):
                    df_chart = stock_historical_data(symbol=selected_ticker, 
                                   start_date=(pd.Timestamp.now() - pd.DateOffset(months=6)).strftime('%Y-%m-%d'), 
                                   end_date=pd.Timestamp.now().strftime('%Y-%m-%d'))
                    
                    fig = go.Figure(data=[go.Candlestick(x=df_chart['time'],
                                    open=df_chart['open'], high=df_chart['high'],
                                    low=df_chart['low'], close=df_chart['close'], name="Giá")])
                    
                    fig.update_layout(title=f"Biểu đồ kỹ thuật {selected_ticker}", xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig, use_container_width=True)

        else:
            st.warning("Không tìm thấy cổ phiếu nào thỏa mãn tiêu chí hôm nay. Hãy thử nới lỏng bộ lọc.")

# --- FOOTER ---
st.markdown("---")
st.caption("Developed by Expert Investor & IT Specialist using Streamlit & Vnstock.")
