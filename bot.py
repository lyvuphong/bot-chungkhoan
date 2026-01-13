import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import plotly.graph_objects as go
from datetime import datetime

# --- CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Vũ Phong Pro Trader", page_icon="💎", layout="wide")

# --- DANH MỤC CỔ PHIẾU CHUYÊN SÂU (DATA SECTOR) ---
SECTORS = {
    "VN30 (Bluechips)": ['ACB', 'BCM', 'BID', 'BVH', 'CTG', 'FPT', 'GAS', 'GVR', 'HDB', 'HPG', 'MBB', 'MSN', 'MWG', 'PLX', 'POW', 'SAB', 'SHB', 'SSB', 'SSI', 'STB', 'TCB', 'TPB', 'VCB', 'VHM', 'VIB', 'VIC', 'VJC', 'VNM', 'VPB', 'VRE'],
    "Ngân Hàng (Bank)": ['VCB', 'BID', 'CTG', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'HDB', 'VIB', 'SHB', 'LPB', 'MSB', 'OCB', 'TPB'],
    "Chứng Khoán": ['SSI', 'VND', 'VCI', 'HCM', 'SHS', 'MBS', 'FTS', 'BSI', 'CTS', 'AGR', 'VIX', 'ORS'],
    "Bất Động Sản": ['VHM', 'NVL', 'PDR', 'DIG', 'DXG', 'CEO', 'KDH', 'NLG', 'HDG', 'HQC', 'SCR'],
    "BĐS Khu Công Nghiệp": ['KBC', 'IDC', 'VGC', 'SZC', 'BCM', 'GVR', 'PHR', 'ITA', 'NTC', 'LHG'],
    "Dầu Khí": ['GAS', 'PVD', 'PVS', 'PVT', 'PLX', 'BSR', 'OIL', 'PVB'],
    "Thủy Sản": ['VHC', 'MPC', 'ANV', 'IDI', 'CMX', 'FMC', 'ACL'],
    "Dệt May": ['TNG', 'GIL', 'MSH', 'VGT', 'STK', 'ADS'],
    "VN100 (Đại diện)": ['HPG', 'FPT', 'MWG', 'MSN', 'VIC', 'VHM', 'VCB', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'SSI', 'VND', 'DGC', 'REE', 'GMD', 'PNJ', 'VHC', 'KBC'], # List rút gọn đại diện
    "HNX30 (Đại diện)": ['SHS', 'CEO', 'IDC', 'MBS', 'PVS', 'TNG', 'VCS', 'HUT', 'L14', 'NVB']
}

# --- HÀM XỬ LÝ DỮ LIỆU CHUYÊN NGHIỆP ---

@st.cache_data(ttl=600)
def get_market_data(ticker_list):
    """
    Tải dữ liệu hàng loạt và chuẩn hóa
    """
    data_packages = []
    # Thêm đuôi .VN cho Yahoo Finance
    symbols = [f"{t}.VN" for t in ticker_list]
    
    try:
        # Tải batch để tăng tốc độ
        raw_data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        return raw_data
    except Exception as e:
        return None

def analyze_ticker(ticker, df_ticker):
    """
    Phân tích kỹ thuật chuyên sâu & Tạo tín hiệu Mua/Bán
    """
    try:
        # Chuẩn hóa cột (xử lý MultiIndex nếu có)
        df = df_ticker.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        # Bỏ qua nếu thiếu dữ liệu
        if len(df) < 200: return None
        if df['close'].iloc[-1] < 1000: return None # Bỏ qua cổ phiếu rác < 1000đ

        # --- CHỈ SỐ KỸ THUẬT ---
        # 1. Trend (Xu hướng)
        df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        
        # 2. Momentum (Động lượng)
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        # 3. Volatility (Biến động - Bollinger Bands)
        bb = BollingerBands(close=df['close'], window=20, window_dev=2)
        df['bb_high'] = bb.bollinger_hband()
        df['bb_low'] = bb.bollinger_lband()

        # --- TÍN HIỆU GIAO DỊCH (LOGIC CHUYÊN GIA) ---
        last = df.iloc[-1]
        prev = df.iloc[-2]
        
        price = last['close']
        
        # Điều kiện xu hướng: Giá > EMA50 > EMA200 (Uptrend bền vững)
        is_uptrend = (price > last['EMA50']) and (last['EMA50'] > last['EMA200'])
        
        # Điểm mua: Uptrend + RSI chưa quá nóng (40-65) + Volume đột biến (Option)
        # Ở đây dùng RSI < 70 để an toàn
        buy_signal = is_uptrend and (40 <= last['RSI'] <= 70)
        
        # Tính toán Quản trị rủi ro
        stop_loss = price * 0.93  # Cắt lỗ 7%
        take_profit = price * 1.20 # Chốt lời 20%
        
        return {
            'Mã': ticker.replace('.VN', ''),
            'Giá': price,
            'Thay đổi %': ((price - prev['close'])/prev['close']) * 100,
            'RSI': last['RSI'],
            'Xu hướng': 'Tăng 🟢' if is_uptrend else 'Giảm/Sideway 🔴',
            'Điểm Mua': '✅ MUA' if buy_signal else 'Theo dõi',
            'Cắt lỗ (-7%)': stop_loss,
            'Chốt lãi (+20%)': take_profit,
            'Volume': last['volume']
        }
    except Exception:
        return None

# --- GIAO DIỆN CHÍNH ---

st.title("💎 Vũ Phong Pro Trader - Hệ thống Đầu tư Thông minh")
st.markdown(f"*Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M')}*")

# TẠO TABS
tab1, tab2 = st.tabs(["🔍 Bộ Lọc Cổ Phiếu (Screener)", "📝 Báo Cáo Thị Trường (Daily Report)"])

# --- TAB 1: BỘ LỌC ---
with tab1:
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.subheader("Cấu hình")
        selected_sector = st.selectbox("Chọn Nhóm Ngành", list(SECTORS.keys()))
        
        st.markdown("---")
        st.info("""
        **Quy tắc Giao dịch:**
        * **Mua:** Khi có tín hiệu '✅ MUA'.
        * **Cắt lỗ:** Tuyệt đối tại giá đỏ.
        * **Chốt lời:** Khi đạt giá xanh hoặc RSI > 80.
        """)
    
    with col2:
        if st.button("🚀 Quét Tín Hiệu Ngay", type="primary"):
            ticker_list = SECTORS[selected_sector]
            st.write(f"Đang phân tích dữ liệu nhóm: **{selected_sector}**...")
            
            raw_data = get_market_data(ticker_list)
            
            if raw_data is not None and not raw_data.empty:
                results = []
                progress_bar = st.progress(0)
                
                # Duyệt qua từng mã trong batch data
                for i, ticker in enumerate(ticker_list):
                    progress_bar.progress((i+1)/len(ticker_list))
                    try:
                        # Lấy dataframe con của từng mã
                        df_single = raw_data[f"{ticker}.VN"] if f"{ticker}.VN" in raw_data.columns.levels[0] else None
                        
                        # Fallback nếu cấu trúc data khác (đôi khi yahoo trả về đơn cấp nếu chỉ request 1 mã)
                        if df_single is None and len(ticker_list) == 1:
                            df_single = raw_data
                            
                        if df_single is not None:
                            res = analyze_ticker(ticker, df_single)
                            if res: results.append(res)
                    except Exception:
                        continue
                        
                progress_bar.empty()
                
                # HIỂN THỊ KẾT QUẢ
                if results:
                    df_res = pd.DataFrame(results)
                    
                    # Style bảng chuyên nghiệp
                    st.success(f"Tìm thấy {len(df_res)} mã cổ phiếu.")
                    
                    st.dataframe(
                        df_res.style.format({
                            'Giá': '{:,.0f}',
                            'Cắt lỗ (-7%)': '{:,.0f}', 
                            'Chốt lãi (+20%)': '{:,.0f}',
                            'RSI': '{:.1f}',
                            'Thay đổi %': '{:+.2f}%',
                            'Volume': '{:,.0f}'
                        })
                        .background_gradient(subset=['Thay đổi %'], cmap='RdYlGn')
                        .applymap(lambda v: 'color: red; font-weight: bold;' if v == '✅ MUA' else '', subset=['Điểm Mua']),
                        use_container_width=True,
                        height=500
                    )
                    
                    # VẼ BIỂU ĐỒ MÃ TỐT NHẤT
                    st.markdown("### 📈 Phân tích Kỹ thuật (Mã Tiềm năng nhất)")
                    best_pick = df_res.iloc[0]['Mã'] # Lấy mã đầu tiên
                    pick_select = st.selectbox("Chọn mã soi chart:", df_res['Mã'], index=0)
                    
                    try:
                        df_chart = raw_data[f"{pick_select}.VN"].copy()
                        # Tính lại chỉ báo cho biểu đồ
                        df_chart['EMA50'] = EMAIndicator(close=df_chart['Close'], window=50).ema_indicator()
                        df_chart['EMA200'] = EMAIndicator(close=df_chart['Close'], window=200).ema_indicator()
                        
                        fig = go.Figure()
                        fig.add_trace(go.Candlestick(x=df_chart.index, open=df_chart['Open'], high=df_chart['High'], low=df_chart['Low'], close=df_chart['Close'], name='Giá'))
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA50'], line=dict(color='orange', width=1), name='EMA 50 (Trung hạn)'))
                        fig.add_trace(go.Scatter(x=df_chart.index, y=df_chart['EMA200'], line=dict(color='blue', width=2), name='EMA 200 (Dài hạn)'))
                        
                        fig.update_layout(title=f"Biểu đồ {pick_select} - Trend Following", template="plotly_white", xaxis_rangeslider_visible=False, height=500)
                        st.plotly_chart(fig, use_container_width=True)
                    except:
                        st.warning("Không vẽ được biểu đồ chi tiết.")
                        
                else:
                    st.warning("Không có dữ liệu hoặc không có mã nào thỏa mãn điều kiện cơ bản.")
            else:
                st.error("Lỗi kết nối dữ liệu Yahoo Finance. Vui lòng thử lại sau 1 phút.")

# --- TAB 2: BÁO CÁO THỊ TRƯỜNG (REPORT) ---
with tab2:
    st.header("📝 Báo cáo Tổng quan Thị trường (Daily Report)")
    st.caption("Dùng chức năng này sau 15:00 để có nhận định cuối ngày.")
    
    if st.button("📄 Tạo Báo Cáo Tổng Hợp 18h00"):
        with st.spinner("Đang tổng hợp dữ liệu toàn thị trường (VN100)..."):
            # Lấy mẫu VN100 để đại diện thị trường
            sample_list = SECTORS["VN100 (Đại diện)"]
            raw_data = get_market_data(sample_list)
            
            up_count = 0
            down_count = 0
            total_vol = 0
            top_gainers = []
            
            if raw_data is not None:
                for ticker in sample_list:
                    try:
                        df = raw_data[f"{ticker}.VN"]
                        if df is None or len(df) < 2: continue
                        
                        change = (df['Close'].iloc[-1] - df['Close'].iloc[-2])
                        if change > 0: up_count += 1
                        else: down_count += 1
                        
                        total_vol += df['Volume'].iloc[-1]
                        
                        if change > 0:
                            top_gainers.append((ticker, (change/df['Close'].iloc[-2])*100))
                    except: continue
                
                # Sắp xếp top tăng
                top_gainers.sort(key=lambda x: x[1], reverse=True)
                
                # XUẤT TEXT BÁO CÁO
                report_text = f"""
                📊 **BÁO CÁO THỊ TRƯỜNG CHỨNG KHOÁN VIỆT NAM**
                🕒 Thời gian: 18:00 - Ngày {datetime.now().strftime('%d/%m/%Y')}
                
                **1. TỔNG QUAN:**
                - Thị trường đại diện (VN100): {up_count} mã Tăng / {down_count} mã Giảm.
                - Xu hướng chung: {'🟢 TÍCH CỰC' if up_count > down_count else '🔴 TIÊU CỰC'}
                
                **2. DÒNG TIỀN:**
                - Các mã dẫn dắt tâm lý: {', '.join([f"{x[0]} ({x[1]:.1f}%)" for x in top_gainers[:5]])}
                
                **3. NHẬN ĐỊNH CHUYÊN GIA (BOT):**
                - Nếu số mã tăng áp đảo (>60%): Thị trường đang trong pha hồi phục/tăng giá. Có thể giải ngân vào các mã có tín hiệu MUA ở Tab 1.
                - Nếu số mã giảm áp đảo: Nên giữ tỷ trọng tiền mặt cao, hạn chế bắt đáy.
                - Chú ý các mã giữ được nền giá trên EMA50 trong bối cảnh thị trường chỉnh.
                
                **4. HÀNH ĐỘNG KHUYẾN NGHỊ:**
                - Kiểm tra lại danh mục nắm giữ.
                - Cắt lỗ ngay nếu vi phạm nguyên tắc -7%.
                - Không mua đuổi (FOMO) nếu RSI > 70.
                """
                
                st.markdown(report_text)
                st.text_area("Copy nội dung báo cáo:", value=report_text, height=300)
            else:
                st.error("Không lấy được dữ liệu thị trường để làm báo cáo.")

st.markdown("---")
st.caption("Developed by Expert Investor (20 Yrs Experience). Data Source: Yahoo Finance.")

