import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Vũ Phong Alpha Trader v2.1", page_icon="🦅", layout="wide")

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
    except Exception:
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
    """Tính điểm RS (Relative Strength)"""
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
        
        # Trọng số: 40% (6M) + 40% (3M) + 20% (1M)
        raw_rs = (rs_6m * 0.4) + (rs_3m * 0.4) + (rs_1m * 0.2)
        return raw_rs * 100 
    except:
        return -999

def calculate_proprietary_score(df, rs_score):
    """
    Tính điểm sức mạnh tổng hợp (Thang điểm 100)
    """
    score = 0
    close = df['close']
    ema50 = df['ema50']
    ema200 = df['ema200']
    rsi = df['rsi']
    vol = df['volume']
    
    current_price = close.iloc[-1]
    
    # 1. TREND (Max 40 điểm)
    if current_price > ema50.iloc[-1]: score += 15
    if ema50.iloc[-1] > ema200.iloc[-1]: score += 15
    if current_price > ema200.iloc[-1]: score += 10
    
    # 2. RS - SỨC MẠNH (Max 40 điểm)
    if rs_score > 0: score += 20 # Mạnh hơn thị trường
    if rs_score > 10: score += 20 # Siêu mạnh
    
    # 3. MOMENTUM & VOL (Max 20 điểm)
    c_rsi = rsi.iloc[-1]
    if 50 <= c_rsi <= 70: score += 10 # Vùng RSI đẹp nhất
    
    avg_vol = vol.rolling(20).mean().iloc[-1]
    if vol.iloc[-1] > avg_vol: score += 10 # Có dòng tiền vào
    
    return min(100, score)

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
        
        # Lọc thanh khoản < 5 tỷ
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        avg_value_20 = avg_vol_20 * current_price
        if avg_value_20 < 5_000_000_000: return None

        # Tính chỉ báo
        df['ema50'] = EMAIndicator(close=close, window=50).ema_indicator()
        df['ema150'] = EMAIndicator(close=close, window=150).ema_indicator()
        df['ema200'] = EMAIndicator(close=close, window=200).ema_indicator()
        df['rsi'] = RSIIndicator(close=close, window=14).rsi()
        
        c_ema50 = df['ema50'].iloc[-1]
        c_ema150 = df['ema150'].iloc[-1]
        c_ema200 = df['ema200'].iloc[-1]
        c_rsi = df['rsi'].iloc[-1]
        
        rs_score = calculate_rs_score(close, vnindex_series)
        
        # Trend Mark Minervini
        trend_ok = (current_price > c_ema50) and (c_ema50 > c_ema150) and (c_ema150 > c_ema200)
        rs_ok = rs_score > 0
        
        # --- TÍNH ĐIỂM SỨC MẠNH (NEW) ---
        power_score = calculate_proprietary_score(df, rs_score)
        
        # --- LẬP KẾ HOẠCH GIAO DỊCH (NEW) ---
        # Chỉ lập kế hoạch nếu Trend OK hoặc RS OK
        take_profit = 0
        stop_loss = 0
        
        if trend_ok or rs_ok:
            stop_loss = current_price * 0.93 # Cắt lỗ 7%
            take_profit = current_price * 1.20 # Chốt lời 20%

        # Logic Khuyến nghị
        status = "⚪ Theo dõi"
        if power_score >= 80: status = "💎 MUA MẠNH"
        elif power_score >= 60: status = "🟢 MUA"
        elif power_score >= 40: status = "🟡 Giữ"
        else: status = "🔴 Bán/Né"

        # Chỉ trả về nếu cổ phiếu ổn
        if trend_ok or rs_ok:
            return {
                'Mã': ticker.replace('.VN', ''),
                'Giá': current_price,
                'Điểm Sức Mạnh': int(power_score), # Cột mới
                'Vùng Mua': current_price, # Cột mới
                'Cắt Lỗ (-7%)': stop_loss, # Cột mới
                'Mục Tiêu (+20%)': take_profit, # Cột mới
                'RS Rating': rs_score,
                'Thanh khoản': avg_value_20 / 1e9,
                'RSI': c_rsi,
                'Khuyến Nghị': status,
                '_sort_score': power_score # Sort theo điểm sức mạnh
            }
        return None
        
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---

st.title("🦅 Vũ Phong Alpha Trader v2.1")
st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 20px; }
</style>
**Nguyên tắc:** Mua cổ phiếu điểm cao, Cắt lỗ quyết liệt (-7%), Gồng lãi tới mục tiêu (+20%).
""", unsafe_allow_html=True)

# --- SIDEBAR ---
with st.sidebar:
    st.header("⚙️ Bộ Lọc")
    selected_sector = st.selectbox("Chọn Ngành", list(SECTORS.keys()))
    min_rs = st.slider("RS Rating tối thiểu", -10.0, 50.0, 0.0, step=1.0)
    st.markdown("---")
    start_scan = st.button("🔍 Quét & Lập Kế Hoạch", type="primary")
    st.caption("Data: Yahoo Finance (15m delay)")

# --- MAIN AREA ---
if start_scan:
    with st.spinner(f"Đang chấm điểm sức mạnh nhóm {selected_sector}..."):
        vnindex = get_vnindex_data()
        
        if vnindex is not None:
            tickers = SECTORS[selected_sector]
            raw_data = get_stock_batch(tickers)
            
            results = []
            if raw_data is not None:
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
                
                # HIỂN THỊ KẾT QUẢ
                if results:
                    df_res = pd.DataFrame(results)
                    # Sort theo Điểm sức mạnh
                    df_res = df_res.sort_values(by='_sort_score', ascending=False).drop(columns=['_sort_score'])
                    
                    st.success(f"Tìm thấy {len(df_res)} mã tiềm năng. Đã lập kế hoạch giao dịch chi tiết!")
                    
                    # FORMAT BẢNG NÂNG CAO
                    st.dataframe(
                        df_res.style.format({
                            'Giá': '{:,.0f}',
                            'Vùng Mua': '{:,.0f}',
                            'Cắt Lỗ (-7%)': '{:,.0f}',
                            'Mục Tiêu (+20%)': '{:,.0f}',
                            'Thanh khoản': '{:.1f} tỷ',
                            'RS Rating': '{:+.2f}',
                            'RSI': '{:.0f}'
                        })
                        .background_gradient(subset=['Điểm Sức Mạnh'], cmap='RdYlGn', vmin=40, vmax=100)
                        .background_gradient(subset=['RS Rating'], cmap='Greens')
                        .applymap(lambda v: 'color: red; font-weight: bold;' if v < 0 else '', subset=['RS Rating'])
                        .applymap(lambda v: 'color: green; font-weight: bold;' if 'MUA' in str(v) else '', subset=['Khuyến Nghị']),
                        use_container_width=True,
                        height=600
                    )
                    
                    # CHART
                    st.markdown("### 📊 Biểu đồ Kỹ thuật")
                    if not df_res.empty:
                        col_chart, col_info = st.columns([3, 1])
                        with col_info:
                            chart_ticker = st.radio("Chọn mã:", df_res['Mã'].tolist())
                            # Hiển thị nhanh Trading Plan bên cạnh chart
                            sel_row = df_res[df_res['Mã'] == chart_ticker].iloc[0]
                            st.info(f"""
                            **Kế hoạch {chart_ticker}:**
                            \n🎯 **Mục tiêu:** {sel_row['Mục Tiêu (+20%)']:,.0f}
                            \n🛑 **Cắt lỗ:** {sel_row['Cắt Lỗ (-7%)']:,.0f}
                            \n💪 **Sức mạnh:** {sel_row['Điểm Sức Mạnh']}/100
                            """)
                        
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
                                
                                fig.update_layout(title=f"{chart_ticker} - Trend & Trading Plan", xaxis_rangeslider_visible=False, height=500, template="plotly_dark")
                                st.plotly_chart(fig, use_container_width=True)
                            except: pass
                else:
                    st.warning("Không tìm thấy mã phù hợp.")
            else:
                st.error("Lỗi dữ liệu.")
        else:
            st.error("Lỗi VNINDEX.")
