import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import Vnstock  # <--- DÙNG CLASS MỚI CỦA VNSTOCK 3
from datetime import datetime, timedelta
import concurrent.futures

# --- 1. CẤU HÌNH ---
st.set_page_config(page_title="AI Pro Trader System", layout="wide", page_icon="📈")

INDUSTRY_GROUPS = {
    "💎 VN30 (Bluechips)": ["ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB", "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"],
    "🏦 Ngân hàng": ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "TPB", "VIB", "MSB", "LPB", "SHB", "EIB"],
    "📈 Chứng khoán": ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS", "AGR"],
    "🏗 Bất động sản": ["VHM", "NVL", "PDR", "DIG", "DXG", "KDH", "NLG", "CEO", "TCH", "HQC", "QCG"],
    "🏭 Khu Công Nghiệp": ["GVR", "IDC", "KBC", "SZC", "BCM", "VGC", "LHG", "ITA"],
    "🛢 Dầu khí": ["GAS", "PVD", "PVS", "BSR", "PLX", "PVT", "OIL"],
    "🐟 Thủy sản": ["VHC", "ANV", "IDI", "CMX", "FMC"],
    "🏗 Thép": ["HPG", "HSG", "NKG", "TLH", "VGS"]
}

# --- 2. XỬ LÝ DỮ LIỆU (CHUẨN MỚI VNSTOCK 3) ---
class DataProvider:
    @staticmethod
    def get_market_data(symbol, days=365):
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # --- SỬA LỖI: Dùng cú pháp mới ---
            # Thay vì import stock_historical_data, ta khởi tạo đối tượng Vnstock
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or df.empty: return None
            
            # Chuẩn hóa tên cột về chữ thường (open, high, low, close)
            df.columns = df.columns.str.lower()
            if 'time' in df.columns: df.rename(columns={'time': 'date'}, inplace=True)
            
            # Ép kiểu số
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception:
            return None

# --- 3. CHIẾN LƯỢC ---
class StrategyEngine:
    def __init__(self, df):
        self.df = df

    def evaluate(self):
        if len(self.df) < 100: return None
        
        df = self.df
        # Chỉ báo
        df['MA20'] = ta.sma(df['close'], length=20)
        df['MA50'] = ta.sma(df['close'], length=50)
        df['MA200'] = ta.sma(df['close'], length=200)
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['Vol_MA20'] = ta.sma(df['volume'], length=20)
        
        # Tích lũy (Biến động thấp)
        df['STD_60'] = df['close'].rolling(60).std()
        df['Mean_60'] = df['close'].rolling(60).mean()
        df['Volat_Pct'] = (df['STD_60'] / df['Mean_60']) * 100
        
        curr = df.iloc[-1]
        
        # Logic
        trend = (curr['close'] > curr['MA20']) and (curr['MA20'] > curr['MA50'])
        tight = curr['Volat_Pct'] < 15 if not pd.isna(curr['Volat_Pct']) else False
        vol_up = curr['volume'] > 1.0 * curr['Vol_MA20']
        
        score = 0
        reasons = []
        if trend: score += 3; reasons.append("Uptrend")
        if tight: score += 2; reasons.append("Nền chặt")
        if vol_up: score += 2; reasons.append("Tiền vào")
        
        return {
            "price": curr['close'],
            "score": score,
            "reasons": ", ".join(reasons),
            "atr": curr['ATR'] if not pd.isna(curr['ATR']) else 0
        }

def process_stock(symbol, capital):
    df = DataProvider.get_market_data(symbol)
    if df is None: return None
    
    engine = StrategyEngine(df)
    res = engine.evaluate()
    
    if res and res['score'] >= 5:
        risk_amt = capital * 0.01
        sl_dist = 2 * res['atr'] if res['atr'] > 0 else res['price']*0.07
        qty = (risk_amt / sl_dist // 100) * 100
        
        return {
            "Mã": symbol,
            "Giá": f"{res['price']:,.0f}",
            "Điểm": res['score'],
            "Lý do": res['reasons'],
            "KL Mua": f"{int(qty):,}",
            "Cắt lỗ": f"{int(res['price'] - sl_dist):,.0f}"
        }
    return None

# --- 4. GIAO DIỆN ---
with st.sidebar:
    st.header("⚙️ Cấu hình")
    capital = st.number_input("Vốn (VND)", value=1000000000, step=100000000)
    
    selected_groups = st.multiselect("Chọn Ngành:", list(INDUSTRY_GROUPS.keys()), default=["💎 VN30 (Bluechips)"])
    symbols = []
    for g in selected_groups: symbols.extend(INDUSTRY_GROUPS[g])
    symbols = sorted(list(set(symbols)))
    
    if st.button("🚀 QUÉT NGAY"):
        st.info(f"Đang quét {len(symbols)} mã...")
        results = []
        bar = st.progress(0)
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as exe:
            futures = {exe.submit(process_stock, s, capital): s for s in symbols}
            for i, f in enumerate(concurrent.futures.as_completed(futures)):
                try:
                    data = f.result()
                    if data: results.append(data)
                except: pass
                bar.progress((i+1)/len(symbols))
        
        bar.empty()
        if results:
            st.success(f"Tìm thấy {len(results)} cơ hội!")
            st.dataframe(pd.DataFrame(results).sort_values("Điểm", ascending=False), use_container_width=True)
        else:
            st.warning("Không tìm thấy mã đạt chuẩn.")
