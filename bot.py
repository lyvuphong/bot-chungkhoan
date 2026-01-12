import streamlit as st
import pandas as pd
import pandas_ta as ta
from vnstock import * # 1. CẤU HÌNH GIAO DIỆN
st.set_page_config(page_title="Trợ Lý Đầu Tư AI", layout="wide")
st.title("📈 HỆ THỐNG TÍN HIỆU CỔ PHIẾU (MA20/MA50 Strategy)")

# 2. HÀM LẤY DỮ LIỆU VÀ PHÂN TÍCH
def analyze_stock(symbol):
    try:
        # Lấy dữ liệu lịch sử 1 năm
        # Lưu ý: vnstock có thể cập nhật, nếu lỗi dòng này hãy báo tôi
        df = stock_historical_data(symbol, "2025-01-01", "2026-01-12", "1D", "stock")
        
        if df is None or len(df) < 60: return None 
        
        # Tính chỉ báo kỹ thuật
        df['MA20'] = ta.sma(df['close'], length=20)
        df['MA50'] = ta.sma(df['close'], length=50)
        df['RSI'] = ta.rsi(df['close'], length=14)
        
        # Lấy giá trị mới nhất
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # --- CHIẾN LƯỢC ---
        # 1. Xu hướng tăng: Giá > MA20 > MA50
        trend_up = (latest['close'] > latest['MA20']) and (latest['MA20'] > latest['MA50'])
        
        # 2. Tín hiệu mua: Giá cắt lên MA20 HOẶC Giá nằm trên MA20
        # (Ở đây tôi để điều kiện mở rộng một chút để dễ bắt tín hiệu hơn)
        buy_signal = latest['close'] > latest['MA20']
        
        # 3. RSI an toàn
        safe_rsi = latest['RSI'] < 70
        
        if trend_up and safe_rsi:
            return {
                "Mã CK": symbol,
                "Giá": latest['close'],
                "MA20": latest['MA20'],
                "MA50": latest['MA50'],
                "RSI": round(latest['RSI'], 2),
                "Trạng thái": "MUA/NẮM GIỮ"
            }
        return None
    except Exception as e:
        return None

# 3. GIAO DIỆN CHÍNH (SIDEBAR)
st.sidebar.header("Bộ Lọc Cổ Phiếu")
input_symbols = st.sidebar.text_area("Nhập danh sách mã (cách nhau dấu phẩy)", "FPT, MBB, IDC, HPG, SSI, VNM, VCB")

# NÚT BẤM CHẠY
if st.sidebar.button("QUÉT TÍN HIỆU 🚀"):
    st.write(f"Đang phân tích dữ liệu thị trường cho: {input_symbols} ...")
    symbols_list = [x.strip() for x in input_symbols.split(',')]
    
    results = []
    # Tạo thanh tiến trình
    my_bar = st.progress(0)
    
    for i, sym in enumerate(symbols_list):
        data = analyze_stock(sym)
        if data:
            results.append(data)
        my_bar.progress((i + 1) / len(symbols_list))
        
    # HIỂN THỊ KẾT QUẢ
    if results:
        st.success(f"Tìm thấy {len(results)} cổ phiếu tiềm năng!")
        df_results = pd.DataFrame(results)
        st.dataframe(df_results)
    else:
        st.warning("Không tìm thấy mã nào đạt tiêu chuẩn hôm nay hoặc dữ liệu đang cập nhật.")

# Ghi chú chân trang
st.markdown("---")
st.markdown("**Ghi chú:** Dữ liệu được lấy từ VNStock. Chiến lược dựa trên MA20, MA50 và RSI.")