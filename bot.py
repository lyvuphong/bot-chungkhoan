import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator
import plotly.graph_objects as go
from datetime import datetime

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Vũ Phong Alpha Trader v2.3", page_icon="🦅", layout="wide")

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
    """Tải dữ liệu VN-INDEX (Đã vá lỗi trả về rỗng)"""
    try:
        # Tải dữ liệu VNINDEX
        vnindex = yf.download("^VNINDEX", period="1y", interval="1d", progress=False)
        
        # Kiểm tra nếu dữ liệu rỗng thì trả về None ngay
        if vnindex is None or vnindex.empty:
            return None

        # Xử lý MultiIndex (Do cập nhật mới của yfinance)
        if isinstance(vnindex.columns, pd.MultiIndex):
            # Cố gắng lấy level Ticker nếu có
            try:
                vnindex = vnindex.xs('^VNINDEX', axis=1, level=1)
            except KeyError:
                pass # Nếu không có level 1 thì giữ nguyên
            
            # Nếu vẫn còn MultiIndex, flatten nó
            if isinstance(vnindex.columns, pd.MultiIndex):
                vnindex.columns = vnindex.columns.get_level_values(0)
        
        # Chuẩn hóa tên cột về chữ thường
        vnindex.columns = [c.lower() for c in vnindex.columns]
        
        # Kiểm tra lại lần cuối xem có cột 'close' không
        if 'close' not in vnindex.columns:
            return None
            
        return vnindex
    except Exception as e:
        print(f"Lỗi tải VNINDEX: {e}")
        return None

@st.cache_data(ttl=900)
def get_stock_batch(ticker_list):
    """Tải dữ liệu batch cổ phiếu"""
    symbols = [f"{t}.VN" for t in ticker_list]
    try:
        data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        if data is None or data.empty:
            return None
        return data
    except Exception:
        return None

def calculate_rs_score(stock_close, market_close):
    """Tính điểm RS"""
    try:
        common_index = stock_close.index.intersection(market_close.index)
        s = stock_close.loc[common_index]
        m = market_close.loc[common_index]
        if len(s) < 130: return 0
        
        s_1m = (s.iloc[-1] / s.iloc[-21]) - 1
        m_1m = (m.iloc[-1] / m.iloc[-21]) - 1
        
        s_3m = (s.iloc[-1] / s.iloc[-63]) - 1
        m_3m = (m.iloc[-1] / m.iloc[-63]) - 1
        
        s_6m = (s.iloc[-1] / s.iloc[-126]) - 1
        m_6m = (m.iloc[-1] / m.iloc[-126]) - 1
        
        rs_score = ((s_6m - m_6m) * 0.4) + ((s_3m - m_3m) * 0.4) + ((s_1m - m_1m) * 0.2)
        return rs_score * 100 
    except:
        return -999

def calculate_proprietary_score(df, rs_score):
    """Tính điểm sức mạnh tổng hợp"""
    try:
        score = 0
        close = df['close']
        ema50 = df['ema50']
        ema200 = df['ema200']
        rsi = df['rsi']
        vol = df['volume']
        
        current_price = close.iloc[-1]
        
        # 1. TREND
        if current_price > ema50.iloc[-1]: score += 15
        if ema50.iloc[-1] > ema200.iloc[-1]: score += 15
        if current_price > ema200.iloc[-1]: score += 10
        
        # 2. RS
        if rs_score > 0: score += 20
        if rs_score > 10: score += 20
        
        # 3. MOMENTUM
        c_rsi = rsi.iloc[-1]
        if 50 <= c_rsi <= 70: score += 10
        
        avg_vol = vol.rolling(20).mean().iloc[-1]
        if vol.iloc[-1] > avg_vol: score += 10
        
        return min(100, score)
    except:
        return 0

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

        df['ema50'] = EMAIndicator(close=close, window=50).ema_indicator()
        df['ema150'] = EMAIndicator(close=close, window=150).ema_indicator()
        df['ema200'] = EMAIndicator(close=close, window=200).ema_indicator()
        df['rsi'] = RSIIndicator(close=close, window=14).rsi()
        
        c_ema50 = df['ema50'].iloc[-1]
        c_ema150 = df['ema150'].iloc[-1]
        c_ema200 = df['ema200'].iloc[-1]
        c_rsi = df['rsi'].iloc[-1]
        
        rs_score = calculate_rs_score(close, vnindex_series)
        power_score = calculate_proprietary_score(df, rs_score)
        
        trend_ok = (current_price > c_ema50) and (c_ema50 > c_ema150) and (c_ema150 > c_ema200)
        rs_ok = rs_score > 0
        
        take_profit = 0
        stop_loss = 0
        
        if trend_ok or rs_ok:
            stop_loss = current_price * 0.93
            take_profit = current_price * 1.20

        status = "⚪ Theo dõi"
        if power_score >= 80: status = "💎 MUA MẠNH"
        elif power_score >= 60: status = "🟢 MUA"
        elif power_score >= 40: status = "🟡 Giữ"
        else: status = "🔴 Bán/Né"

        if trend_ok or rs_ok:
            return {
                'Mã': ticker.replace('.VN', ''),
                'Giá': current_price,
                'Điểm Sức Mạnh': int(power_score),
                'Vùng Mua': current_price,
                'Cắt Lỗ (-7%)': stop_loss,
                'Mục Tiêu (+20%)': take_profit,
                'RS Rating': rs_score,
                'Thanh khoản': avg_value_20 / 1e9,
                'RSI': c_rsi,
                'Khuyến Nghị': status,
                '_sort_score': power_score
            }
        return None
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---

st.title("🦅 Vũ Phong Alpha Trader v2.3")
st.markdown("""
<style>
div[data-testid="stMetricValue"] { font-size: 20px; }
</style>
""", unsafe_allow_html=True)

# TẠO TABS CHÍNH
tab1, tab2 = st.tabs(["📊 Bộ Lọc Cổ Phiếu & Trading Plan", "📝 Báo Cáo Chuyên Gia (Market View)"])

# --- TAB 1: BỘ LỌC CỔ PHIẾU ---
with tab1:
    col_filter, col_main = st.columns([1, 4])
    
    with col_filter:
        st.subheader("Cấu hình Lọc")
        selected_sector = st.selectbox("Chọn Ngành", list(SECTORS.keys()))
        min_rs = st.slider("RS Rating tối thiểu", -10.0, 50.0, 0.0, step=1.0)
        start_scan = st.button("🔍 Quét Cổ Phiếu", type="primary")
        st.caption("Data: Yahoo Finance")

    with col_main:
        if start_scan:
            with st.spinner(f"Đang phân tích nhóm {selected_sector}..."):
                vnindex_df = get_vnindex_data()
                
                # Check kỹ dữ liệu
                if vnindex_df is not None and not vnindex_df.empty:
                    vnindex_close = vnindex_df['close']
                    tickers = SECTORS[selected_sector]
                    raw_data = get_stock_batch(tickers)
                    
                    results = []
                    if raw_data is not None and not raw_data.empty:
                        bar = st.progress(0)
                        for i, t in enumerate(tickers):
                            bar.progress((i+1)/len(tickers))
                            try:
                                df_single = raw_data[f"{t}.VN"] if f"{t}.VN" in raw_data.columns.levels[0] else None
                                if df_single is None and len(tickers) == 1: df_single = raw_data
                                
                                if df_single is not None:
                                    res = analyze_ticker_pro(t, df_single, vnindex_close)
                                    if res and res['RS Rating'] >= min_rs:
                                        results.append(res)
                            except: continue
                        bar.empty()
                        
                        if results:
                            df_res = pd.DataFrame(results)
                            df_res = df_res.sort_values(by='_sort_score', ascending=False).drop(columns=['_sort_score'])
                            
                            st.success(f"Tìm thấy {len(df_res)} mã tiềm năng.")
                            
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
                                height=500
                            )
                            
                            if not df_res.empty:
                                chart_ticker = st.selectbox("Xem Chart:", df_res['Mã'].tolist())
                                try:
                                    df_chart = raw_data[f"{chart_ticker}.VN"].copy()
                                    df_chart['EMA50'] = EMAIndicator(close=df_chart['Close'], window=50).ema_indicator()
                                    
                                    fig = go.Figure()
                                    fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Giá'))
                                    fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA50'], line=dict(color='orange', width=1.5), name='EMA 50'))
                                    fig.update_layout(title=f"{chart_ticker}", xaxis_rangeslider_visible=False, height=400, template="plotly_dark")
                                    st.plotly_chart(fig, use_container_width=True)
                                except: pass
                        else:
                            st.warning("Không tìm thấy mã phù hợp.")
                    else:
                        st.error("Lỗi: Không tải được dữ liệu cổ phiếu.")
                else:
                    st.error("⚠️ Lỗi kết nối VN-INDEX: Yahoo Finance đang quá tải hoặc trả về dữ liệu rỗng. Vui lòng thử lại sau 1 phút.")

# --- TAB 2: NHẬN ĐỊNH THỊ TRƯỜNG (FIXED BUG) ---
with tab2:
    st.header("📢 Nhận Định & Hành Động Chuyên Gia")
    st.caption("Dữ liệu được cập nhật sau phiên giao dịch (15h30).")
    
    if st.button("🔄 Phân Tích Tổng Quan Thị Trường"):
        with st.spinner("Đang tính toán sức khỏe thị trường..."):
            vnindex_df = get_vnindex_data()
            
            # --- FIX ERROR LOCATION: Check if dataframe is NOT EMPTY ---
            if vnindex_df is not None and not vnindex_df.empty and len(vnindex_df) > 50:
                # 1. Tính toán chỉ số VN-INDEX
                vni = vnindex_df.copy()
                
                try:
                    vni['EMA20'] = EMAIndicator(close=vni['close'], window=20).ema_indicator()
                    vni['EMA50'] = EMAIndicator(close=vni['close'], window=50).ema_indicator()
                    vni['RSI'] = RSIIndicator(close=vni['close'], window=14).rsi()
                    
                    # Lấy dữ liệu an toàn
                    last = vni.iloc[-1]
                    prev = vni.iloc[-2]
                    
                    # 2. Phân tích Vol
                    avg_vol_20 = vni['volume'].rolling(20).mean().iloc[-1]
                    curr_vol = last['volume']
                    vol_status = "Cao hơn TB 20 phiên" if curr_vol > avg_vol_20 else "Thấp hơn TB 20 phiên"
                    
                    # 3. Phân tích Xu hướng
                    trend = ""
                    action = ""
                    bg_color = ""
                    
                    if last['close'] > last['EMA50']:
                        if last['RSI'] > 70:
                            trend = "UPTREND - QUÁ MUA (Overbought)"
                            action = "⚠️ Hạn chế mua đuổi. Nên chốt lời một phần các mã đạt mục tiêu."
                            bg_color = "#ffcc00"
                        else:
                            trend = "UPTREND - TĂNG TRƯỞNG BỀN VỮNG"
                            action = "💎 Duy trì tỷ trọng Cổ phiếu cao (80-100%)."
                            bg_color = "#d4edda"
                    elif last['close'] < last['EMA50'] and last['close'] > last['EMA20']:
                        trend = "SIDEWAY / HỒI PHỤC KỸ THUẬT"
                        action = "⚖️ Giữ tỷ trọng 50% Tiền / 50% Cổ."
                        bg_color = "#fff3cd"
                    else:
                        trend = "DOWNTREND - RỦI RO CAO"
                        action = "🛑 Đưa tỷ trọng Tiền mặt lên tối đa (70-100%)."
                        bg_color = "#f8d7da"

                    col1, col2, col3 = st.columns(3)
                    col1.metric("VN-INDEX", f"{last['close']:,.2f}", f"{(last['close']-prev['close']):.2f} điểm")
                    col2.metric("Thanh khoản", f"{curr_vol/1e6:.1f} tr cổ", vol_status)
                    col3.metric("RSI", f"{last['RSI']:.1f}", "Cao" if last['RSI']>70 else "Ổn")
                    
                    st.markdown("---")
                    
                    st.markdown(f"""
                    <div style="background-color: {bg_color}; padding: 20px; border-radius: 10px; border: 1px solid #ddd;">
                        <h3 style="color: #333; margin-top: 0;">🔎 TRẠNG THÁI: {trend}</h3>
                        <p style="font-size: 18px;"><b>🛡 HÀNH ĐỘNG KHUYẾN NGHỊ:</b> {action}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    
                    st.subheader("📈 Biểu đồ VN-INDEX")
                    fig_vni = go.Figure()
                    fig_vni.add_trace(go.Candlestick(x=vni.index, open=vni['open'], high=vni['high'], low=vni['low'], close=vni['close'], name='VNINDEX'))
                    fig_vni.add_trace(go.Scatter(x=vni.index, y=vni['EMA20'], line=dict(color='blue', width=1), name='EMA 20'))
                    fig_vni.add_trace(go.Scatter(x=vni.index, y=vni['EMA50'], line=dict(color='orange', width=2), name='EMA 50'))
                    fig_vni.update_layout(height=400, template="plotly_dark", xaxis_rangeslider_visible=False)
                    st.plotly_chart(fig_vni, use_container_width=True)

                except Exception as e:
                    st.error(f"Lỗi tính toán chỉ số: {e}")
            else:
                st.error("⚠️ Không thể tải dữ liệu VN-INDEX lúc này (Yahoo API trả về rỗng). Vui lòng thử lại sau.")
