import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import Vnstock # <--- CẬP NHẬT QUAN TRỌNG: Dùng Class mới
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

# --- 2. XỬ LÝ DỮ LIỆU (NÂNG CẤP VNSTOCK V3) ---
class DataProvider:
    @staticmethod
    def get_market_data(symbol, days=365):
        try:
            end_date = datetime.now().strftime('%Y-%m-%d')
            start_date = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%d')
            
            # --- CODE MỚI: Tương thích Vnstock mới nhất ---
            stock = Vnstock().stock(symbol=symbol, source='VCI')
            df = stock.quote.history(start=start_date, end=end_date, interval='1D')
            
            if df is None or df.empty: return None
            
            # Chuẩn hóa tên cột (Về dạng chữ thường: open, high, low, close)
            df.columns = df.columns.str.lower()
            
            # Đảm bảo các cột quan trọng tồn tại
            if 'time' in df.columns: df.rename(columns={'time': 'date'}, inplace=True)
            
            # Chuyển đổi dữ liệu sang số (tránh lỗi string)
            cols = ['open', 'high', 'low', 'close', 'volume']
            for col in cols:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
            
            return df
        except Exception as e:
            # print(f"Lỗi tải {symbol}: {e}")
            return None

# --- 3. CHIẾN LƯỢC (GIỮ NGUYÊN) ---
class StrategyEngine:
    def __init__(self, df):
        self.df = df

    def evaluate(self):
        if len(self.df) < 200: return None
        
        # Chỉ báo
        df = self.df
        df['MA20'] = ta.sma(df['close'], length=20)
        df['MA50'] = ta.sma(df['close'], length=50)
        df['MA200'] = ta.sma(df['close'], length=200)
        df['ATR'] = ta.atr(df['high'], df['low'], df['close'], length=14)
        df['Vol_MA20'] = ta.sma(df['volume'], length=20)
        
        # Tích lũy
        df['STD_60'] = df['close'].rolling(60).std()
        df['Mean_60'] = df['close'].rolling(60).mean()
        df['Volat_Pct'] = (df['STD_60'] / df['Mean_60']) * 100
        
        curr = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Logic Mua
        trend = (curr['close'] > curr['MA20']) and (curr['MA20'] > curr['MA50']) and (curr['MA50'] > curr['MA200'])
        tight = curr['Volat_Pct'] < 15
        vol_up = curr['volume'] > 1.2 * curr['Vol_MA20']
        breakout = (curr['close'] > prev['close'])
        
        score = 0
        reasons = []
        if trend: score += 3; reasons.append("Uptrend")
        if tight: score += 2; reasons.append("Nền chặt")
        if vol_up and breakout: score += 2; reasons.append("Tiền vào")
        
        # Backtest nhanh (Winrate MA20 cắt MA50)
        # Giản lược để tăng tốc độ
        return {
            "price": curr['close'],
            "score": score,
            "reasons": ", ".join(reasons),
            "atr": curr['ATR'],
            "volatility": round(curr['Volat_Pct'], 2)
        }

def process_stock(symbol, capital):
    df = DataProvider.get_market_data(symbol)
    if df is None: return None
    
    engine = StrategyEngine(df)
    res = engine.evaluate()
    
    if res and res['score'] >= 5:
        # Quản lý vốn: Rủi ro 1% NAV
        risk_amt = capital * 0.01
        sl_dist = 2 * res['atr']
        qty = (risk_amt / sl_dist // 100) * 100 if sl_dist > 0 else 0
        
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
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as exe:
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
