import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import plotly.graph_objects as go
from datetime import datetime

# --- CẤU HÌNH UI CHUẨN MOBILE ---
st.set_page_config(page_title="Vũ Phong Mobile Trader", page_icon="📱", layout="wide")

# CSS hack để ẩn bớt padding trên mobile cho rộng chỗ
st.markdown("""
    <style>
    .block-container { padding-top: 1rem; padding-bottom: 0rem; padding-left: 1rem; padding-right: 1rem; }
    div[data-testid="stMetricValue"] { font-size: 1.2rem; }
    </style>
""", unsafe_allow_html=True)

# --- DANH MỤC CỔ PHIẾU (DATA SECTOR) ---
SECTORS = {
    "VN30 (Bluechips)": ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
    "Ngân Hàng": ['VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'HDB', 'VIB', 'SHB', 'LPB', 'MSB', 'OCB', 'TPB'],
    "Chứng Khoán": ['SSI', 'VND', 'VCI', 'HCM', 'SHS', 'MBS', 'FTS', 'BSI', 'CTS', 'AGR', 'VIX', 'ORS'],
    "Bất Động Sản": ['VHM', 'NVL', 'PDR', 'DIG', 'DXG', 'CEO', 'KDH', 'NLG', 'HDG', 'HQC', 'SCR'],
    "BĐS Khu CN": ['KBC', 'NTC', 'IDC', 'VGC', 'SZC', 'BCM', 'GVR', 'PHR', 'ITA', 'LHG'],
    "Dầu Khí": ['GAS', 'PVD', 'PVS', 'PVT', 'PLX', 'BSR', 'OIL', 'PVB'],
    "Thủy Sản": ['VHC', 'MPC', 'ANV', 'IDI', 'CMX', 'FMC', 'ACL'],
    "Dệt May": ['TNG', 'GIL', 'MSH', 'VGT', 'STK', 'ADS'],
    "Thép": ['HPG', 'HSG', 'NKG', 'TLH', 'POM'],
    "Bán Lẻ": ['MWG', 'FRT', 'DGW', 'PET', 'PNJ']
}

# --- HÀM XỬ LÝ DỮ LIỆU ---

@st.cache_data(ttl=600)
def get_market_data(ticker_list):
    """Tải dữ liệu giá hàng loạt (Batch Download)"""
    symbols = [f"{t}.VN" for t in ticker_list]
    try:
        raw_data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        return raw_data
    except Exception:
        return None

@st.cache_data(ttl=3600) # Cache lâu hơn vì chỉ số cơ bản ít thay đổi
def get_company_info(symbol):
    """Lấy chỉ số cơ bản: PE, EPS, Market Cap..."""
    try:
        ticker = yf.Ticker(f"{symbol}.VN")
        info = ticker.info
        
        # Xử lý dữ liệu trả về (Yahoo đôi khi trả về None)
        return {
            "pe": info.get('trailingPE', 0),
            "eps": info.get('trailingEps', 0),
            "pb": info.get('priceToBook', 0),
            "market_cap": info.get('marketCap', 0),
            "shares": info.get('sharesOutstanding', 0),
            "dividend": info.get('dividendYield', 0),
            "name": info.get('longName', symbol)
        }
    except Exception:
        return None

def analyze_ticker(ticker, df_ticker):
    """Phân tích kỹ thuật"""
    try:
        df = df_ticker.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if len(df) < 50 or df['close'].iloc[-1] < 1000: return None

        # Chỉ báo
        df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['close']
        
        # Logic: Uptrend khi giá > EMA50
        is_uptrend = price > last['EMA50']
        
        # Điểm mua RSI: 40-60
        buy_signal = is_uptrend and (40 <= last['RSI'] <= 65)
        
        stop_loss = price * 0.93
        take_profit = price * 1.20
        
        return {
            'Mã': ticker.replace('.VN', ''),
            'Giá': price,
            'Thay đổi %': ((price - prev['close'])/prev['close']) * 100,
            'RSI': last['RSI'],
            'Xu hướng': 'Tăng 🟢' if is_uptrend else 'Giảm 🔴',
            'Tín hiệu': '✅ MUA' if buy_signal else 'Theo dõi',
            'EMA50': last['EMA50'],
            'Volume': last['volume']
        }
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---

st.title("📱 Vũ Phong Mobile Trader")
st.caption("Công cụ lọc cổ phiếu chuyên nghiệp tích hợp Phân tích Cơ bản")

# 1. BỘ LỌC (Dùng Expander cho gọn trên mobile)
with st.expander("🔍 Cấu hình Bộ Lọc (Bấm để mở)", expanded=True):
    selected_sector = st.selectbox("Chọn Nhóm Ngành", list(SECTORS.keys()))
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        run_scan = st.button("🚀 Quét Thị Trường", type="primary", use_container_width=True)
    with col_btn2:
        st.caption("Dữ liệu: Yahoo Finance")

# 2. XỬ LÝ KẾT QUẢ
if run_scan:
    ticker_list = SECTORS[selected_sector]
    with st.spinner(f"Đang quét {len(ticker_list)} mã ngành {selected_sector}..."):
        raw_data = get_market_data(ticker_list)
        
        if raw_data is not None:
            results = []
            
            # Xử lý nhanh (không lấy info cơ bản ở bước này để tránh treo máy)
            for ticker in ticker_list:
                try:
                    df_single = raw_data[f"{ticker}.VN"] if f"{ticker}.VN" in raw_data.columns.levels[0] else None
                    if df_single is None and len(ticker_list) == 1: df_single = raw_data
                    
                    if df_single is not None:
                        res = analyze_ticker(ticker, df_single)
                        if res: results.append(res)
                except: continue
            
            if results:
                st.session_state['scan_results'] = pd.DataFrame(results)
                st.toast(f"Đã tìm thấy {len(results)} mã!", icon="✅")
            else:
                st.warning("Không tìm thấy mã nào thỏa mãn điều kiện.")

# 3. HIỂN THỊ KẾT QUẢ (LƯU TRONG SESSION STATE ĐỂ KHÔNG MẤT KHI RELOAD)
if 'scan_results' in st.session_state:
    df_res = st.session_state['scan_results']
    
    st.markdown("### 📋 Kết quả Lọc")
    
    # Hiển thị bảng rút gọn cho Mobile (Chỉ hiện Mã, Giá, Tín hiệu)
    st.dataframe(
        df_res[['Mã', 'Giá', 'Thay đổi %', 'Tín hiệu']].style.format({
            'Giá': '{:,.0f}', 'Thay đổi %': '{:+.2f}%'
        }).applymap(lambda v: 'color: green; font-weight: bold;' if v == '✅ MUA' else '', subset=['Tín hiệu']),
        use_container_width=True,
        hide_index=True
    )
    
    st.markdown("---")
    st.markdown("### 📊 Soi Chi Tiết & Chỉ Số Cơ Bản")
    
    # Chọn mã để xem chi tiết
    selected_ticker = st.selectbox("Chọn mã để xem chi tiết:", df_res['Mã'])
    
    if selected_ticker:
        # Lấy lại data giá để vẽ chart
        row_data = df_res[df_res['Mã'] == selected_ticker].iloc[0]
        
        # --- PHẦN 1: CHART KỸ THUẬT ---
        # Vẽ chart nến đơn giản cho mobile
        try:
            raw_data = get_market_data([selected_ticker]) # Lấy lại data để vẽ chart
            df_chart = raw_data[f"{selected_ticker}.VN"] if raw_data is not None else None
            
            if df_chart is not None:
                # Fix lỗi multiindex
                if isinstance(df_chart.columns, pd.MultiIndex): df_chart.columns = df_chart.columns.get_level_values(0)
                
                fig = go.Figure(data=[go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'])])
                fig.update_layout(
                    title=f"Chart {selected_ticker}", 
                    height=350, 
                    margin=dict(l=10, r=10, t=30, b=10),
                    xaxis_rangeslider_visible=False
                )
                st.plotly_chart(fig, use_container_width=True)
        except: pass

        # --- PHẦN 2: CHỈ SỐ CƠ BẢN (FUNDAMENTALS) ---
        st.markdown(f"#### 🏢 Sức khỏe Tài chính: **{selected_ticker}**")
        with st.spinner("Đang tải dữ liệu Báo cáo tài chính..."):
            fund_info = get_company_info(selected_ticker)
        
        if fund_info:
            # Format số liệu cho đẹp
            pe_val = f"{fund_info['pe']:.2f}" if fund_info['pe'] else "N/A"
            eps_val = f"{fund_info['eps']:.0f} đ" if fund_info['eps'] else "N/A"
            pb_val = f"{fund_info['pb']:.2f}" if fund_info['pb'] else "N/A"
            
            # Vốn hóa đổi sang Tỷ đồng
            cap_val = f"{fund_info['market_cap']/1000000000:,.0f} Tỷ" if fund_info['market_cap'] else "N/A"
            
            # Cổ tức
            div_val = f"{fund_info['dividend']*100:.2f}%" if fund_info['dividend'] else "0%"
            
            # HIỂN THỊ DẠNG METRIC (Rất đẹp trên Mobile)
            c1, c2, c3 = st.columns(3)
            with c1: st.metric("P/E (Định giá)", pe_val, delta_color="normal")
            with c2: st.metric("EPS (Lợi nhuận/CP)", eps_val)
            with c3: st.metric("P/B (Sổ sách)", pb_val)
            
            c4, c5, c6 = st.columns(3)
            with c4: st.metric("Vốn hóa", cap_val)
            with c5: st.metric("Cổ tức", div_val)
            with c6: st.metric("KL Lưu hành", f"{fund_info['shares']/1000000:,.1f} Tr")
            
            # Đánh giá nhanh
            st.info(f"""
            **Nhận định nhanh:**
            - **Giá mua khuyến nghị:** {row_data['Giá']:,.0f} VND
            - **Cắt lỗ (-7%):** {row_data['Giá']*0.93:,.0f} VND
            - **Chốt lời (+20%):** {row_data['Giá']*1.2:,.0f} VND
            - **Trạng thái:** {row_data['Tín hiệu']}
            """)
        else:
            st.warning("Không lấy được dữ liệu cơ bản từ nguồn quốc tế.")

# --- FOOTER ---
st.markdown("---")
st.caption("Developed by Expert Investor (20 Yrs Exp).")
