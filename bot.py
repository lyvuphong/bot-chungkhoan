import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Trading Pro (Yahoo Data)", layout="wide", page_icon="📈")
st.title("📈 TRỢ LÝ ĐẦU TƯ AI - PHIÊN BẢN QUỐC TẾ")
st.caption("Dữ liệu: Yahoo Finance (Realtime) | Ổn định trên mọi nền tảng")

# --- 2. DANH SÁCH CỔ PHIẾU (Thêm đuôi .VN cho Yahoo hiểu) ---
def get_symbol_list():
    raw_symbols = [
        "FPT", "MWG", "HPG", "VCB", "TCB", "MBB", "ACB", "STB", "VIP", "VRE",
        "VHM", "VIC", "MSN", "GAS", "POW", "PLX", "VNM", "SAB", "GVR", "KDH",
        "PDR", "SSI", "VCI", "HCM", "VND", "DGC", "DXG", "NKG", "HSG", "DBC",
        "FRT", "PNJ", "REE", "GEX", "VGC", "IDC", "KBC", "SZC", "PC1", "HDG"
    ]
    # Yahoo quy định cổ phiếu VN phải có đuôi .VN
    return [f"{sym}.VN" for sym in raw_symbols]

# --- 3. HÀM XỬ LÝ DỮ LIỆU ---
def analyze_stock_yahoo(symbol):
    try:
        # Lấy dữ liệu 1 năm gần nhất
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        # Tải dữ liệu từ Yahoo
        df = yf.download(symbol, start=start_date, end=end_date, progress=False)
        
        # Xử lý lỗi Multi-index của Yahoo (nếu có)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 50: return None

        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        # Lấy nến mới nhất (Loại bỏ dòng NaN cuối cùng nếu có)
        latest = df.iloc[-1]
        
        # --- CHẤM ĐIỂM ---
        score = 0
        reasons = []
        
        # Giá trị (Loại bỏ cổ phiếu rác giá < 5k)
        if latest['Close'] < 5000: return None

        # 1. Trend
        if latest['Close'] > latest['SMA_20']: score += 30
        if latest['SMA_20'] > latest['SMA_50']: 
            score += 20
            reasons.append("Xu hướng Tăng")
            
        # 2. RSI
        rsi_val = latest['RSI_14']
        if 40 <= rsi_val <= 70: 
            score += 30
            reasons.append("RSI Ổn định")
        elif rsi_val > 70:
            score += 10
            reasons.append("RSI Nóng")
            
        # 3. Volume (So với trung bình)
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol:
            score += 20
            reasons.append("Tiền vào")

        return {
            "Mã": symbol.replace(".VN", ""), # Bỏ đuôi .VN khi hiển thị cho đẹp
            "Giá": f"{int(latest['Close']):,}",
            "RSI": round(rsi_val, 1),
            "Điểm AI": score,
            "Tín hiệu": ", ".join(reasons) if reasons else "Yếu",
            "Dataframe": df
        }
    except Exception as e:
        return None

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(df, symbol):
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.update_layout(title=f"Biểu đồ: {symbol}", xaxis_rangeslider_visible=False, height=400)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN ---
with st.sidebar:
    st.header("🎛️ BỘ LỌC")
    min_score = st.slider("Điểm tối thiểu", 0, 100, 30)
    if st.button("QUÉT THỊ TRƯỜNG NGAY 🚀", type="primary"):
        run_app = True
    else:
        run_app = False

if run_app:
    symbols = get_symbol_list()
    status = st.status("Dang kết nối máy chủ Yahoo Finance...", expanded=True)
    
    results = []
    bar = status.progress(0)
    
    for i, sym in enumerate(symbols):
        data = analyze_stock_yahoo(sym)
        if data and data['Điểm AI'] >= min_score:
            results.append(data)
        bar.progress((i+1)/len(symbols))
        
    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm AI", ascending=False)
        st.success(f"Tìm thấy {len(df_res)} mã tiềm năng!")
        
        # Hiển thị bảng
        st.dataframe(
            df_res[['Mã', 'Giá', 'RSI', 'Điểm AI', 'Tín hiệu']], 
            use_container_width=True
        )
        
        # Chọn xem chart
        st.divider()
        choice = st.selectbox("🔍 Chọn mã xem biểu đồ:", df_res['Mã'])
        # Tìm lại data để vẽ
        target_data = next(item for item in results if item["Mã"] == choice)
        plot_chart(target_data['Dataframe'], choice)
        
    else:
        st.warning("Không tìm thấy mã nào. Hãy thử hạ điểm lọc xuống thấp hơn!")
else:
    st.info("👈 Bấm nút 'QUÉT THỊ TRƯỜNG' để bắt đầu.")
