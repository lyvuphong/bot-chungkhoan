import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="AI Stock Sniper (Real-Time)",
    layout="wide",
    page_icon="🔥",
    initial_sidebar_state="expanded"
)

# --- CSS GIAO DIỆN ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    div[data-testid="stMetric"] {
        background-color: white; border: 1px solid #ddd; padding: 10px; border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. HÀM XỬ LÝ DỮ LIỆU ---

# TÍNH NĂNG CACHING: Giúp app chạy nhanh, không tải lại dữ liệu cũ
@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_data_cached(symbol):
    try:
        # Tự động thêm đuôi .VN nếu thiếu
        if not symbol.endswith(".VN"): symbol += ".VN"
        
        # TÍNH NĂNG REAL-TIME DYNAMIC DATE:
        # Luôn lấy dữ liệu từ (Hôm nay - 365 ngày) đến (Hôm nay)
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Tải dữ liệu
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start_date, end=end_date)
        
        # TÍNH NĂNG ERROR HANDLING: Kiểm tra dữ liệu rỗng
        if df is None or df.empty or len(df) < 50:
            return None, None, "Dữ liệu không đủ hoặc mã sai."

        # Lấy Info cơ bản (P/E...) - Try catch để không crash nếu lỗi
        info = {}
        try: info = ticker.info
        except: pass

        return df, info, None
    except Exception as e:
        return None, None, str(e)

def analyze_stock(symbol, min_liquidity_billions):
    # 1. Tải dữ liệu
    df_raw, info, err = fetch_stock_data_cached(symbol)
    if err: return None, err
    
    try:
        df = df_raw.copy()
        
        # 2. TÍNH TOÁN THANH KHOẢN (GTGD)
        # Giá trị GD = Giá Đóng Cửa * Khối Lượng
        df['Turnover'] = df['Close'] * df['Volume']
        # GTGD Trung bình 20 phiên
        avg_val_20 = df['Turnover'].rolling(window=20).mean().iloc[-1]
        
        # TÍNH NĂNG BỘ LỌC THANH KHOẢN
        # Đổi 5 tỷ thành số thực: 5 * 10^9
        min_liquidity = min_liquidity_billions * 1_000_000_000
        if avg_val_20 < min_liquidity:
            return None, f"Thanh khoản thấp (< {min_liquidity_billions} tỷ)"

        # 3. Tính chỉ báo kỹ thuật
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        latest = df.iloc[-1]
        
        # 4. Chiến lược (Strategy)
        score = 0
        reasons = []
        
        # Trend
        if latest['Close'] > latest['SMA_20']: score += 20; reasons.append("Giá > MA20")
        if latest['SMA_20'] > latest['SMA_50']: score += 20; reasons.append("Uptrend (MA20 > MA50)")
        
        # Momentum
        if 50 <= latest['RSI'] <= 70: score += 15; reasons.append("RSI Khỏe")
        
        # Dòng tiền
        if latest['Volume'] > df['Volume'].tail(20).mean(): score += 20; reasons.append("Vol đột biến")
        
        # P/E
        pe = info.get('trailingPE', 0) if info else 0
        if pe and 5 < pe < 20: score += 15; reasons.append("P/E Tốt")

        # 5. Trade Plan
        support = df['Low'].tail(20).min()
        risk_pct = (latest['Close'] - support) / latest['Close']
        stop_loss = latest['Close'] * 0.93 if risk_pct > 0.07 else support
        take_profit = latest['Close'] + (latest['Close'] - stop_loss) * 2

        # Khuyến nghị
        rec = "THEO DÕI"
        if score >= 80: rec = "MUA MẠNH"
        elif score >= 60: rec = "MUA"

        return {
            "Symbol": symbol.replace(".VN", ""),
            "Price": latest['Close'],
            "Score": score,
            "Rec": rec,
            "Liquidity": avg_val_20 / 1_000_000_000, # Đổi ra Tỷ VNĐ
            "SL": stop_loss,
            "TP": take_profit,
            "Reasons": ", ".join(reasons),
            "DF": df
        }, None

    except Exception as e:
        return None, str(e)

# --- 3. VẼ BIỂU ĐỒ TƯƠNG TÁC (PLOTLY) ---
def plot_interactive_chart(data):
    df = data['DF']
    
    # Tạo biểu đồ 2 dòng (Giá ở trên, Vol ở dưới)
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, 
                        row_heights=[0.7, 0.3], vertical_spacing=0.03)

    # Nến Nhật (Candlestick)
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], 
        name='Giá'
    ), row=1, col=1)
    
    # Đường MA
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'), row=1, col=1)

    # Các đường Plan (TP/SL)
    fig.add_hline(y=data['Price'], line_dash="dot", line_color="gray", annotation_text="Entry", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", annotation_text="StopLoss", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="green", annotation_text="Target", row=1, col=1)

    # Volume (Màu xanh đỏ theo giá)
    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Volume'), row=2, col=1)

    # Tinh chỉnh giao diện
    fig.update_layout(
        title=f"Biểu đồ kỹ thuật: {data['Symbol']} (GTGD TB: {round(data['Liquidity'], 1)} Tỷ)",
        height=600,
        xaxis_rangeslider_visible=False, # Tắt thanh trượt dưới cùng cho gọn
        template="plotly_white",
        hovermode="x unified" # Rê chuột hiện thông tin cả 2 biểu đồ
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("🔥 AI STOCK SNIPER (DYNAMIC DATA)")
st.caption(f"Dữ liệu Real-time: {datetime.now().strftime('%d/%m/%Y')}")

# SIDEBAR
with st.sidebar:
    st.header("⚙️ CẤU HÌNH QUÉT")
    
    # Input mã
    default_symbols = "HPG, SSI, VND, FPT, VCB, MWG, NVL, DIG, CEO, PDR, VIX, SHS"
    txt_input = st.text_area("Nhập mã (cách nhau dấu phẩy):", default_symbols)
    
    # Slider lọc thanh khoản
    min_liq = st.slider("GTGD Trung bình tối thiểu (Tỷ VNĐ):", 0, 50, 5, help="Lọc bỏ các mã rác thanh khoản thấp dưới mức này")
    
    btn_scan = st.button("🚀 QUÉT TÍN HIỆU", type="primary")

# MAIN CONTENT
if btn_scan:
    symbols = [s.strip().upper() for s in txt_input.split(',')]
    
    st.toast(f"Đang xử lý {len(symbols)} mã...", icon="⏳")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(symbols):
        status_text.text(f"Đang phân tích: {sym}...")
        
        # Gọi hàm phân tích mới
        data, err = analyze_stock(sym, min_liq)
        
        if data:
            results.append(data)
        elif err and "Thanh khoản" in err:
            # Log nhẹ các mã bị loại do thanh khoản
            print(f"Bỏ qua {sym}: {err}")
            
        progress_bar.progress((i+1)/len(symbols))
        
    status_text.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.success(f"✅ Tìm thấy {len(df_res)} mã đạt chuẩn thanh khoản > {min_liq} tỷ.")
        
        # Bảng kết quả
        st.dataframe(
            df_res[['Symbol', 'Price', 'Score', 'Rec', 'Liquidity', 'SL', 'TP', 'Reasons']],
            use_container_width=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Điểm", max_value=100),
                "Price": st.column_config.NumberColumn("Giá", format="%d"),
                "Liquidity": st.column_config.NumberColumn("GTGD (Tỷ)", format="%.1f"),
                "SL": st.column_config.NumberColumn("Cắt Lỗ", format="%d"),
                "TP": st.column_config.NumberColumn("Chốt Lời", format="%d"),
            }
        )
        
        # Chart section
        st.divider()
        st.subheader("📈 Soi Biểu Đồ (Interactive)")
        
        selected_stock = st.selectbox("Chọn mã để xem chart:", df_res['Symbol'].tolist())
        item = next((x for x in results if x['Symbol'] == selected_stock), None)
        
        if item:
            plot_interactive_chart(item)
            
    else:
        st.warning(f"Không tìm thấy mã nào! (Có thể do thanh khoản < {min_liq} tỷ hoặc dữ liệu lỗi)")
