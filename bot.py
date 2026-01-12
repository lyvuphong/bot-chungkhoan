import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Trading Expert (Fixed)", layout="wide", page_icon="⭐")
st.title("⭐ HỆ THỐNG CHẤM ĐIỂM CỔ PHIẾU CHUYÊN NGHIỆP (VIP 100)")
st.caption("Phiên bản: Ổn định (Fix lỗi chọn biểu đồ) | Dữ liệu: Yahoo Finance")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # NGÂN HÀNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    # CHỨNG KHOÁN
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    # BẤT ĐỘNG SẢN & KCN
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    # THÉP
    steel = ["HPG", "HSG", "NKG"]
    # VN30 KHÁC
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH"]
    # MIDCAP CHIẾN LƯỢC
    midcap = ["VHC", "ANV", "FMC", "DGC", "CSV", "REE", "PC1", "GEG", "GMD", "HAH", "PVT", "DGW", "FRT", "PET", "PVS", "PVD", "VOS"]

    selected_symbols = []
    if "Ngân hàng" in sector_choice: selected_symbols += banks
    if "Chứng khoán" in sector_choice: selected_symbols += securities
    if "Bất động sản" in sector_choice: selected_symbols += real_estate
    if "Thép" in sector_choice: selected_symbols += steel
    if "VN30" in sector_choice: selected_symbols += vn30_other
    if "Midcap" in sector_choice: selected_symbols += midcap
    
    if "QUÉT TOÀN BỘ (ALL)" in sector_choice:
        selected_symbols = banks + securities + real_estate + steel + vn30_other + midcap

    unique_symbols = list(set(selected_symbols))
    return [f"{sym}.VN" for sym in unique_symbols]

# --- 3. HÀM PHÂN TÍCH (CORE LOGIC) ---
def analyze_vip_score(symbol):
    try:
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 200: return None

        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        
        latest = df.iloc[-1]
        
        if latest['Close'] < 5000 or latest['Volume'] < 50000: return None

        # Tính toán
        df_3m = df.tail(60)
        max_3m = df_3m['High'].max()
        min_3m = df_3m['Low'].min()
        fluctuation = (max_3m - min_3m) / min_3m
        
        # Trend
        is_uptrend_mid = latest['SMA_20'] > latest['SMA_50']
        is_uptrend_long = latest['Close'] > latest['SMA_200']
        dist_ma20 = (latest['Close'] - latest['SMA_20']) / latest['SMA_20']
        
        # Chấm điểm
        score = 0
        details = []

        # A. TREND
        if is_uptrend_mid: score += 15
        if latest['Close'] > latest['SMA_20']: score += 10
        if is_uptrend_long: 
            score += 15
            details.append("Trend Dài hạn Tốt")
        if dist_ma20 > 0.15: 
            score -= 10
            details.append("⚠️ Giá xa nền")

        # B. TÍCH LŨY
        if fluctuation < 0.10: 
            score += 40
            details.append(f"Nền Siêu Chặt ({round(fluctuation*100,1)}%)")
        elif fluctuation < 0.15: 
            score += 30
            details.append(f"Nền Chuẩn ({round(fluctuation*100,1)}%)")
        elif fluctuation < 0.25: 
            score += 10
            details.append("Nền lỏng")
            
        # C. MOMENTUM
        if latest['Volume'] > df['Volume'].tail(20).mean():
            score += 10
            details.append("Tiền vào")
        if 50 <= latest['RSI_14'] <= 70: score += 10

        # Xếp hạng
        action = "THEO DÕI"
        if score >= 80: action = "MUA MẠNH (STRONG BUY)"
        elif score >= 70: action = "MUA THĂM DÒ (BUY)"
        elif score < 50: action = "BÁN / TRÁNH XA"

        stop_loss = int(min_3m * 0.98)
        target = int(latest['Close'] * 1.15)

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm VIP": score,
            "Xếp hạng": action,
            "Lý do": ", ".join(details),
            "Cắt Lỗ": f"{stop_loss:,}",
            "Chốt Lời": f"{target:,}",
            "Dataframe": df,
            "Box_High": max_3m,
            "Box_Low": min_3m
        }
    except:
        return None

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='black', width=1, dash='dot'), name='MA200'))
    fig.add_hrect(y0=data['Box_Low'], y1=data['Box_High'], line_width=0, fillcolor="yellow", opacity=0.15, annotation_text="Vùng Gom Hàng")
    
    fig.update_layout(title=f"CHART KỸ THUẬT: {symbol} ({data['Điểm VIP']}đ)", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH (ĐÃ SỬA LỖI SESSION STATE) ---
with st.sidebar:
    st.header("🔍 BỘ LỌC CHUYÊN GIA")
    
    sector_options = ["QUÉT TOÀN BỘ (ALL)", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "VN30", "Midcap"]
    selected_sectors = st.multiselect("Chọn ngành:", sector_options, default=["QUÉT TOÀN BỘ (ALL)"])
    
    min_vip_score = st.slider("Điểm VIP tối thiểu", 0, 100, 70)
    
    # Nút bấm kích hoạt phân tích
    if st.button("CHẤM ĐIỂM THỊ TRƯỜNG 🚀", type="primary"):
        # Khi bấm nút, chúng ta lưu trạng thái "đang xử lý"
        st.session_state['trigger_scan'] = True

# LOGIC XỬ LÝ DỮ LIỆU
if st.session_state.get('trigger_scan'):
    symbols = get_stock_universe(selected_sectors)
    
    # Chỉ chạy quét nếu chưa có data hoặc nút vừa được bấm
    with st.spinner(f"AI đang chấm điểm {len(symbols)} mã... Vui lòng đợi 1-2 phút..."):
        results = []
        progress_bar = st.progress(0)
        
        for i, sym in enumerate(symbols):
            data = analyze_vip_score(sym)
            if data and data['Điểm VIP'] >= min_vip_score:
                results.append(data)
            progress_bar.progress((i+1)/len(symbols))
            
        # LƯU KẾT QUẢ VÀO SESSION STATE (BỘ NHỚ ĐỆM)
        # Đây là bước quan trọng nhất để sửa lỗi
        if results:
            df_res = pd.DataFrame(results).sort_values(by="Điểm VIP", ascending=False)
            st.session_state['scan_results'] = df_res
            st.session_state['full_data'] = results # Lưu data gốc để vẽ chart
        else:
            st.session_state['scan_results'] = None
            
    # Tắt cờ trigger để tránh chạy lại không cần thiết
    st.session_state['trigger_scan'] = False 

# LOGIC HIỂN THỊ (Sử dụng dữ liệu từ Session State)
if 'scan_results' in st.session_state and st.session_state['scan_results'] is not None:
    df_res = st.session_state['scan_results']
    full_data = st.session_state['full_data']
    
    st.success(f"✅ Đã tìm thấy {len(df_res)} mã tiềm năng!")
    
    # 1. Bảng kết quả
    st.dataframe(
        df_res[['Mã', 'Giá', 'Điểm VIP', 'Xếp hạng', 'Lý do', 'Cắt Lỗ', 'Chốt Lời']],
        use_container_width=True,
        height=400
    )
    
    st.divider()
    
    # 2. Khu vực soi Chart (Tương tác ở đây sẽ không bị mất dữ liệu nữa)
    st.subheader("🧐 SOI CHI TIẾT & BIỂU ĐỒ")
    col1, col2 = st.columns([1,3])
    
    with col1:
        # Danh sách mã để chọn
        stock_list = df_res['Mã'].tolist()
        if stock_list:
            # Selectbox thay vì Radio cho gọn nếu list dài
            choice = st.radio("Chọn mã xem chart:", stock_list, key="chart_selector")
            
            # Lấy thông tin mã đang chọn
            item = next((x for x in full_data if x["Mã"] == choice), None)
            
            if item:
                st.metric("Điểm Chuyên Gia", f"{item['Điểm VIP']}/100")
                st.metric("Khuyến nghị", item['Xếp hạng'])
                st.info(f"Lý do: {item['Lý do']}")
        
    with col2:
        if 'item' in locals() and item:
            plot_chart(item)

elif 'scan_results' in st.session_state and st.session_state['scan_results'] is None:
    st.warning("Không tìm thấy mã nào đạt chuẩn.")
else:
    st.info("👈 Hãy chọn ngành và bấm nút 'CHẤM ĐIỂM' để bắt đầu.")
