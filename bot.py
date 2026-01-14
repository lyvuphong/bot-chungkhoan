import streamlit as st
import pandas as pd
import numpy as np
import yfinance as yf
from ta.trend import EMAIndicator, SMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import AverageTrueRange
import plotly.graph_objects as go
from datetime import datetime

# --- CẤU HÌNH HỆ THỐNG (SYSTEM CONFIG) ---
st.set_page_config(page_title="Vũ Phong Alpha Trader v3.0", page_icon="🦅", layout="wide")

# --- DANH MỤC CỔ PHIẾU (WATCHLIST) ---
# Hardcoded sector list (Có thể nâng cấp thành file config riêng)
SECTORS = {
    "💎 Bluechips (VN30)": ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
    "🏦 Ngân Hàng": ['VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'HDB', 'VIB', 'SHB', 'LPB', 'MSB', 'OCB', 'TPB', 'EIB'],
    "⚡ Chứng Khoán": ['SSI', 'VND', 'VCI', 'HCM', 'SHS', 'MBS', 'FTS', 'BSI', 'CTS', 'AGR', 'VIX', 'ORS'],
    "🏗 Bất Động Sản & KCN": ['VHM', 'NVL', 'PDR', 'DIG', 'DXG', 'CEO', 'KDH', 'NLG', 'KBC', 'IDC', 'VGC', 'SZC', 'BCM', 'GVR'],
    "🛢 Dầu Khí & Năng Lượng": ['GAS', 'PVD', 'PVS', 'PVT', 'PLX', 'BSR', 'POW', 'REE', 'PC1', 'GEG'],
    "📦 Bán Lẻ & SX": ['MWG', 'MSN', 'PNJ', 'DGW', 'FRT', 'VNM', 'SAB', 'DGC', 'HPG', 'HSG', 'NKG'],
    "🍤 Thủy Sản & Dệt May": ['VHC', 'ANV', 'IDI', 'TNG', 'GIL', 'MSH', 'STK'],
    "🚀 Alpha Midcaps (Growth)": ['FPT', 'DGC', 'GMD', 'REE', 'VHC', 'ANV', 'HAH', 'DGW', 'FRT', 'CTR', 'VGI', 'BMP']
}

# --- MODULE: DATA ENGINE ---

@st.cache_data(ttl=900) # Cache 15 phút
def get_market_data(ticker_list, period="1y"):
    """
    Tải dữ liệu batch từ Yahoo Finance và xử lý MultiIndex.
    """
    symbols = [f"{t}.VN" for t in ticker_list]
    # Thêm VNINDEX để so sánh sức mạnh
    symbols.append("^VNINDEX")
    
    try:
        data = yf.download(symbols, period=period, interval="1d", group_by='ticker', progress=False, threads=True)
        return data
    except Exception as e:
        st.error(f"Lỗi tải dữ liệu: {e}")
        return None

def extract_ticker_data(raw_data, ticker):
    """
    Trích xuất và làm sạch dữ liệu của 1 mã cụ thể từ Raw Data
    """
    symbol = f"{ticker}.VN" if ticker != "^VNINDEX" else ticker
    try:
        # Xử lý trường hợp MultiIndex phức tạp của yfinance bản mới
        df = raw_data[symbol] if symbol in raw_data.columns.levels[0] else None
        
        # Fallback nếu chỉ tải 1 mã
        if df is None and len(raw_data.columns.levels[0]) == 1:
            df = raw_data
            
        if df is None or df.empty: return None

        df = df.copy()
        df.columns = [c.lower() for c in df.columns]
        
        # Fill NaN cơ bản
        df.ffill(inplace=True)
        return df
    except Exception:
        return None

# --- MODULE: CORE ANALYSIS (BRAIN) ---

def calculate_rs_rating(stock_close, market_close):
    """
    Tính điểm RS (Relative Strength) theo phương pháp IBD.
    Trọng số: 40% (6M) + 40% (3M) + 20% (1M)
    """
    try:
        # Align index
        common_idx = stock_close.index.intersection(market_close.index)
        s = stock_close.loc[common_idx]
        m = market_close.loc[common_idx]
        
        if len(s) < 130: return -999
        
        # Performance Stock vs Market
        roc = lambda s_series, m_series, period: (s_series.iloc[-1]/s_series.iloc[-period] - 1) - (m_series.iloc[-1]/m_series.iloc[-period] - 1)
        
        rs_1m = roc(s, m, 21)
        rs_3m = roc(s, m, 63)
        rs_6m = roc(s, m, 126)
        
        raw_rs = (rs_6m * 0.4) + (rs_3m * 0.4) + (rs_1m * 0.2)
        return raw_rs * 100
    except:
        return -999

def analyze_stock(ticker, df_stock, df_market_close):
    """
    Phân tích kỹ thuật chuyên sâu & Quản trị rủi ro
    """
    try:
        if len(df_stock) < 200: return None
        
        # 1. Tính toán chỉ báo
        close = df_stock['close']
        high = df_stock['high']
        low = df_stock['low']
        volume = df_stock['volume']
        
        # Moving Averages
        ema50 = EMAIndicator(close=close, window=50).ema_indicator()
        ema150 = EMAIndicator(close=close, window=150).ema_indicator()
        ema200 = EMAIndicator(close=close, window=200).ema_indicator()
        
        # Momentum & Volatility
        rsi = RSIIndicator(close=close, window=14).rsi()
        atr = AverageTrueRange(high=high, low=low, close=close, window=14).average_true_range()
        
        # Giá trị hiện tại
        curr_price = close.iloc[-1]
        curr_vol = volume.iloc[-1]
        avg_vol_20 = volume.rolling(20).mean().iloc[-1]
        curr_atr = atr.iloc[-1]
        curr_rsi = rsi.iloc[-1]
        
        # Lọc thanh khoản (GTGD > 5 tỷ/phiên)
        if (curr_price * avg_vol_20) < 5_000_000_000: return None

        # 2. Logic Scoring (Thang điểm 100)
        score = 0
        
        # Trend (40 điểm)
        c_ema50, c_ema150, c_ema200 = ema50.iloc[-1], ema150.iloc[-1], ema200.iloc[-1]
        trend_up = (curr_price > c_ema50) and (c_ema50 > c_ema150) and (c_ema150 > c_ema200)
        if trend_up: score += 25
        if curr_price > c_ema200: score += 15
        
        # RS Strength (30 điểm)
        rs_rating = calculate_rs_rating(close, df_market_close)
        if rs_rating > 0: score += 15
        if rs_rating > 10: score += 15
        
        # Dòng tiền & Momentum (30 điểm)
        if 50 <= curr_rsi <= 70: score += 10 # RSI vùng Bullish
        if curr_vol > avg_vol_20 * 1.2: score += 20 # Nổ Vol > 120% TB 20 phiên
        elif curr_vol > avg_vol_20: score += 10

        # 3. Dynamic Trading Plan (Dựa trên ATR)
        # Stoploss rộng hơn 1 chút so với biến động tự nhiên (2.5 ATR)
        sl_price = curr_price - (2.5 * curr_atr)
        sl_pct = (curr_price - sl_price) / curr_price * 100
        
        # Reward/Risk Ratio = 2.5 : 1
        target_price = curr_price + (2.5 * (curr_price - sl_price))
        target_pct = (target_price - curr_price) / curr_price * 100
        
        # Khuyến nghị
        status = "⚪ Theo dõi"
        action_col = "grey"
        
        if score >= 80: 
            status = "💎 MUA MẠNH"
            action_col = "green"
        elif score >= 60: 
            status = "🟢 MUA"
            action_col = "lightgreen"
        elif score < 40:
            status = "🔴 Yếu"
            action_col = "red"

        # Chỉ trả về kết quả nếu Trend ổn hoặc RS mạnh
        if trend_up or rs_rating > 5:
            return {
                'Mã': ticker,
                'Giá': curr_price,
                'Score': int(score),
                'RS Rating': rs_rating,
                'RSI': curr_rsi,
                'Vol/Avg': curr_vol / avg_vol_20,
                'ATR (Biến động)': curr_atr,
                'Stoploss (Dynamic)': sl_price,
                'SL %': sl_pct,
                'Target': target_price,
                'Target %': target_pct,
                'Khuyến Nghị': status,
                '_raw_vol': volume, # Để vẽ chart
                '_raw_close': close,
                '_ema50': ema50,
                '_ema200': ema200
            }
        return None
    except Exception as e:
        return None

# --- UI & VISUALIZATION ---

def main():
    st.title("🦅 Vũ Phong Alpha Trader v3.0 (Core System)")
    st.caption(f"System Time: {datetime.now().strftime('%Y-%m-%d %H:%M')} | Engineer: Vu Phong")
    
    with st.sidebar:
        st.header("⚙️ Control Panel")
        selected_sector = st.selectbox("Chọn Danh Mục Quét", list(SECTORS.keys()))
        custom_tickers = st.text_area("Thêm mã riêng (phân tách dấu phẩy)", "").upper()
        
        st.divider()
        st.subheader("Tham số lọc")
        min_score = st.slider("Điểm sức mạnh tối thiểu", 0, 100, 50)
        
        run_btn = st.button("🚀 Kích hoạt Scan", type="primary")
        st.info("💡 Lưu ý: Dữ liệu Yahoo Finance (.VN) có thể trễ 15p.")

    if run_btn:
        # Chuẩn bị danh sách mã
        ticker_list = SECTORS[selected_sector]
        if custom_tickers:
            extras = [t.strip() for t in custom_tickers.split(',') if t.strip()]
            ticker_list.extend(extras)
        ticker_list = list(set(ticker_list)) # Remove duplicates

        with st.spinner(f"Đang xử lý dữ liệu Big Data cho {len(ticker_list)} mã..."):
            # 1. Tải Data
            raw_data = get_market_data(ticker_list)
            
            if raw_data is not None:
                vnindex_df = extract_ticker_data(raw_data, "^VNINDEX")
                if vnindex_df is None:
                    st.error("Không tải được dữ liệu VNINDEX làm chuẩn benchmark.")
                    st.stop()
                    
                vnindex_close = vnindex_df['close']
                
                # 2. Phân tích Loop
                results = []
                progress_bar = st.progress(0)
                
                for i, ticker in enumerate(ticker_list):
                    df_s = extract_ticker_data(raw_data, ticker)
                    if df_s is not None:
                        res = analyze_stock(ticker, df_s, vnindex_close)
                        if res and res['Score'] >= min_score:
                            results.append(res)
                    progress_bar.progress((i + 1) / len(ticker_list))
                
                progress_bar.empty()
                
                # 3. Hiển thị kết quả
                if results:
                    df_res = pd.DataFrame(results)
                    df_res = df_res.sort_values(by='Score', ascending=False)
                    
                    # Thống kê nhanh
                    c1, c2, c3 = st.columns(3)
                    c1.metric("Mã tiềm năng", len(df_res))
                    c2.metric("Top Pick", df_res.iloc[0]['Mã'])
                    c3.metric("Điểm cao nhất", df_res.iloc[0]['Score'])
                    
                    # Bảng chi tiết
                    st.subheader("📋 Bảng Tín Hiệu Alpha")
                    
                    display_cols = ['Mã', 'Giá', 'Score', 'Khuyến Nghị', 'RS Rating', 'RSI', 'Vol/Avg', 'Stoploss (Dynamic)', 'SL %', 'Target', 'Target %']
                    
                    st.dataframe(
                        df_res[display_cols].style.format({
                            'Giá': '{:,.0f}',
                            'Stoploss (Dynamic)': '{:,.0f}',
                            'Target': '{:,.0f}',
                            'RS Rating': '{:+.2f}',
                            'RSI': '{:.0f}',
                            'Vol/Avg': '{:.2f}x',
                            'SL %': '-{:.1f}%',
                            'Target %': '+{:.1f}%',
                        })
                        .background_gradient(subset=['Score'], cmap='RdYlGn', vmin=40, vmax=100)
                        .background_gradient(subset=['RS Rating'], cmap='Greens')
                        .applymap(lambda x: 'color: #ff4b4b; font-weight: bold' if 'MUA' in str(x) else '', subset=['Khuyến Nghị']),
                        use_container_width=True,
                        height=500
                    )
                    
                    # 4. Chart Phân tích chi tiết (Interactive)
                    st.divider()
                    st.subheader("📈 Phân Tích Kỹ Thuật & Kế Hoạch Giao Dịch")
                    
                    col_sel, col_chart = st.columns([1, 4])
                    
                    with col_sel:
                        selected_ticker_chart = st.radio("Chọn mã xem biểu đồ:", df_res['Mã'].tolist())
                        
                        # Lấy data của mã đã chọn
                        row_data = df_res[df_res['Mã'] == selected_ticker_chart].iloc[0]
                        
                        st.markdown(f"""
                        **PLAN: {selected_ticker_chart}**
                        
                        🔴 **Cắt lỗ:** {row_data['Stoploss (Dynamic)']:,.0f}
                        
                        🟢 **Chốt lời:** {row_data['Target']:,.0f}
                        
                        ⚡ **ATR:** {row_data['ATR (Biến động)']:,.0f}
                        """)
                    
                    with col_chart:
                        # Vẽ Chart
                        raw_close = row_data['_raw_close']
                        ema50 = row_data['_ema50']
                        ema200 = row_data['_ema200']
                        
                        # Lấy 6 tháng gần nhất để vẽ cho gọn
                        lookback = 126
                        dates = raw_close.index[-lookback:]
                        
                        fig = go.Figure()
                        
                        # Giá
                        fig.add_trace(go.Scatter(x=dates, y=raw_close[-lookback:], mode='lines', name='Giá', line=dict(color='white', width=1)))
                        # EMA
                        fig.add_trace(go.Scatter(x=dates, y=ema50[-lookback:], mode='lines', name='EMA50', line=dict(color='orange', width=1)))
                        fig.add_trace(go.Scatter(x=dates, y=ema200[-lookback:], mode='lines', name='EMA200', line=dict(color='blue', width=1)))
                        
                        # Vùng Mua/Bán (Lines)
                        curr_p = row_data['Giá']
                        sl_p = row_data['Stoploss (Dynamic)']
                        tp_p = row_data['Target']
                        
                        fig.add_hline(y=curr_p, line_dash="dot", annotation_text="Entry", annotation_position="top right", line_color="yellow")
                        fig.add_hline(y=sl_p, line_dash="dash", annotation_text="STOPLOSS", annotation_position="bottom right", line_color="red")
                        fig.add_hline(y=tp_p, line_dash="dash", annotation_text="TARGET", annotation_position="top right", line_color="green")

                        fig.update_layout(
                            title=f"{selected_ticker_chart} - Trading Plan (Risk:Reward = 1:2.5)",
                            template="plotly_dark",
                            height=600,
                            xaxis_rangeslider_visible=False
                        )
                        st.plotly_chart(fig, use_container_width=True)

                else:
                    st.warning("Không tìm thấy cổ phiếu nào đạt tiêu chuẩn Alpha hôm nay. Hãy nghỉ ngơi!")
            else:
                st.error("Lỗi kết nối dữ liệu máy chủ.")

if __name__ == "__main__":
    main()
