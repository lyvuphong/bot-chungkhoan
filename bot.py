import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Stock Sniper (Tích Lũy)", layout="wide", page_icon="🎯")
st.title("🎯 HỆ THỐNG SĂN CỔ PHIẾU TÍCH LŨY")
st.caption("Chiến lược: Tích lũy nền phẳng > 3 tháng + Dòng tiền bùng nổ")

# --- 2. DANH SÁCH CỔ PHIẾU ---
def get_symbol_list():
    raw_symbols = [
        "FPT", "MWG", "HPG", "VCB", "TCB", "MBB", "ACB", "STB", "VIP", "VRE",
        "VHM", "VIC", "MSN", "GAS", "POW", "PLX", "VNM", "SAB", "GVR", "KDH",
        "PDR", "SSI", "VCI", "HCM", "VND", "DGC", "DXG", "NKG", "HSG", "DBC",
        "FRT", "PNJ", "REE", "GEX", "VGC", "IDC", "KBC", "SZC", "PC1", "HDG",
        "ANV", "VHC", "FTS", "BSI", "CTS", "DIG", "CEO", "NVL", "HDB", "TPB",
        "DGW", "HAH", "VOS", "PVD", "PVS", "PVT", "VIX", "ORS", "TCH", "HUT"
    ]
    return [f"{sym}.VN" for sym in raw_symbols]

# --- 3. HÀM PHÂN TÍCH CHUYÊN SÂU ---
def analyze_stock_accumulation(symbol):
    try:
        # Lấy dữ liệu 1 năm để có đủ bối cảnh
        df = yf.download(symbol, period="1y", progress=False)
        
        # Xử lý Multi-index của Yahoo
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 70: return None # Cần ít nhất 3 tháng dữ liệu

        # Tính chỉ báo cơ bản
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        latest = df.iloc[-1]
        
        # --- LOGIC TÍNH TÍCH LŨY 3 THÁNG (QUAN TRỌNG) ---
        # Lấy 60 phiên gần nhất (~3 tháng)
        df_3m = df.tail(60)
        max_price_3m = df_3m['High'].max()
        min_price_3m = df_3m['Low'].min()
        
        # Tính biên độ biến động (Fluctuation)
        # Nếu (Đỉnh - Đáy) / Đáy < 20% => Là tích lũy chặt
        fluctuation = (max_price_3m - min_price_3m) / min_price_3m
        is_accumulation = fluctuation < 0.20  # Biên độ dưới 20%
        
        # --- HỆ THỐNG CHẤM ĐIỂM ---
        score = 0
        reasons = []

        # 1. Tiêu chí Tích Lũy (Ưu tiên số 1)
        if is_accumulation:
            score += 40
            reasons.append(f"Nền chặt 3M (Biên độ {round(fluctuation*100, 1)}%)")
        else:
            # Nếu không tích lũy chặt, nhưng đang Uptrend mạnh thì vẫn cộng điểm nhẹ
            if latest['Close'] > latest['SMA_50']: score += 10
            
        # 2. Tiêu chí Xu Hướng (MA20 > MA50)
        if latest['Close'] > latest['SMA_20'] and latest['SMA_20'] > latest['SMA_50']:
            score += 20
            reasons.append("Xu hướng Tăng")
            
        # 3. Tiêu chí Dòng Tiền (Volume hôm nay > TB 20 phiên)
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol:
            score += 20
            reasons.append("Tiền vào")
            
        # 4. RSI An toàn
        if 40 <= latest['RSI_14'] <= 70:
            score += 20

        # Loại cổ phiếu rác giá < 5k
        if latest['Close'] < 5000: return None

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Biên độ 3T": f"{round(fluctuation*100, 1)}%",
            "Điểm AI": score,
            "Tín hiệu": ", ".join(reasons) if reasons else "Theo dõi",
            "Dataframe": df
        }
    except Exception as e:
        return None

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(df, symbol):
    fig = go.Figure()
    
    # Vẽ nến
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Giá'))
    
    # Vẽ hộp tích lũy 3 tháng (vùng hỗ trợ/kháng cự gần nhất)
    df_3m = df.tail(60)
    max_3m = df_3m['High'].max()
    min_3m = df_3m['Low'].min()
    
    fig.add_hrect(y0=min_3m, y1=max_3m, line_width=0, fillcolor="yellow", opacity=0.2, annotation_text="Vùng biến động 3 tháng")
    
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    
    fig.update_layout(title=f"Biểu đồ kỹ thuật: {symbol}", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🔍 BỘ LỌC TÍCH LŨY")
    st.write("Tìm cổ phiếu đi ngang (Sideway) trong 3 tháng với biên độ hẹp.")
    
    min_score = st.slider("Điểm AI tối thiểu", 0, 100, 50)
    
    if st.button("QUÉT TÍN HIỆU 🌪️", type="primary"):
        run_app = True
    else:
        run_app = False

if run_app:
    symbols = get_symbol_list()
    status = st.status("📡 AI đang đo độ nén nền giá (3 tháng)...", expanded=True)
    
    results = []
    bar = status.progress(0)
    
    for i, sym in enumerate(symbols):
        data = analyze_stock_accumulation(sym)
        if data and data['Điểm AI'] >= min_score:
            results.append(data)
        bar.progress((i+1)/len(symbols))
        
    status.update(label="✅ Đã quét xong!", state="complete", expanded=False)
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm AI", ascending=False)
        
        # Thống kê nhanh
        st.success(f"Tìm thấy {len(df_res)} mã tiềm năng theo tiêu chí của bạn.")
        
        # Hiển thị bảng kết quả
        st.dataframe(
            df_res[['Mã', 'Giá', 'Biên độ 3T', 'Điểm AI', 'Tín hiệu']], 
            use_container_width=True
        )
        
        st.divider()
        st.subheader("🧐 SOI BIỂU ĐỒ & HỘP DARVAS")
        choice = st.selectbox("Chọn mã để xem vùng tích lũy:", df_res['Mã'])
        
        # Lấy data và vẽ chart
        target = next(item for item in results if item["Mã"] == choice)
        plot_chart(target['Dataframe'], choice)
        
    else:
        st.warning("Không tìm thấy mã nào. Hãy thử hạ điểm lọc xuống!")
else:
    st.info("👈 Bấm nút 'QUÉT TÍN HIỆU' để bắt đầu.")
