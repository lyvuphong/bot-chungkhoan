import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz # Thư viện xử lý múi giờ

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="AI Stock Sniper (Realtime Fix)",
    layout="wide",
    page_icon="⚡",
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

# --- 2. HÀM XỬ LÝ DỮ LIỆU CHUẨN XÁC ---

@st.cache_data(ttl=300, show_spinner=False) # Cache 5 phút
def fetch_stock_data_cached(symbol):
    try:
        if not symbol.endswith(".VN"): symbol += ".VN"
        
        # 1. Xử lý thời gian (Múi giờ VN)
        tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
        now = datetime.now(tz_vn)
        
        # Quan trọng: Cộng thêm 1 ngày cho end_date để yfinance lấy đủ dữ liệu hôm nay
        end_date = now + timedelta(days=1) 
        start_date = now - timedelta(days=365)
        
        ticker = yf.Ticker(symbol)
        
        # 2. Lấy dữ liệu lịch sử (1 Ngày)
        df = ticker.history(start=start_date, end=end_date, interval="1d")
        
        if df is None or df.empty:
            return None, None, "Không có dữ liệu."

        # 3. LẤY GIÁ REALTIME (FIX LỖI TRỄ GIÁ)
        # Yahoo nến ngày (1d) thường chậm update giá chốt phiên.
        # Ta lấy thêm nến phút (1m) của phiên hôm nay để lấy giá khớp gần nhất.
        try:
            df_intraday = ticker.history(period="1d", interval="1m")
            if not df_intraday.empty:
                latest_price = df_intraday['Close'].iloc[-1]
                # Cập nhật giá đóng cửa của ngày hôm nay trong bảng df chính
                df.iloc[-1, df.columns.get_loc('Close')] = latest_price
                # Cập nhật luôn High/Low nếu giá hiện tại vượt biên
                if latest_price > df.iloc[-1]['High']: df.iloc[-1, df.columns.get_loc('High')] = latest_price
                if latest_price < df.iloc[-1]['Low']: df.iloc[-1, df.columns.get_loc('Low')] = latest_price
        except:
            pass # Nếu lỗi lấy intraday thì dùng giá 1d tạm

        # Lấy Info
        info = {}
        try: info = ticker.info
        except: pass

        return df, info, None
    except Exception as e:
        return None, None, str(e)

def analyze_stock(symbol, min_liquidity_billions):
    df_raw, info, err = fetch_stock_data_cached(symbol)
    if err: return None, err
    
    try:
        df = df_raw.copy()
        
        # Tính thanh khoản
        df['Turnover'] = df['Close'] * df['Volume']
        avg_val_20 = df['Turnover'].rolling(window=20).mean().iloc[-1]
        
        min_liquidity = min_liquidity_billions * 1_000_000_000
        if avg_val_20 < min_liquidity:
            return None, f"Thanh khoản thấp (< {min_liquidity_billions} tỷ)"

        # Chỉ báo
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        latest = df.iloc[-1]
        
        # Strategy
        score = 0
        reasons = []
        
        if latest['Close'] > latest['SMA_20']: score += 20; reasons.append("Giá > MA20")
        if latest['SMA_20'] > latest['SMA_50']: score += 20; reasons.append("Uptrend")
        if 50 <= latest['RSI'] <= 70: score += 15; reasons.append("RSI Khỏe")
        if latest['Volume'] > df['Volume'].tail(20).mean(): score += 20; reasons.append("Vol đột biến")
        
        pe = info.get('trailingPE', 0) if info else 0
        if pe and 5 < pe < 20: score += 15; reasons.append("P/E Tốt")

        # Plan
        support = df['Low'].tail(20).min()
        risk_pct = (latest['Close'] - support) / latest['Close']
        stop_loss = latest['Close'] * 0.93 if risk_pct > 0.07 else support
        take_profit = latest['Close'] + (latest['Close'] - stop_loss) * 2

        rec = "THEO DÕI"
        if score >= 80: rec = "MUA MẠNH"
        elif score >= 60: rec = "MUA"

        return {
            "Symbol": symbol.replace(".VN", ""),
            "Price": latest['Close'],
            "Score": score,
            "Rec": rec,
            "Liquidity": avg_val_20 / 1_000_000_000,
            "SL": stop_loss,
            "TP": take_profit,
            "Reasons": ", ".join(reasons),
            "DF": df
        }, None

    except Exception as e:
        return None, str(e)

# --- 3. VẼ BIỂU ĐỒ ---
def plot_interactive_chart(data):
    df = data['DF']
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)

    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    
    fig.add_hline(y=data['Price'], line_dash="dot", line_color="gray", annotation_text=f"Current: {int(data['Price']):,}", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", annotation_text="SL", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="green", annotation_text="TP", row=1, col=1)

    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    fig.update_layout(title=f"Chart: {data['Symbol']} (Giá: {int(data['Price']):,} đ)", height=600, xaxis_rangeslider_visible=False, template="plotly_white")
    st.plotly_chart(fig, use_container_width=True)

# --- 4. GIAO DIỆN CHÍNH ---
st.title("⚡ AI STOCK SNIPER (REAL-TIME)")
st.caption(f"Cập nhật lúc: {datetime.now().strftime('%H:%M %d/%m/%Y')}")

with st.sidebar:
    st.header("⚙️ CẤU HÌNH")
    default_symbols = "HPG, SSI, VND, FPT, VCB, MWG, NVL, DIG, CEO, PDR, VIX, SHS, STB"
    txt_input = st.text_area("Nhập mã:", default_symbols)
    min_liq = st.slider("Thanh khoản tối thiểu (Tỷ):", 0, 50, 5)
    btn_scan = st.button("🚀 QUÉT GIÁ MỚI NHẤT", type="primary")

if btn_scan:
    symbols = [s.strip().upper() for s in txt_input.split(',')]
    st.toast(f"Đang lấy dữ liệu mới nhất cho {len(symbols)} mã...", icon="🔄")
    
    results = []
    progress_bar = st.progress(0)
    
    for i, sym in enumerate(symbols):
        data, err = analyze_stock(sym, min_liq)
        if data: results.append(data)
        progress_bar.progress((i+1)/len(symbols))
        
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Score", ascending=False)
        st.success(f"Đã cập nhật dữ liệu mới nhất!")
        
        st.dataframe(
            df_res[['Symbol', 'Price', 'Score', 'Rec', 'Liquidity', 'SL', 'TP', 'Reasons']],
            use_container_width=True,
            column_config={
                "Score": st.column_config.ProgressColumn("Điểm", max_value=100),
                "Price": st.column_config.NumberColumn("Giá (Realtime)", format="%d"),
                "Liquidity": st.column_config.NumberColumn("GTGD (Tỷ)", format="%.1f"),
                "SL": st.column_config.NumberColumn("Cắt Lỗ", format="%d"),
                "TP": st.column_config.NumberColumn("Chốt Lời", format="%d"),
            }
        )
        
        st.divider()
        selected_stock = st.selectbox("Xem biểu đồ chi tiết:", df_res['Symbol'].tolist())
        item = next((x for x in results if x['Symbol'] == selected_stock), None)
        if item: plot_interactive_chart(item)
    else:
        st.warning("Không tìm thấy mã nào.")
