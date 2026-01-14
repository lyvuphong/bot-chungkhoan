import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Vũ Phong Alpha Trader v2.4 (Fail-Safe)", page_icon="🦅", layout="wide")

# --- DANH MỤC CỔ PHIẾU ---
SECTORS = {
    "💎 Bluechips (VN30)": ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
    "🏦 Ngân Hàng": ['VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'HDB', 'VIB', 'SHB', 'LPB', 'MSB', 'OCB', 'TPB', 'EIB'],
    "⚡ Chứng Khoán": ['SSI', 'VND', 'VCI', 'HCM', 'SHS', 'MBS', 'FTS', 'BSI', 'CTS', 'AGR', 'VIX', 'ORS'],
    "🏗 Bất Động Sản & KCN": ['VHM', 'NVL', 'PDR', 'DIG', 'DXG', 'CEO', 'KDH', 'NLG', 'KBC', 'IDC', 'VGC', 'SZC', 'BCM', 'GVR'],
    "🛢 Dầu Khí & Năng Lượng": ['GAS', 'PVD', 'PVS', 'PVT', 'PLX', 'BSR', 'POW', 'REE', 'PC1', 'GEG'],
    "📦 Bán Lẻ & SX": ['MWG', 'MSN', 'PNJ', 'DGW', 'FRT', 'VNM', 'SAB', 'DGC', 'HPG', 'HSG', 'NKG'],
    "🍤 Thủy Sản & Dệt May": ['VHC', 'ANV', 'IDI', 'TNG', 'GIL', 'MSH', 'STK'],
    "🚀 Top Tăng Trưởng (Midcaps)": ['FPT', 'DGC', 'GMD', 'REE', 'VHC', 'ANV', 'HAH', 'DGW', 'FRT', 'CTR', 'VGI']
}

# --- HÀM XỬ LÝ DỮ LIỆU ---

@st.cache_data(ttl=600)
def get_vnindex_data():
    """Tải VN-INDEX an toàn - Trả về None nếu lỗi"""
    try:
        # Thử tải VNINDEX
        df = yf.download("^VNINDEX", period="1y", interval="1d", progress=False)
        
        # Kiểm tra rỗng
        if df is None or df.empty:
            return None
            
        # Xử lý MultiIndex
        if isinstance(df.columns, pd.MultiIndex):
            try:
                df = df.xs('^VNINDEX', axis=1, level=1)
            except: pass
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
                
        df.columns = [c.lower() for c in df.columns]
        
        # Kiểm tra lại lần cuối
        if 'close' not in df.columns or len(df) < 10:
            return None
            
        return df
    except:
        return None

@st.cache_data(ttl=900)
def get_stock_batch(ticker_list):
    symbols = [f"{t}.VN" for t in ticker_list]
    try:
        data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        if data is None or data.empty: return None
        return data
    except: return None

def calculate_rs_score(stock_close, market_close):
    """Tính RS Rating. Trả về 0 nếu không có dữ liệu Market"""
    if market_close is None or market_close.empty:
        return 0 # Fail-safe value
        
    try:
        common = stock_close.index.intersection(market_close.index)
        if len(common) < 130: return 0
        
        s = stock_close.loc[common]
        m = market_close.loc[common]
        
        s_1m = (s.iloc[-1] / s.iloc[-21]) - 1
        m_1m = (m.iloc[-1] / m.iloc[-21]) - 1
        
        s_3m = (s.iloc[-1] / s.iloc[-63]) - 1
        m_3m = (m.iloc[-1] / m.iloc[-63]) - 1
        
        s_6m = (s.iloc[-1] / s.iloc[-126]) - 1
        m_6m = (m.iloc[-1] / m.iloc[-126]) - 1
        
        rs = ((s_6m - m_6m) * 0.4) + ((s_3m - m_3m) * 0.4) + ((s_1m - m_1m) * 0.2)
        return rs * 100
    except:
        return 0

def calculate_proprietary_score(df, rs_score):
    """Tính điểm sức mạnh"""
    try:
        score = 0
        close = df['close']
        ema50 = df['ema50']
        ema200 = df['ema200']
        
        current_price = close.iloc[-1]
        
        # 1. Trend (Max 50)
        if current_price > ema50.iloc[-1]: score += 20
        if ema50.iloc[-1] > ema200.iloc[-1]: score += 20
        if current_price > ema200.iloc[-1]: score += 10
        
        # 2. RS (Max 30)
        # Nếu RS = 0 (do lỗi mạng), điểm này mất -> Score sẽ thấp hơn nhưng vẫn lọc được
        if rs_score > 0: score += 15
        if rs_score > 10: score += 15
        
        # 3. Momentum (Max 20)
        rsi = df['rsi'].iloc[-1]
        if 50 <= rsi <= 70: score += 10
        if df['volume'].iloc[-1] > df['volume'].rolling(20).mean().iloc[-1]: score += 10
        
        return min(100, score)
    except: return 0

def analyze_ticker_pro(ticker, df_input, vnindex_series):
    try:
        df = df_input.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if len(df) < 150: return None
        
        close = df['close']
        volume = df['volume']
        current_price = close.iloc[-1]
        
        # Lọc thanh khoản
        avg_value = (volume.rolling(20).mean().iloc[-1] * current_price)
        if avg_value < 5_000_000_000: return None # < 5 tỷ bỏ qua

        # Chỉ báo
        df['ema50'] = EMAIndicator(close=close, window=50).ema_indicator()
        df['ema150'] = EMAIndicator(close=close, window=150).ema_indicator()
        df['ema200'] = EMAIndicator(close=close, window=200).ema_indicator()
        df['rsi'] = RSIIndicator(close=close, window=14).rsi()
        
        # RS Score (Nếu vnindex_series là None thì rs_score = 0)
        rs_score = calculate_rs_score(close, vnindex_series)
        
        # Proprietary Score
        power_score = calculate_proprietary_score(df, rs_score)
        
        # Logic đánh giá
        c_ema50 = df['ema50'].iloc[-1]
        trend_ok = current_price > c_ema50
        
        # Kế hoạch GD
        stop_loss = current_price * 0.93
        take_profit = current_price * 1.20
        
        # Khuyến nghị
        status = "⚪ Theo dõi"
        if power_score >= 80: status = "💎 MUA MẠNH"
        elif power_score >= 60: status = "🟢 MUA"
        elif power_score >= 40: status = "🟡 Giữ"
        else: status = "🔴 Yếu"

        # TRẢ VỀ KẾT QUẢ KỂ CẢ KHI KHÔNG CÓ RS (Miễn là Trend OK)
        if trend_ok or power_score >= 40:
            return {
                'Mã': ticker.replace('.VN', ''),
                'Giá': current_price,
                'Điểm': int(power_score),
                'Vùng Mua': current_price,
                'Cắt Lỗ': stop_loss,
                'Mục Tiêu': take_profit,
                'RS Rating': rs_score if vnindex_series is not None else -999, # -999 để đánh dấu
                'RSI': df['rsi'].iloc[-1],
                'Khuyến Nghị': status,
                '_sort': power_score
            }
        return None
    except: return None

# --- UI CHÍNH ---
st.title("🦅 Vũ Phong Alpha Trader v2.4")
st.markdown("**Trạng thái:** Hệ thống đã kích hoạt chế độ *Fail-Safe* (Chống crash khi mất dữ liệu VN-INDEX).")

tab1, tab2 = st.tabs(["📊 Bộ Lọc Cổ Phiếu", "📝 Báo Cáo Thị Trường"])

# --- TAB 1 ---
with tab1:
    col1, col2 = st.columns([1, 4])
    with col1:
        sector = st.selectbox("Chọn Ngành", list(SECTORS.keys()))
        btn_scan = st.button("🔍 Quét Ngay", type="primary")
    
    with col2:
        if btn_scan:
            with st.spinner("Đang xử lý dữ liệu..."):
                # 1. Thử lấy VNINDEX
                vni_df = get_vnindex_data()
                vni_series = vni_df['close'] if vni_df is not None else None
                
                if vni_series is None:
                    st.warning("⚠️ Không lấy được dữ liệu VN-INDEX (Yahoo API Lỗi). Hệ thống sẽ lọc theo Xu hướng & Dòng tiền (Bỏ qua tiêu chí RS).")
                
                # 2. Lấy Data Cổ phiếu
                tickers = SECTORS[sector]
                raw_data = get_stock_batch(tickers)
                
                if raw_data is not None:
                    results = []
                    bar = st.progress(0)
                    for i, t in enumerate(tickers):
                        bar.progress((i+1)/len(tickers))
                        try:
                            df_s = raw_data[f"{t}.VN"] if f"{t}.VN" in raw_data.columns.levels[0] else None
                            if df_s is None and len(tickers) == 1: df_s = raw_data
                            
                            if df_s is not None:
                                res = analyze_ticker_pro(t, df_s, vni_series)
                                if res: results.append(res)
                        except: continue
                    bar.empty()
                    
                    if results:
                        df_res = pd.DataFrame(results).sort_values(by='_sort', ascending=False)
                        
                        # Hiển thị
                        st.dataframe(
                            df_res.style.format({
                                'Giá': '{:,.0f}', 'Vùng Mua': '{:,.0f}', 'Cắt Lỗ': '{:,.0f}', 'Mục Tiêu': '{:,.0f}',
                                'RS Rating': '{:.2f}', 'RSI': '{:.1f}'
                            })
                            .background_gradient(subset=['Điểm'], cmap='RdYlGn', vmin=40, vmax=100)
                            .applymap(lambda x: 'color: transparent' if x == -999 else '', subset=['RS Rating']),
                            use_container_width=True, height=500
                        )
                        
                        # Chart
                        try:
                            pick = st.selectbox("Chọn mã xem chart:", df_res['Mã'].tolist())
                            df_c = raw_data[f"{pick}.VN"].copy()
                            df_c['EMA50'] = EMAIndicator(close=df_c['Close'], window=50).ema_indicator()
                            fig = go.Figure()
                            fig.add_trace(go.Candlestick(x=df_c.index, open=df_c['Open'], high=df_c['High'], low=df_c['Low'], close=df_c['Close'], name='Giá'))
                            fig.add_trace(go.Scatter(x=df_c.index, y=df_c['EMA50'], line=dict(color='orange'), name='EMA50'))
                            fig.update_layout(title=f"{pick} Chart", template="plotly_dark", height=400, xaxis_rangeslider_visible=False)
                            st.plotly_chart(fig, use_container_width=True)
                        except: pass
                    else: st.info("Không tìm thấy mã tiềm năng.")
                else: st.error("Lỗi kết nối dữ liệu cổ phiếu.")

# --- TAB 2 (FIXED CRASH) ---
with tab2:
    if st.button("Kiểm tra Sức khỏe Thị trường"):
        vni = get_vnindex_data()
        
        # --- FIX QUAN TRỌNG: Kiểm tra độ dài trước khi iloc ---
        if vni is not None and len(vni) > 50:
            try:
                # Tính toán
                vni['EMA50'] = EMAIndicator(close=vni['close'], window=50).ema_indicator()
                vni['RSI'] = RSIIndicator(close=vni['close'], window=14).rsi()
                
                last = vni.iloc[-1]
                prev = vni.iloc[-2]
                
                trend_msg = "TĂNG (Uptrend)" if last['close'] > last['EMA50'] else "GIẢM (Downtrend)"
                color = "green" if last['close'] > last['EMA50'] else "red"
                
                c1, c2 = st.columns(2)
                c1.metric("VN-INDEX", f"{last['close']:,.2f}", f"{last['close']-prev['close']:.2f}")
                c2.markdown(f"### Xu hướng: :{color}[{trend_msg}]")
                
                # Vẽ chart
                fig = go.Figure()
                fig.add_trace(go.Candlestick(x=vni.index, open=vni['open'], high=vni['high'], low=vni['low'], close=vni['close']))
                fig.add_trace(go.Scatter(x=vni.index, y=vni['EMA50'], line=dict(color='orange'), name='EMA50'))
                st.plotly_chart(fig, use_container_width=True)
                
            except Exception as e:
                st.error(f"Lỗi tính toán chỉ số: {str(e)}")
        else:
            st.warning("⚠️ Hiện tại Yahoo Finance không trả về dữ liệu VN-INDEX. Vui lòng thử lại sau 15 phút hoặc xem bảng giá công ty chứng khoán.")
