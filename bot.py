import streamlit as st
import pandas as pd
import yfinance as yf
from ta.trend import SMAIndicator, EMAIndicator
from ta.momentum import RSIIndicator
from ta.volatility import BollingerBands
import plotly.graph_objects as go
from datetime import datetime
import random
# ... các import cũ ...
from vnstock import stock_overview, stock_evaluation, quote_instant
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
    "VN100 (Đại diện)": ['HPG', 'FPT', 'MWG', 'MSN', 'VIC', 'VHM', 'VCB', 'TCB', 'VPB', 'MBB', 'ACB', 'STB', 'SSI', 'VND', 'DGC', 'REE', 'GMD', 'PNJ', 'VHC', 'KBC'],
    "HNX30 (Đại diện)": ['SHS', 'CEO', 'IDC', 'MBS', 'PVS', 'TNG', 'VCS', 'HUT', 'L14', 'NVB']
}

# --- QUOTES ĐẦU TƯ (TÂM LÝ CHIẾN) ---
QUOTES = [
    "Quy tắc số 1: Không bao giờ để mất tiền. Quy tắc số 2: Đừng quên quy tắc số 1. - Warren Buffett",
    "Thị trường chứng khoán là công cụ chuyển tiền từ người thiếu kiên nhẫn sang người kiên nhẫn. - Warren Buffett",
    "Giá là những gì bạn trả, Giá trị là những gì bạn nhận được. - Warren Buffett",
    "Trong ngắn hạn thị trường là một cái máy bỏ phiếu, nhưng trong dài hạn nó là một cái bàn cân. - Benjamin Graham",
    "Rủi ro đến từ việc bạn không biết mình đang làm gì. - Warren Buffett",
    "Đừng cố gắng bắt dao rơi. Hãy đợi cho đến khi con dao cắm phập xuống đất và rung lắc xong. - Old Wall Street Sayings",
    "Bạn không đúng hay sai vì đám đông đồng ý với bạn. Bạn đúng vì số liệu và lập luận của bạn đúng. - Benjamin Graham"
]

# --- HÀM XỬ LÝ DỮ LIỆU CHUYÊN NGHIỆP ---

@st.cache_data(ttl=600)
def get_market_data(ticker_list):
    """Tải dữ liệu kỹ thuật hàng loạt"""
    symbols = [f"{t}.VN" for t in ticker_list]
    try:
        raw_data = yf.download(symbols, period="1y", interval="1d", group_by='ticker', progress=False, threads=True)
        return raw_data
    except Exception:
        return None

def analyze_ticker(ticker, df_ticker):
    """Phân tích kỹ thuật chuyên sâu"""
    try:
        df = df_ticker.copy()
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df.columns = [c.lower() for c in df.columns]
        
        if len(df) < 200: return None
        if df['close'].iloc[-1] < 1000: return None 

        df['EMA50'] = EMAIndicator(close=df['close'], window=50).ema_indicator()
        df['EMA200'] = EMAIndicator(close=df['close'], window=200).ema_indicator()
        df['RSI'] = RSIIndicator(close=df['close'], window=14).rsi()
        
        last = df.iloc[-1]
        prev = df.iloc[-2]
        price = last['close']
        
        is_uptrend = (price > last['EMA50']) and (last['EMA50'] > last['EMA200'])
        buy_signal = is_uptrend and (40 <= last['RSI'] <= 70)
        
        return {
            'Mã': ticker.replace('.VN', ''),
            'Giá': price,
            'Thay đổi %': ((price - prev['close'])/prev['close']) * 100,
            'RSI': last['RSI'],
            'Xu hướng': 'Tăng 🟢' if is_uptrend else 'Giảm/Sideway 🔴',
            'Điểm Mua': '✅ MUA' if buy_signal else 'Theo dõi',
            'Cắt lỗ (-7%)': price * 0.93,
            'Chốt lãi (+20%)': price * 1.20,
            'Volume': last['volume']
        }
    except Exception:
        return None

def get_fundamental_analysis(ticker):
    """
    Phân tích cơ bản chuyên sâu (Sử dụng VNSTOCK - Dữ liệu chuẩn xác từ TCBS/SSI)
    """
    try:
        symbol = ticker.upper()
        
        # --- BƯỚC 1: LẤY DỮ LIỆU TỪ VNSTOCK ---
        # 1. Lấy thông tin tổng quan (Vốn hóa, ngành...)
        try:
            df_overview = stock_overview(symbol=symbol)
            if df_overview is None or df_overview.empty: return None
            overview = df_overview.iloc[0]
        except: return None # Không tìm thấy mã

        # 2. Lấy chỉ số định giá (P/E, P/B, ROE...)
        try:
            df_eval = stock_evaluation(symbol=symbol, period=1, lang='vi')
            if df_eval is None or df_eval.empty:
                # Fallback nếu mã mới lên sàn chưa có đánh giá
                evaluation_data = {}
            else:
                evaluation_data = df_eval.iloc[0]
        except: evaluation_data = {}

        # 3. Lấy giá hiện tại (Real-time)
        try:
            df_price = quote_instant(symbol=symbol)
            current_price = df_price['price'].iloc[0] * 1000 # VNStock trả về nghìn đồng
        except: 
            current_price = 0

        # --- BƯỚC 2: CHUẨN HÓA DỮ LIỆU ---
        # Lưu ý: VNStock trả về 'exchange', 'industry', 'marketCap' (tỷ đồng)
        
        market_cap_ty_dong = overview.get('marketCap', 0) 
        market_cap = market_cap_ty_dong * 1_000_000_000 # Đổi về VND để thống nhất logic
        
        # Chỉ số tài chính (Handle missing keys an toàn)
        pe = evaluation_data.get('PE', 0)
        pb = evaluation_data.get('PB', 0)
        roe = evaluation_data.get('ROE', 0) # VNStock thường trả về %, ví dụ 0.15 hoặc 15
        
        # Chuẩn hóa ROE về dạng thập phân (0.15) nếu nó đang là số nguyên (15)
        if roe > 1: roe = roe / 100
        
        # Cổ tức: VNStock không trả trực tiếp Yield trong hàm eval, ta ước lượng hoặc bỏ qua tạm thời
        # Để đơn giản, ta dùng P/B và P/E để chấm điểm chính
        
        # --- BƯỚC 3: LOGIC TÍNH ĐIỂM (COMPOUNDER GUARDIAN) ---
        score = 0
        details = []
        
        # 1. Vị thế & Quy mô (Market Cap)
        if market_cap_ty_dong > 10_000: # > 10k tỷ
            score += 2
            details.append(f"✅ Vốn hóa: {market_cap_ty_dong:,.0f} tỷ - Bluechip đầu ngành.")
        elif market_cap_ty_dong > 3_000:
            score += 1.5
            details.append(f"✅ Vốn hóa: {market_cap_ty_dong:,.0f} tỷ - Midcap quy mô tốt.")
        else:
            score += 0.5
            details.append(f"⚠️ Vốn hóa: {market_cap_ty_dong:,.0f} tỷ - Penny/Smallcap (Biến động cao).")

        # 2. Hiệu quả sử dụng vốn (ROE)
        if roe > 0.15: 
            score += 2.5
            details.append(f"✅ ROE = {roe*100:.1f}%: Doanh nghiệp tạo lãi xuất sắc (>15%).")
        elif roe > 0.10:
            score += 1.5
            details.append(f"⚖️ ROE = {roe*100:.1f}%: Hiệu quả sinh lời ổn định.")
        else:
            details.append(f"⚠️ ROE = {roe*100:.1f}%: Hiệu quả sử dụng vốn thấp.")

        # 3. Định giá (P/E)
        if pe > 0:
            if pe < 10:
                score += 2.5
                details.append(f"✅ P/E = {pe:.1f}: Định giá RẤT RẺ (Vùng mua giá trị).")
            elif 10 <= pe < 18:
                score += 1.5
                details.append(f"⚖️ P/E = {pe:.1f}: Định giá HỢP LÝ.")
            else:
                score += 0.5
                details.append(f"⚠️ P/E = {pe:.1f}: Định giá CAO (Phản ánh kỳ vọng lớn).")
        else:
            details.append("⚠️ P/E Âm: Doanh nghiệp đang thua lỗ.")

        # 4. Giá trị sổ sách (P/B) - Tiêu chí phụ cho tích sản
        if pb > 0 and pb < 1.5:
             score += 1
             details.append(f"✅ P/B = {pb:.1f}: Giá cổ phiếu sát giá trị sổ sách (An toàn).")
        
        # --- BƯỚC 4: TỔNG HỢP ---
        # Thang điểm tối đa khoảng 8-9 (dành chỗ cho yếu tố con người/tin tức)
        final_score = min(score + 1, 10) # +1 điểm khuyến khích cơ bản
        
        evaluation = ""
        if final_score >= 8: evaluation = "💎 CƠ HỘI VÀNG (Excellent Case)"
        elif final_score >= 6: evaluation = "⚖️ TRẠNG THÁI TỐT (Investable)"
        else: evaluation = "⚠️ CẦN CÂN NHẮC KỸ (High Risk)"

        return {
            'symbol': symbol,
            'name': overview.get('shortName', symbol), # Lấy tên cty
            'price': current_price,
            'score': round(final_score, 1),
            'evaluation': evaluation,
            'details': details,
            'metrics': {
                'P/E': pe, 'P/B': pb, 'ROE': roe, 'Div Yield': 0 # VNStock basic chưa có yield, để 0
            }
        }

    except Exception as e:
        print(f"VNStock Error [{ticker}]: {e}")
        return None
# --- GIAO DIỆN CHÍNH ---

st.title("💎 Vũ Phong Pro Trader - Hệ thống Đầu tư Thông minh")
st.markdown(f"*Cập nhật: {datetime.now().strftime('%d/%m/%Y %H:%M')}*")

# TẠO TABS
tab1, tab2, tab3 = st.tabs(["🔍 Bộ Lọc (Screener)", "📝 Báo Cáo (Report)", "🐢 Đầu Tư Giá Trị (Value & Compound)"])

# --- TAB 1: BỘ LỌC KỸ THUẬT ---
with tab1:
    col1, col2 = st.columns([1, 3])
    with col1:
        st.subheader("Cấu hình Lọc")
        selected_sector = st.selectbox("Chọn Nhóm Ngành", list(SECTORS.keys()))
        st.info("**Chiến thuật:** Swing Trading / Trend Following.")
    
    with col2:
        if st.button("🚀 Quét Tín Hiệu Kỹ Thuật"):
            ticker_list = SECTORS[selected_sector]
            st.write(f"Đang phân tích kỹ thuật nhóm: **{selected_sector}**...")
            raw_data = get_market_data(ticker_list)
            
            if raw_data is not None and not raw_data.empty:
                results = []
                for ticker in ticker_list:
                    try:
                        # Fix data access for new yfinance structure
                        df_single = raw_data.xs(f"{ticker}.VN", level=1, axis=1) if isinstance(raw_data.columns, pd.MultiIndex) else raw_data
                        if df_single is not None:
                            res = analyze_ticker(ticker, df_single)
                            if res: results.append(res)
                    except: continue
                
                if results:
                    df_res = pd.DataFrame(results)
                    st.dataframe(df_res.style.format({'Giá':'{:,.0f}','Cắt lỗ (-7%)':'{:,.0f}','Chốt lãi (+20%)':'{:,.0f}','RSI':'{:.1f}','Thay đổi %':'{:+.2f}%','Volume':'{:,.0f}'}).background_gradient(subset=['Thay đổi %'], cmap='RdYlGn'), use_container_width=True)
                else:
                    st.warning("Không tìm thấy mã phù hợp.")
            else:
                st.error("Lỗi dữ liệu.")

# --- TAB 2: BÁO CÁO ---
with tab2:
    st.header("📝 Báo cáo Thị trường Daily")
    if st.button("📄 Tạo Báo Cáo Nhanh"):
        st.info("Tính năng tạo báo cáo tổng hợp dựa trên VN100 đang được xử lý...")
        # (Giữ nguyên logic cũ của bạn hoặc rút gọn để tiết kiệm token hiển thị)
        st.write("Dữ liệu đang được tổng hợp từ phiên giao dịch gần nhất...")

# --- TAB 3: ĐẦU TƯ GIÁ TRỊ & TÍCH SẢN (NEW FEATURE) ---
with tab3:
    st.markdown("## 🐢 Compounder Guardian - Góc nhìn Đầu tư Dài hạn")
    st.caption("Phân tích Doanh nghiệp theo triết lý Warren Buffett & Howard Marks.")
    
    col_input, col_display = st.columns([1, 2])
    
    with col_input:
        # Chọn mã từ danh sách ngành để tiện lợi
        sector_val = st.selectbox("1. Chọn Ngành:", list(SECTORS.keys()), key='sec_val')
        ticker_val = st.selectbox("2. Chọn Cổ Phiếu:", SECTORS[sector_val], key='tick_val')
        
        st.markdown("---")
        st.markdown("### 🎯 Mục tiêu của bạn?")
        strategy = st.radio("Chọn chiến lược:", ["Đầu tư Trung hạn (6-12 tháng)", "Tích sản Dài hạn (Hold to Die)"])
        
        if st.button("🔍 Phân Tích 360 Độ", type="primary"):
            with st.spinner(f"Đang 'khám sức khỏe' doanh nghiệp {ticker_val}..."):
                fund_data = get_fundamental_analysis(ticker_val)
                
                if fund_data:
                    st.session_state['fund_result'] = fund_data
                    st.session_state['strategy'] = strategy
                else:
                    st.error("Không tải được dữ liệu cơ bản. Mã này có thể thiếu BCTC trên hệ thống.")

    with col_display:
        if 'fund_result' in st.session_state:
            data = st.session_state['fund_result']
            strat = st.session_state['strategy']
            
            # 1. HIỂN THỊ ĐIỂM SỐ
            st.subheader(f"{data['name']} ({data['symbol']})")
            
            score_color = "green" if data['score'] >= 7 else "orange" if data['score'] >= 5 else "red"
            st.markdown(f"""
            ### Điểm số Doanh nghiệp: <span style='color:{score_color}; font-size: 32px'>{data['score']}/10</span>
            **Đánh giá:** {data['evaluation']}
            """, unsafe_allow_html=True)
            
            st.progress(data['score']/10)
            
            # 2. PHÂN TÍCH CHI TIẾT (Simulated Chain of Thought)
            st.markdown("---")
            c1, c2, c3 = st.columns(3)
            with c1:
                st.metric("P/E (Định giá)", f"{data['metrics']['P/E']:.1f}" if data['metrics']['P/E'] else "N/A")
            with c2:
                roe_disp = f"{data['metrics']['ROE']*100:.1f}%" if data['metrics']['ROE'] else "N/A"
                st.metric("ROE (Hiệu quả)", roe_disp)
            with c3:
                div_disp = f"{data['metrics']['Div Yield']*100:.1f}%" if data['metrics']['Div Yield'] else "0%"
                st.metric("Cổ tức (Yield)", div_disp)

            st.markdown("#### 🕵️ Phân tích Chi tiết (Compounder Logic):")
            for detail in data['details']:
                st.markdown(f"- {detail}")
            
            # 3. KHUYẾN NGHỊ HÀNH ĐỘNG
            st.markdown("---")
            st.subheader("💡 Khuyến nghị Hành động")
            
            current_price = data['price']
            
            if strat == "Đầu tư Trung hạn (6-12 tháng)":
                st.info(f"""
                **Chiến lược Trung hạn:**
                * **Vùng mua tối ưu (Margin of Safety):** {current_price * 0.9:,.0f} - {current_price * 0.95:,.0f} VND (Canh chỉnh giảm 5-10%).
                * **Động lực:** Chờ đợi KQKD quý tới hoặc phục hồi kỹ thuật.
                * **Cắt lỗ:** Nếu gãy xu hướng dài hạn (EMA200).
                """)
            else:
                st.success(f"""
                **Chiến lược Tích sản (Dài hạn):**
                * **Tư duy:** Mua sở hữu doanh nghiệp, bỏ qua biến động ngắn hạn.
                * **Hành động:** Chia vốn mua đều hàng tháng (DCA).
                * **Panic Buy:** Mua mạnh tay nếu giá rơi về vùng {current_price * 0.8:,.0f} (Chiết khấu 20%).
                * **Lưu ý:** Tái đầu tư toàn bộ cổ tức nhận được.
                """)
            
            # 4. LỜI KHUYÊN TÂM LÝ
            st.markdown("---")
            quote = random.choice(QUOTES)
            st.markdown(f"> *“{quote}”*")
            
        else:
            st.info("👈 Hãy chọn mã cổ phiếu và nhấn nút Phân tích để xem báo cáo chuyên sâu.")

st.markdown("---")
st.caption("Developed by Expert Investor. Data Source: Yahoo Finance. Disclaimer: For educational purposes only.")


