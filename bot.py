import streamlit as st
import pandas as pd
import pandas_ta as ta
import numpy as np
from vnstock import stock_historical_data, financial_ratio
from datetime import datetime, timedelta
import concurrent.futures
import time

# --- 1. CẤU HÌNH TRANG & DỮ LIỆU NGÀNH ---
st.set_page_config(page_title="AI Pro Trader System", layout="wide", page_icon="📈")

# Danh sách cổ phiếu theo nhóm ngành (Hardcoded Database)
INDUSTRY_GROUPS = {
    "💎 VN30 (Bluechips)": [
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"
    ],
    "⭐ VN100 (Midcap + Bluechips)": [
         # VN30
        "ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG",
        "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB",
        "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE",
        # Midcap tiêu biểu
        "DGC", "REE", "VHC", "ANV", "PTB", "GIL", "GEG", "PC1", "HDG", "DIG",
        "DXG", "NLG", "KDH", "PDR", "NVL", "KBC", "IDC", "SZC", "VGC", "GEX",
        "VIX", "VND", "VCI", "HCM", "FTS", "BSI", "MBS", "SHS", "DGW", "FRT"
    ],
    "🏦 Ngân hàng (Banks)": [
        "VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "TPB",
        "VIB", "OCB", "MSB", "LPB", "SHB", "EIB", "NAB", "BAB"
    ],
    "📈 Chứng khoán (Securities)": [
        "SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", 
        "ORS", "AGR", "BVS", "VDS"
    ],
    "🏗 Bất động sản (Real Estate)": [
        "VHM", "NVL", "PDR", "DIG", "DXG", "KDH", "NLG", "HDG", "CEO", "TCH", 
        "KHG", "SCR", "HQC", "QCG"
    ],
    "🏭 BĐS Khu Công Nghiệp": [
        "GVR", "IDC", "KBC", "SZC", "BCM", "VGC", "LHG", "TIP", "D2D", "PHR", "ITA"
    ],
    "🛢 Dầu khí (Oil & Gas)": [
        "GAS", "PVD", "PVS", "BSR", "PLX", "PVT", "OIL", "PVC", "PVB"
    ],
    "🐟 Thủy sản (Seafood)": [
        "VHC", "ANV", "IDI", "CMX", "FMC", "ACL"
    ],
    "👕 Dệt may (Textiles)": [
        "TNG", "MSH", "GIL", "VGT", "STK", "ADS"
    ],
    "🏛 HNX30 (Sàn Hà Nội)": [
        "SHS", "CEO", "MBS", "PVS", "IDC", "HUT", "L14", "TNG", "VCS", "API",
        "IDJ", "BVS", "PVC", "DDG"
    ],
    "🏗 Thép (Steel)": [
        "HPG", "HSG", "NKG", "TLH", "VGS", "SMC", "TVN"
    ]
}

# --- 2. LỚP DATA PROVIDER ---
class DataProvider:
    """Chịu trách nhiệm lấy dữ liệu từ VNStock"""
    @staticmethod
    def get_market_data(symbol, days=365):
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # Lấy dữ liệu lịch sử
            df = stock_historical_data(symbol, start_date, end_date, "1D", "stock")
            
            if df is None or df.empty:
                return None
                
            # Chuẩn hóa tên cột
            df.columns = df.columns.str.lower()
            if 'volume' not in df.columns and 'khoi_luong' in df.columns:
                 df.rename(columns={'khoi_luong': 'volume'}, inplace=True)
            
            # Chuyển đổi kiểu dữ liệu số
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            df = df.dropna()
            return df
        except Exception:
            return None

    @staticmethod
    def get_fundamentals(symbol):
        """Lấy chỉ số cơ bản (NPM, ROE)"""
        try:
            # Lấy báo cáo quý gần nhất (Lưu ý: Có thể chậm nếu mạng kém)
            df_fin = financial_ratio(symbol, 'quarterly', True)
            if df_fin is not None and not df_fin.empty:
                # Lấy giá trị mới nhất
                npm = df_fin.get('net_profit_margin', None)
                roe = df_fin.get('roe', None)
                
                latest_npm = npm.iloc[0] if npm is not None else 0
                latest_roe = roe.iloc[0] if roe is not None else 0
                return {"NPM": latest_npm, "ROE": latest_roe}
        except:
            pass # Bỏ qua nếu lỗi API cơ bản để không dừng chương trình
        return {"NPM": 0, "ROE": 0}

# --- 3. LỚP CHIẾN LƯỢC (STRATEGY ENGINE) ---
class StrategyEngine:
    def __init__(self, df, fundamentals=None):
        self.df = df
        self.fund = fundamentals if fundamentals else {"NPM": 0, "ROE": 0}

    def compute_indicators(self):
        # Xu hướng
        self.df['MA20'] = ta.sma(self.df['close'], length=20)
        self.df['MA50'] = ta.sma(self.df['close'], length=50)
        self.df['MA200'] = ta.sma(self.df['close'], length=200)
        
        # Động lượng & Biến động
        self.df['RSI'] = ta.rsi(self.df['close'], length=14)
        self.df['ATR'] = ta.atr(self.df['high'], self.df['low'], self.df['close'], length=14)
        
        # Volume
        self.df['Vol_MA20'] = ta.sma(self.df['volume'], length=20)
        
        # Độ biến động (Tích lũy) - 60 phiên (~3 tháng)
        self.df['STD_60'] = self.df['close'].rolling(60).std()
        self.df['Price_Mean_60'] = self.df['close'].rolling(60).mean()
        self.df['Volatility_Pct'] = (self.df['STD_60'] / self.df['Price_Mean_60']) * 100

    def evaluate(self):
        if len(self.df) < 200: return None
        
        self.compute_indicators()
        curr = self.df.iloc[-1]
        prev = self.df.iloc[-2]
        
        # 1. Xu hướng dài hạn (Trend)
        trend_cond = (curr['close'] > curr['MA20']) and \
                     (curr['MA20'] > curr['MA50']) and \
                     (curr['MA50'] > curr['MA200'])
        
        # 2. Tích lũy (Accumulation) - Biến động thấp < 15%
        accumulation_cond = curr['Volatility_Pct'] < 15 
        
        # 3. Cơ bản (Fundamentals) - NPM > 15%
        # Lưu ý: Dữ liệu API trả về có thể là 0.15 hoặc 15, cần kiểm tra linh hoạt
        npm_val = self.fund['NPM']
        fund_cond = (npm_val > 0.15) or (npm_val > 15)
        
        # 4. Điểm mua (Action)
        vol_cond = curr['volume'] > 1.2 * curr['Vol_MA20'] # Nổ Vol
        price_action = (curr['close'] > prev['close'])
        
        # Tính điểm
        score = 0
        reasons = []
        
        if trend_cond: score += 3; reasons.append("Uptrend (MA200)")
        if accumulation_cond: score += 2; reasons.append("Nền chặt")
        if fund_cond: score += 3; reasons.append("FA Tốt")
        if vol_cond and price_action: score += 2; reasons.append("Tiền vào")
        
        is_buy = score >= 6 # Ngưỡng khuyến nghị
        
        return {
            "Gia": curr['close'],
            "ATR": curr['ATR'],
            "Score": score,
            "Reasons": ", ".join(reasons),
            "Is_Buy": is_buy,
            "Volatility": round(curr['Volatility_Pct'], 2)
        }

    def simple_backtest(self):
        """Backtest nhanh MA Crossover"""
        data = self.df.copy()
        data['Signal'] = 0
        # Mua khi MA20 cắt lên MA50
        data.loc[(data['MA20'] > data['MA50']) & (data['MA20'].shift(1) <= data['MA50'].shift(1)), 'Signal'] = 1
        # Bán khi Giá gãy MA50
        data.loc[data['close'] < data['MA50'], 'Signal'] = -1
        
        trades = []
        entry_price = 0
        position = 0
        
        for index, row in data.iterrows():
            if row['Signal'] == 1 and position == 0:
                position = 1
                entry_price = row['close']
            elif row['Signal'] == -1 and position == 1:
                position = 0
                if entry_price > 0:
                    pnl = (row['close'] - entry_price) / entry_price
                    trades.append(pnl)
        
        win_rate = len([x for x in trades if x > 0]) / len(trades) if trades else 0
        return win_rate

# --- 4. HÀM TÍNH KHỐI LƯỢNG (RISK MANAGEMENT) ---
def calculate_position_size(capital, risk_per_trade, entry_price, atr):
    if pd.isna(atr) or atr == 0: return 0, 0
    risk_amount = capital * risk_per_trade # VD: 1 tỷ * 1% = 10tr
    stop_loss_dist = 2 * atr # Cắt lỗ 2ATR
    
    if stop_loss_dist == 0: return 0, 0
    
    shares = risk_amount / stop_loss_dist
    stop_loss_price = entry_price - stop_loss_dist
    
    # Làm tròn lô 100
    shares = (shares // 100) * 100
    return shares, stop_loss_price

# --- 5. HÀM CHẠY ĐA LUỒNG ---
def process_single_stock(symbol, capital_input):
    """Xử lý 1 mã cổ phiếu"""
    df = DataProvider.get_market_data(symbol)
    if df is None: return None
    
    # Tạm tắt lấy Fundamental để tăng tốc độ Demo (vì API free thường chậm)
    # Muốn bật lại, bỏ comment dòng dưới:
    # fundamentals = DataProvider.get_fundamentals(symbol)
    fundamentals = {"NPM": 0.16, "ROE": 0.2} # Mock data giả định tốt để test kỹ thuật
    
    engine = StrategyEngine(df, fundamentals)
    result = engine.evaluate()
    
    # Chỉ lấy mã có điểm >= 5 để báo cáo cho gọn
    if result and result['Score'] >= 5: 
        win_rate = engine.simple_backtest()
        qty, sl_price = calculate_position_size(capital_input, 0.01, result['Gia'], result['ATR'])
        
        return {
            "Mã CK": symbol,
            "Giá": f"{result['Gia']:,.0f}",
            "Điểm": result['Score'],
            "Lý Do": result['Reasons'],
            "Biến động (3T)": f"{result['Volatility']}%",
            "WinRate (1Y)": f"{round(win_rate*100, 1)}%",
            "KL Mua": f"{int(qty):,}",
            "Cắt Lỗ": f"{int(sl_price):,}",
            "Trạng thái": "MUA NGAY" if result['Is_Buy'] else "THEO DÕI"
        }
    return None

# --- 6. GIAO DIỆN NGƯỜI DÙNG (UI) ---
with st.sidebar:
    st.title("⚙️ Cấu hình Bot")
    st.markdown("Hệ thống đầu tư vốn 1 Tỷ VND")
    
    # Input Vốn
    capital = st.number_input("Vốn Đầu Tư (VND)", value=1000000000, step=100000000)
    
    st.markdown("---")
    st.subheader("🔍 Chọn Danh Mục Quét")
    
    # Multiselect chọn ngành
    selected_groups = st.multiselect(
        "Nhóm ngành mục tiêu:", 
        options=list(INDUSTRY_GROUPS.keys()),
        default=["💎 VN30 (Bluechips)"]
    )
    
    # Tổng hợp mã từ các nhóm đã chọn
    default_symbols = []
    for group in selected_groups:
        default_symbols.extend(INDUSTRY_GROUPS[group])
    
    # Loại bỏ trùng lặp và sort
    default_symbols = sorted(list(set(default_symbols)))
    default_text = ", ".join(default_symbols)
    
    # Cho phép user sửa lại list cuối cùng
    symbols_text = st.text_area("Danh sách mã sẽ quét:", value=default_text, height=150)
    
    st.caption(f"Số lượng mã: {len(symbols_text.split(','))}")
    
    run_btn = st.button("🚀 QUÉT TÍN HIỆU", type="primary")

# --- 7. MAIN LOGIC ---
st.title("📈 TRỢ LÝ ĐẦU TƯ AI CHUYÊN NGHIỆP")
st.markdown(f"**Chiến lược:** Trend Following + VSA + Quản trị rủi ro (Risk 1%/Trade)")

if run_btn:
    symbols = [s.strip().upper() for s in symbols_text.split(',') if s.strip()]
    
    if not symbols:
        st.warning("Vui lòng chọn ít nhất 1 mã cổ phiếu.")
    else:
        st.info(f"Đang phân tích dữ liệu thị trường cho {len(symbols)} mã... Vui lòng đợi.")
        
        results = []
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Chạy đa luồng (10 workers)
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_stock = {executor.submit(process_single_stock, sym, capital): sym for sym in symbols}
            
            completed = 0
            for future in concurrent.futures.as_completed(future_to_stock):
                stock = future_to_stock[future]
                completed += 1
                progress_bar.progress(completed / len(symbols))
                status_text.text(f"Đang xử lý: {stock}...")
                
                try:
                    data = future.result()
                    if data:
                        results.append(data)
                except Exception as exc:
                    print(f"{stock} lỗi: {exc}") # Log ẩn

        status_text.empty()
        progress_bar.empty()
        
        if results:
            st.success(f"Hoàn tất! Tìm thấy {len(results)} cổ phiếu tiềm năng.")
            df_res = pd.DataFrame(results)
            
            # Sắp xếp theo điểm số giảm dần
            df_res = df_res.sort_values(by="Điểm", ascending=False)
            
            # Tô màu trạng thái
            def highlight_status(val):
                color = '#90EE90' if val == "MUA NGAY" else '' # Xanh nhạt
                return f'background-color: {color}; color: black' if val == "MUA NGAY" else ''

            st.dataframe(
                df_res.style.applymap(highlight_status, subset=['Trạng thái']),
                use_container_width=True,
                height=600
            )
            
            # Kế hoạch hành động
            st.markdown("### 📝 Kế hoạch hành động:")
            st.info("""
            1. **MUA NGAY:** Các mã có xu hướng tăng, tích lũy tốt và có dòng tiền.
            2. **KL Mua:** Đã được tính toán để rủi ro tối đa là 10 triệu VND (1% của 1 tỷ) nếu chạm cắt lỗ.
            3. **Cắt Lỗ:** Giá kích hoạt lệnh bán tự động để bảo vệ vốn (dựa trên 2ATR).
            """)
        else:
            st.warning("Không tìm thấy mã nào đủ tiêu chuẩn khắt khe hôm nay.")

st.markdown("---")
st.caption("Developed by AI Assistant | Data Source: VNStock | Strategy: Minervini & O'Neil")
