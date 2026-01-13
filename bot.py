import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import stock_historical_data
from datetime import datetime, timedelta
import plotly.graph_objects as go

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="VN-Stock AI Filter", layout="wide", page_icon="📈")
st.title("🤖 HỆ THỐNG LỌC CỔ PHIẾU VIỆT NAM (PRO VERSION)")
st.markdown("---")

# --- 2. SIDEBAR CẤU HÌNH ---
st.sidebar.header("⚙️ THAM SỐ LỌC")

# Input mã chứng khoán
default_tickers = "FPT, HPG, SSI, VND, MBB, TCB, STB, VNM, MWG, DXG, PDR, DIG, VCI"
input_symbols = st.sidebar.text_area("Danh sách mã (cách nhau dấu phẩy)", default_tickers, height=100)

# Cấu hình chỉ báo
st.sidebar.subheader("Thiết lập chỉ báo")
ma_fast_len = st.sidebar.number_input("Đường xu hướng nhanh (MA Fast)", value=20)
ma_slow_len = st.sidebar.number_input("Đường xu hướng chậm (MA Slow)", value=50)
rsi_threshold = st.sidebar.slider("Ngưỡng RSI an toàn (Max)", 50, 90, 70)

# Cấu hình thanh khoản (QUAN TRỌNG)
st.sidebar.subheader("Bộ lọc thanh khoản")
min_vol_val = st.sidebar.number_input("GTGD tối thiểu (Tỷ VNĐ/phiên)", value=5.0)

# --- 3. HÀM XỬ LÝ DỮ LIỆU ---
@st.cache_data(ttl=3600) # Cache dữ liệu 1 tiếng để tránh spam API
def get_stock_data(symbol):
    """Lấy dữ liệu và tính toán chỉ báo"""
    try:
        # Tự động lấy ngày hiện tại và lùi về 1 năm trước
        end_date = datetime.now().strftime('%Y-%m-%d')
        start_date = (datetime.now() - timedelta(days=365)).strftime('%Y-%m-%d')
        
        df = stock_historical_data(symbol, start_date, end_date, "1D", "stock")
        
        if df is None or df.empty or len(df) < ma_slow_len + 5:
            return None
            
        # Chuẩn hóa tên cột (đề phòng vnstock trả về tên khác)
        df.columns = df.columns.str.lower() # chuyển hết về chữ thường
        
        # Tính toán chỉ báo
        df['ma_fast'] = ta.sma(df['close'], length=ma_fast_len)
        df['ma_slow'] = ta.sma(df['close'], length=ma_slow_len)
        df['rsi'] = ta.rsi(df['close'], length=14)
        
        # Tính giá trị giao dịch trung bình 20 phiên (Tỷ đồng)
        df['avg_val_20'] = (df['close'] * df['volume']).rolling(20).mean() / 1_000_000_000
        
        return df
    except Exception as e:
        # st.error(f"Lỗi tải {symbol}: {e}") # Bỏ comment nếu muốn debug
        return None

def check_signal(df, symbol):
    """Kiểm tra điều kiện Mua"""
    if df is None: return None
    
    curr = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Điều kiện thanh khoản (Tránh cổ phiếu rác)
    if curr['avg_val_20'] < min_vol_val:
        return None

    # 2. Xu hướng tăng: Giá > MA Fast > MA Slow
    trend_up = (curr['close'] > curr['ma_fast']) and (curr['ma_fast'] > curr['ma_slow'])
    
    # 3. Điểm mua:
    # Cách 1: Giá vừa cắt lên MA Fast
    cross_up = (prev['close'] < prev['ma_fast']) and (curr['close'] > curr['ma_fast'])
    # Cách 2: Giá test lại MA Fast và bật lên (Pullback)
    pullback = (curr['low'] <= curr['ma_fast'] * 1.02) and (curr['close'] > curr['ma_fast'])
    
    buy_signal = trend_up and (cross_up or pullback)
    
    # 4. RSI không quá nóng
    safe_rsi = curr['rsi'] < rsi_threshold
    
    if buy_signal and safe_rsi:
        return {
            "Mã CK": symbol,
            "Giá": curr['close'],
            f"MA{ma_fast_len}": round(curr['ma_fast'], 0),
            "RSI": round(curr['rsi'], 1),
            "GTGD TB (Tỷ)": round(curr['avg_val_20'], 2),
            "Khuyến nghị": "MUA 🟢"
        }
    return None

# --- 4. HÀM VẼ BIỂU ĐỒ ---
def plot_chart(df, symbol):
    """Vẽ biểu đồ nến + MA"""
    # Lấy 100 nến gần nhất để vẽ cho rõ
    plot_df = df.tail(100)
    
    fig = go.Figure()
    
    # Nến
    fig.add_trace(go.Candlestick(x=plot_df.index,
                    open=plot_df['open'], high=plot_df['high'],
                    low=plot_df['low'], close=plot_df['close'],
                    name='Giá'))
    
    # Đường MA
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['ma_fast'], 
                             line=dict(color='orange', width=1.5), name=f'MA{ma_fast_len}'))
    fig.add_trace(go.Scatter(x=plot_df.index, y=plot_df['ma_slow'], 
                             line=dict(color='blue', width=1.5), name=f'MA{ma_slow_len}'))
    
    fig.update_layout(title=f"Biểu đồ kỹ thuật {symbol}", 
                      xaxis_rangeslider_visible=False,
                      template="plotly_dark", height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. LOGIC CHẠY CHÍNH ---
if st.sidebar.button("QUÉT TÍN HIỆU NGAY 🔥", type="primary"):
    symbols_list = [x.strip().upper() for x in input_symbols.split(',') if x.strip()]
    
    results = []
    valid_dfs = {} # Lưu lại data để vẽ biểu đồ sau này
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(symbols_list):
        status_text.text(f"Đang phân tích: {sym}...")
        df = get_stock_data(sym)
        
        if df is not None:
            sig = check_signal(df, sym)
            if sig:
                results.append(sig)
                valid_dfs[sym] = df
        
        progress_bar.progress((i + 1) / len(symbols_list))
        
    progress_bar.empty()
    status_text.empty()
    
    # HIỂN THỊ KẾT QUẢ
    if results:
        st.success(f"🎉 Tìm thấy {len(results)} mã cổ phiếu tiềm năng!")
        
        # 1. Hiển thị bảng tổng hợp
        df_res = pd.DataFrame(results)
        st.dataframe(df_res.style.highlight_max(axis=0, color='green'), use_container_width=True)
        
        st.markdown("### 📊 Chi tiết biểu đồ")
        # 2. Tabs cho từng mã để xem biểu đồ
        tabs = st.tabs([x['Mã CK'] for x in results])
        for i, tab in enumerate(tabs):
            symbol = results[i]['Mã CK']
            with tab:
                st.write(f"Phân tích kỹ thuật mã **{symbol}**")
                plot_chart(valid_dfs[symbol], symbol)
                
    else:
        st.warning("Không tìm thấy mã nào thỏa mãn tiêu chí lọc hôm nay. Hãy thử nới lỏng điều kiện RSI hoặc MA.")
else:
    st.info("👈 Nhập danh sách mã bên trái và bấm nút Quét để bắt đầu.")
