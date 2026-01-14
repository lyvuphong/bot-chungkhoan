import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Vũ Phong Alpha Trader v2.0", page_icon="📈", layout="wide")

# --- DANH MỤC CỔ PHIẾU (DATA SECTOR) ---
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

@st.cache_data(ttl=3600)
def get_vnindex_data():
    """Tải dữ liệu VN-INDEX"""
    try:
        vnindex = yf.download("^VNINDEX", period="1y", interval="1d", progress=False)
        if isinstance(vnindex.columns, pd.MultiIndex):
            vnindex = vnindex.xs('^VNINDEX', axis=1, level=1) if '^VNINDEX' in vnindex.columns.levels[1] else vnindex
            if isinstance(vnindex.columns, pd.MultiIndex):
                vnindex.columns = vnindex.columns.get_level_values(0)
        vnindex.columns = [c.lower() for c in vnindex.columns]
        return vnindex['close']
    except Exception as e:
        return None

@st.cache_data(ttl=900)
def get_stock_batch(ticker_list):
    """Tải dữ liệu batch cổ phiếu"""
    symbols = [f"{t}.VN" for t in ticker_list]
    try:
        data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        return data
    except Exception:
        return None

def calculate_rs_score(stock_close, market_close):
    try:
        common_index = stock_close.index.intersection(market_close.index)
        s = stock_close.loc[common_index]
        m = market_close.loc[common_index]
        if len(s) < 130: return 0
        
        s_1m = (s.iloc[-1] / s.iloc[-21]) - 1
        m_1m = (m.iloc[-1] / m.iloc[-21]) - 1
        rs_1m = s_1m - m_1m
        
        s_3m = (s.iloc[-1] / s.iloc[-63]) - 1
        m_3m = (m.iloc[-1] / m.iloc[-63]) - 1
        rs_3m = s_3m - m_3m
        
        s_6m = (s.iloc[-1] / s.iloc[-126]) - 1
        m_6m = (m.iloc[-1] / m.iloc[-126]) - 1
        rs_6m = s_6m - m_6m
        
        raw_rs = (rs_6m * 0.4) + (rs_3m * 0.4) + (rs_1m * 0.2)
        return raw_rs * 100 
    except:
        return -999

def analyze_ticker_pro(ticker, df_input, vnindex_series):
    try:
        df = df_input.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if len(df) < 200: return None
        
        close = df['close']
        volume = df['volume']
        current_price = close.iloc[-1]
        
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        avg_value_20 = avg_vol_20 * current_price
        
        if avg_value_20 < 5_000_000_000: return None

        ema50 = EMAIndicator(close=close, window=50).ema_indicator()
        ema150 = EMAIndicator(close=close, window=150).ema_indicator()
        ema200 = EMAIndicator(close=close, window=200).ema_indicator()
        rsi = RSIIndicator(close=close, window=14).rsi()
        
        c_ema50 = ema50.iloc[-1]
        c_ema150 = ema150.iloc[-1]
        c_ema200 = ema200.iloc[-1]
        c_rsi = rsi.iloc[-1]
        
        rs_score = calculate_rs_score(close, vnindex_series)
        
        trend_ok = (current_price > c_ema50) and (c_ema50 > c_ema150) and (c_ema150 > c_ema200)
        rs_ok = rs_score > 0
        
        status = "⚪ Theo dõi"
        
        if trend_ok and rs_ok:
            if 50 <= c_rsi <= 70:
                status = "💎 MUA (Strong)"
            elif c_rsi < 50:
                status = "🟢 MUA (Tích lũy)"
            else:
                status = "🟡 Giữ (Hold)"
        elif not trend_ok and rs_ok:
            status = "⚠️ Cảnh báo"
        elif trend_ok and not rs_ok:
             status = "🐢 Yếu hơn TT"
        
        if trend_ok or rs_ok:
            return {
                'Mã': ticker.replace('.VN', ''),
                'Giá': current_price,
                'Thay đổi': ((current_price - close.iloc[-2])/close.iloc[-2]) * 100,
                'RS Rating': rs_score,
                'Thanh khoản (Tỷ)': avg_value_20 / 1e9,
                'RSI': c_rsi,
                'Trend': 'Tăng 📈' if trend_ok else 'Chỉnh 📉',
                'Khuyến Nghị': status,
                '_sort_score': rs_score if trend_ok else -999
            }
        return None
        
    except Exception as e:
        return None

# --- GIAO DIỆN CHÍNH (MAIN LAYOUT) ---

st.title("🦅 Vũ Phong Alpha Trader v2.0")
st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 20px; }
</style>
**Triết lý đầu tư:** Chỉ mua cổ phiếu có *Xu hướng tăng*, *Thanh khoản cao* và *Mạnh hơn VN-INDEX*.
""", unsafe_allow_html=True)

# --- SIDEBAR (CHỈ CHỨA INPUT) ---
with st.sidebar:
    st.header("⚙️ Bộ Lọc")
    selected_sector = st.selectbox("Chọn Ngành", list(SECTORS.keys()))
    min_rs = st.slider("RS Rating tối thiểu", -10.0, 50.0, 0.0, step=1.0)
    st.markdown("---")
    # Nút bấm nằm ở Sidebar, nhưng kết quả sẽ trả về biến start_scan
    start_scan = st.button("🔍 Quét Thị Trường", type="primary")
    st.caption("Dữ liệu Yahoo Finance (Delay 15p).")

# --- MAIN AREA (HIỂN THỊ KẾT QUẢ) ---
# Logic này nằm NGOÀI khối 'with st.sidebar' nên sẽ hiện ở giữa màn hình
if start_scan:
    with st.spinner(f"Đang phân tích dữ liệu ngành {selected_sector}..."):
        # 1. Tải VNINDEX
        vnindex = get_vnindex_data()
        
        if vnindex is not None:
            # 2. Tải Cổ phiếu
            tickers = SECTORS[selected_sector]
            raw_data = get_stock_batch(tickers)
            
            results = []
            if raw_data is not None:
                # Progress bar hiện ở Main Area
                bar = st.progress(0)
                for i, t in enumerate(tickers):
                    bar.progress((i+1)/len(tickers))
                    try:
                        df_single = raw_data[f"{t}.VN"] if f"{t}.VN" in raw_data.columns.levels[0] else None
                        if df_single is None and len(tickers) == 1: df_single = raw_data
                        
                        if df_single is not None:
                            res = analyze_ticker_pro(t, df_single, vnindex)
                            if res and res['RS Rating'] >= min_rs:
                                results.append(res)
                    except: continue
                bar.empty()
                
                # 3. HIỂN THỊ KẾT QUẢ
                if results:
                    df_res = pd.DataFrame(results)
                    df_res = df_res.sort_values(by='_sort_score', ascending=False).drop(columns=['_sort_score'])
                    
                    st.success(f"Tìm thấy {len(df_res)} mã tiềm năng!")
                    
                    # BẢNG KẾT QUẢ (Main Area)
                    st.dataframe(
                        df_res.style.format({
                            'Giá': '{:,.0f}',
                            'Thanh khoản (Tỷ)': '{:.1f} tỷ',
                            'RS Rating': '{:+.2f}%',
                            'RSI': '{:.1f}',
                            'Thay đổi': '{:+.2f}%'
                        })
                        .background_gradient(subset=['RS Rating'], cmap='Greens')
                        .background_gradient(subset=['Thay đổi'], cmap='RdYlGn')
                        .applymap(lambda v: 'color: green; font-weight: bold;' if 'MUA' in str(v) else '', subset=['Khuyến Nghị']),
                        use_container_width=True,
                        height=600
                    )
                    
                    # CHART CHI TIẾT (Main Area)
                    st.markdown("### 📊 Phân tích Chi tiết")
                    if not df_res.empty:
                        col_chart, col_info = st.columns([3, 1])
                        
                        with col_info:
                            chart_ticker = st.radio("Chọn mã xem chart:", df_res['Mã'].tolist())
                        
                        with col_chart:
                            try:
                                df_chart = raw_data[f"{chart_ticker}.VN"].copy()
                                df_chart['EMA50'] = EMAIndicator(close=df_chart['Close'], window=50).ema_indicator()
                                df_chart['EMA200'] = EMAIndicator(close=df_chart['Close'], window=200).ema_indicator()
                                
                                fig = go.Figure()
                                fig.add_trace(go.Candlestick(x=df_chart.index,
                                                open=df_chart['Open'], high=df_chart['High'],
                                                low=df_chart['Low'], close=df_chart['Close'], name='Giá'))
                                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA50'], 
                                                            line=dict(color='orange', width=1.5), name='EMA 50'))
                                fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA200'], 
                                                            line=dict(color='blue', width=2), name='EMA 200'))
                                
                                fig.update_layout(
                                    title=f"Biểu đồ {chart_ticker}",
                                    xaxis_rangeslider_visible=False,
                                    height=500,
                                    template="plotly_dark"
                                )
                                st.plotly_chart(fig, use_container_width=True)
                            except:
                                st.error("Không vẽ được biểu đồ.")
                else:
                    st.warning("Không tìm thấy mã nào đủ tiêu chuẩn (Trend Tăng + RS Tốt + Thanh Khoản).")
            else:
                st.error("Lỗi kết nối dữ liệu cổ phiếu.")
        else:
            st.error("Không lấy được dữ liệu VN-INDEX.")
