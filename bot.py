import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import *
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN CHUYÊN NGHIỆP ---
st.set_page_config(page_title="AI Trading Pro", layout="wide", page_icon="💎")

st.markdown("""
<style>
    .metric-card {background-color: #f0f2f6; border-radius: 10px; padding: 15px; text-align: center;}
    .stProgress > div > div > div > div { background-color: #4CAF50; }
</style>
""", unsafe_allow_html=True)

st.title("💎 HỆ THỐNG TRUY VẤN CỔ PHIẾU CHUYÊN SÂU (AI PRO)")
st.caption("Chiến lược: Trend Following + VSA Breakdown | Nguồn: VN100/HOSE")

# --- 2. HÀM XỬ LÝ DỮ LIỆU & CHẤM ĐIỂM ---
@st.cache_data(ttl=3600) # Lưu bộ nhớ đệm 1 tiếng để chạy nhanh hơn
def get_market_symbols():
    # Lấy danh sách VN30 và VNMID (Đại diện cho nhóm cổ phiếu tốt)
    # Để demo nhanh chúng ta dùng danh sách cứng các mã tốt nhất thị trường
    # Bạn có thể mở rộng list này sau
    return [
        "FPT", "MWG", "HPG", "VCB", "TCB", "MBB", "ACB", "STB", "VIP", "VRE",
        "VHM", "VIC", "MSN", "GAS", "POW", "PLX", "VNM", "SAB", "GVR", "KDH",
        "PDR", "SSI", "VCI", "HCM", "VND", "DGC", "DXG", "NKG", "HSG", "DBC",
        "FRT", "PNJ", "REE", "GEX", "VGC", "IDC", "KBC", "SZC", "PC1", "HDG",
        "ANV", "VHC", "FTS", "BSI", "CTS", "DIG", "CEO", "NVL", "HDB", "TPB"
    ]

def calculate_score(df):
    """Hàm chấm điểm sức mạnh cổ phiếu theo thang 100"""
    score = 0
    reasons = []
    
    latest = df.iloc[-1]
    prev = df.iloc[-2]
    
    # 1. Xu hướng dài hạn (MA50/MA200) - Trọng số: 30 điểm
    if latest['close'] > latest['MA50']:
        score += 20
        reasons.append("Trên MA50")
    if latest['close'] > latest['MA200']:
        score += 10
        reasons.append("Uptrend dài hạn")
        
    # 2. Dòng tiền (Volume) - Trọng số: 20 điểm
    vol_ratio = latest['volume'] / latest['VOL_MA20']
    if vol_ratio > 1.2: # Vol nổ > 120% trung bình
        score += 20
        reasons.append(f"Tiền vào mạnh (x{round(vol_ratio,1)})")
    elif vol_ratio > 0.8:
        score += 10
        
    # 3. Động lượng (RSI) - Trọng số: 20 điểm
    if 50 <= latest['RSI'] <= 70:
        score += 20 # Vùng tăng giá mạnh nhất
        reasons.append("RSI Sức mạnh")
    elif 40 < latest['RSI'] < 50:
        score += 10 # Vùng phục hồi
        
    # 4. Tích lũy (Bollinger Band) - Trọng số: 15 điểm
    # Bandwidth thấp nghĩa là đang thắt nút cổ chai (tích lũy)
    bandwidth = (latest['BBU_20_2.0'] - latest['BBL_20_2.0']) / latest['MA20']
    if bandwidth < 0.15: # Biên độ hẹp < 15%
        score += 15
        reasons.append("Nền giá chặt")
        
    # 5. Xu hướng ngắn hạn (MA20) - Trọng số: 15 điểm
    if latest['close'] > latest['MA20']:
        score += 15
        
    return score, ", ".join(reasons)

def analyze_stock_pro(symbol):
    try:
        # Lấy dữ liệu 1 năm
        df = stock_historical_data(symbol, "2025-01-01", "2026-01-13", "1D", "stock")
        if df is None or len(df) < 200: return None
        
        # Tính toán chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        
        # Tính Volume MA20 thủ công để tránh lỗi tên cột
        df['VOL_MA20'] = df['volume'].rolling(window=20).mean()
        
        # Lấy dữ liệu mới nhất
        df = df.dropna() # Loại bỏ dữ liệu lỗi
        if df.empty: return None
        
        latest = df.iloc[-1]
        
        # Logic lọc cơ bản: Giá > 10k & Vol > 100k (Loại bỏ rác)
        if latest['close'] < 10000 or latest['volume'] < 100000:
            return None

        # Chấm điểm
        confidence, reason = calculate_score(df)
        
        # Lấy thông tin cơ bản
        recommendation = "MUA MẠNH" if confidence >= 80 else ("MUA" if confidence >= 70 else "THEO DÕI")
        
        return {
            "Mã CK": symbol,
            "Giá": int(latest['close']),
            "Biến động": f"{round((latest['close'] - df.iloc[-2]['close'])/df.iloc[-2]['close']*100, 2)}%",
            "RSI": round(latest['RSI'], 1),
            "Khối lượng": f"{int(latest['volume']/1000)}K",
            "Độ tin cậy": confidence,
            "Lý do AI chọn": reason,
            "Khuyến nghị": recommendation
        }
    except Exception as e:
        return None

# --- 3. GIAO DIỆN ĐIỀU KHIỂN ---
with st.sidebar:
    st.header("⚙️ BỘ LỌC ĐIỀU KIỆN")
    min_score = st.slider("Độ tin cậy tối thiểu (%)", 50, 90, 70)
    top_n = st.number_input("Số lượng hiển thị", 10, 50, 20)
    st.markdown("---")
    if st.button("🚀 KÍCH HOẠT HỆ THỐNG", use_container_width=True):
        run_analysis = True
    else:
        run_analysis = False

# --- 4. MÀN HÌNH KẾT QUẢ ---
if run_analysis:
    symbols = get_market_symbols()
    st.info(f"Đang quét dữ liệu chuyên sâu {len(symbols)} mã Bluechip & Midcap tiềm năng...")
    
    results = []
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, sym in enumerate(symbols):
        status_text.text(f"AI đang phân tích: {sym} ({i+1}/{len(symbols)})")
        data = analyze_stock_pro(sym)
        if data and data['Độ tin cậy'] >= min_score:
            results.append(data)
        progress_bar.progress((i + 1) / len(symbols))
        
    status_text.empty()
    progress_bar.empty()
    
    if results:
        # Chuyển thành DataFrame và Sắp xếp
        df_res = pd.DataFrame(results)
        df_res = df_res.sort_values(by="Độ tin cậy", ascending=False).head(top_n)
        
        # Hiển thị Metrics tổng quan
        c1, c2, c3 = st.columns(3)
        c1.metric("Số mã đạt chuẩn", len(df_res))
        c2.metric("Điểm TB Top 5", f"{round(df_res.head(5)['Độ tin cậy'].mean(), 1)}/100")
        c3.metric("Mã mạnh nhất", df_res.iloc[0]['Mã CK'])
        
        st.subheader(f"🏆 DANH MỤC TOP {top_n} CỔ PHIẾU KHUYẾN NGHỊ")
        
        # Tô màu bảng kết quả
        def color_highlight(val):
            color = '#d4edda' if val == 'MUA MẠNH' else '#fff3cd' if val == 'MUA' else 'white'
            return f'background-color: {color}; color: black'

        st.dataframe(
            df_res.style.applymap(color_highlight, subset=['Khuyến nghị']),
            use_container_width=True,
            height=600
        )
        
        # Vẽ biểu đồ so sánh độ tin cậy
        st.subheader("📊 So sánh độ mạnh dòng tiền")
        st.bar_chart(df_res.set_index("Mã CK")["Độ tin cậy"])
        
    else:
        st.warning("Thị trường quá xấu! Không tìm thấy mã nào đủ điều kiện an toàn > 70%.")
else:
    st.info("👈 Vui lòng bấm nút 'KÍCH HOẠT HỆ THỐNG' ở thanh bên trái để bắt đầu quét.")
