import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Trading Expert (VIP Scoring)", layout="wide", page_icon="⭐")
st.title("⭐ HỆ THỐNG CHẤM ĐIỂM CỔ PHIẾU CHUYÊN NGHIỆP (VIP 100)")
st.caption("Chiến lược: An toàn trên hết | Trend Following + VSA Scoring")

# --- 2. KHO DỮ LIỆU (DATABASE) ---
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

# --- 3. HÀM CHẤM ĐIỂM CHUYÊN SÂU (CORE LOGIC) ---
def analyze_vip_score(symbol):
    try:
        # Lấy đủ dữ liệu để tính MA200
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 200: return None

        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        
        latest = df.iloc[-1]
        
        # --- BỘ LỌC CƠ BẢN ---
        if latest['Close'] < 5000 or latest['Volume'] < 50000: return None

        # --- TÍNH TOÁN CÁC BIẾN SỐ ---
        # 1. Tích lũy 3 tháng
        df_3m = df.tail(60)
        max_3m = df_3m['High'].max()
        min_3m = df_3m['Low'].min()
        fluctuation = (max_3m - min_3m) / min_3m
        
        # 2. Độ dốc xu hướng
        is_uptrend_short = latest['Close'] > latest['SMA_20']
        is_uptrend_mid = latest['SMA_20'] > latest['SMA_50']
        is_uptrend_long = latest['Close'] > latest['SMA_200']
        
        # 3. Khoảng cách giá với MA20 (Đo độ nóng)
        dist_ma20 = (latest['Close'] - latest['SMA_20']) / latest['SMA_20']
        
        # ==========================================
        # 🏆 HỆ THỐNG CHẤM ĐIỂM (VIP SCORE 100)
        # ==========================================
        score = 0
        details = []

        # A. XU HƯỚNG (Max 40đ)
        if is_uptrend_mid: 
            score += 15
        if is_uptrend_short: 
            score += 10
        if is_uptrend_long: 
            score += 15
            details.append("Trend Dài hạn Tốt")
        else:
            details.append("Dưới MA200 (Yếu)")
            
        # Trừ điểm nếu giá chạy quá xa nền (FOMO)
        if dist_ma20 > 0.15: # Lớn hơn 15% so với MA20
            score -= 10
            details.append("⚠️ Giá quá xa nền")

        # B. TÍCH LŨY (Max 40đ)
        if fluctuation < 0.10: # Siêu chặt < 10%
            score += 40
            details.append(f"Nền Siêu Chặt ({round(fluctuation*100,1)}%)")
        elif fluctuation < 0.15: # Chuẩn < 15%
            score += 30
            details.append(f"Nền Chuẩn ({round(fluctuation*100,1)}%)")
        elif fluctuation < 0.25: # Lỏng < 25%
            score += 10
            details.append("Nền hơi lỏng")
        else:
            score += 0 # Quá lỏng lẻo
            
        # C. DÒNG TIỀN & RSI (Max 20đ)
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol:
            score += 10
            details.append("Tiền vào")
            
        rsi = latest['RSI_14']
        if 50 <= rsi <= 70:
            score += 10
        elif rsi > 75:
            score -= 5
            details.append("⚠️ RSI Quá mua")

        # --- KHUYẾN NGHỊ HÀNH ĐỘNG ---
        action = "THEO DÕI"
        color = "yellow"
        
        if score >= 80:
            action = "MUA MẠNH (STRONG BUY)"
            color = "#00FF00" # Xanh lá tươi
        elif score >= 70:
            action = "MUA THĂM DÒ (BUY)"
            color = "#90EE90" # Xanh nhạt
        elif score < 50:
            action = "BÁN / TRÁNH XA"
            color = "#FF6347" # Đỏ

        # Trade Plan
        stop_loss = int(min_3m * 0.98)
        target = int(latest['Close'] * 1.15)

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm VIP": score,
            "Xếp hạng": action,
            "Lý do": ", ".join(details),
            "Biên độ": f"{round(fluctuation*100, 1)}%",
            "Cắt Lỗ": f"{stop_loss:,}",
            "Chốt Lời": f"{target:,}",
            "Color": color,
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
    
    # Nến
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    # MA
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_200'], line=dict(color='black', width=1, dash='dot'), name='MA200 (Long-term)'))
    
    # Hộp Darvas
    fig.add_hrect(y0=data['Box_Low'], y1=data['Box_High'], line_width=0, fillcolor="yellow", opacity=0.15, annotation_text="Vùng Gom Hàng")
    
    fig.update_layout(title=f"PHÂN TÍCH KỸ THUẬT: {symbol} (Điểm số: {data['Điểm VIP']}/100)", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🔍 BỘ LỌC CHUYÊN GIA")
    
    sector_options = ["QUÉT TOÀN BỘ (ALL)", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "VN30", "Midcap"]
    selected_sectors = st.multiselect("Chọn ngành:", sector_options, default=["QUÉT TOÀN BỘ (ALL)"])
    
    min_vip_score = st.slider("Điểm VIP tối thiểu", 0, 100, 70)
    st.info("💡 Mẹo: > 70 điểm là Vùng Mua An Toàn.")
    
    if st.button("CHẤM ĐIỂM THỊ TRƯỜNG 🚀", type="primary"):
        run_app = True
    else:
        run_app = False

if run_app:
    symbols = get_stock_universe(selected_sectors)
    st.info(f"AI đang chấm điểm {len(symbols)} mã cổ phiếu... Vui lòng đợi.")
    
    results = []
    my_bar = st.progress(0)
    
    for i, sym in enumerate(symbols):
        data = analyze_vip_score(sym)
        if data and data['Điểm VIP'] >= min_vip_score:
            results.append(data)
        my_bar.progress((i+1)/len(symbols))
        
    my_bar.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm VIP", ascending=False)
        st.success(f"✅ Tìm thấy {len(df_res)} mã đạt tiêu chuẩn an toàn!")
        
        # HIỂN THỊ BẢNG MÀU SẮC TRỰC QUAN
        def color_highlight(val):
            color = 'white'
            if val == "MUA MẠNH (STRONG BUY)": color = '#d4edda' # Xanh lá nhạt
            elif val == "MUA THĂM DÒ (BUY)": color = '#e2e3e5' # Xám nhạt
            return f'background-color: {color}; color: black'

        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm VIP', 'Xếp hạng', 'Lý do', 'Biên độ', 'Cắt Lỗ', 'Chốt Lời']]
            .style.applymap(lambda x: 'font-weight: bold', subset=['Điểm VIP', 'Xếp hạng']),
            use_container_width=True,
            height=600
        )
        
        st.divider()
        st.subheader("🧐 SOI CHI TIẾT & BIỂU ĐỒ")
        col1, col2 = st.columns([1,3])
        
        with col1:
            choice = st.radio("Chọn mã xem chart:", df_res['Mã'])
            item = next(x for x in results if x["Mã"] == choice)
            st.metric("Điểm Chuyên Gia", f"{item['Điểm VIP']}/100")
            st.metric("Khuyến nghị", item['Xếp hạng'])
            
        with col2:
            plot_chart(item)
            
    else:
        st.warning("Thị trường quá xấu! Không có mã nào đạt điểm an toàn.")
else:
    st.info("👈 Chọn Ngành và bấm nút để bắt đầu chấm điểm.")
