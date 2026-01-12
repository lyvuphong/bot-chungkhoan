import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Pro Stock Scanner", layout="wide", page_icon="⚡")
st.title("⚡ HỆ THỐNG PHÂN TÍCH CỔ PHIẾU CHUYÊN SÂU")
st.caption("Chiến lược: VN100 & Midcap | Tích hợp Định giá & Dòng tiền thông minh")

# --- 2. KHO DỮ LIỆU CỔ PHIẾU ---
def get_stock_universe(sector_choice):
    # 1. NGÂN HÀNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB", "EIB", "BAB", "NAB"]
    
    # 2. CHỨNG KHOÁN
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS", "AGR", "VDS"]
    
    # 3. BẤT ĐỘNG SẢN & KCN
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR", "IJC", "HDC", "TCH"]
    
    # 4. THÉP & VẬT LIỆU
    steel = ["HPG", "HSG", "NKG", "VGS", "HT1", "BCC", "KSB"]
    
    # 5. THỦY SẢN (Theo yêu cầu: MPC, VHC...)
    seafood = ["VHC", "ANV", "FMC", "MPC", "IDI", "CMX", "ACL"]
    
    # 6. NHÓM VN30 (Các mã chưa liệt kê)
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD", "VJC"]
    
    # 7. MIDCAP TIỀM NĂNG (Dệt may, Điện, Bán lẻ, Hóa chất, Vận tải...)
    midcap = [
        "DGC", "CSV", "DPM", "DCM", "LAS", # Hóa chất
        "DGW", "FRT", "PET", "HAX", # Bán lẻ
        "PC1", "GEG", "NT2", "VSH", "TDM", "BWE", # Điện nước
        "HAH", "VOS", "PVT", "GMD", "SGP", # Cảng biển
        "TNG", "GIL", "MSH", "VGT", # Dệt may
        "PVS", "PVD", "BSR", "OIL", # Dầu khí
        "DBC", "HAG", "BFCO", "LTG", "PAN" # Nông nghiệp
    ]

    selected_symbols = []
    
    # Logic chọn ngành
    if "QUÉT TOÀN BỘ (VN100 & ALL)" in sector_choice:
        selected_symbols = list(set(banks + securities + real_estate + steel + seafood + vn30_other + midcap))
    else:
        if "Ngân hàng" in sector_choice: selected_symbols += banks
        if "Chứng khoán" in sector_choice: selected_symbols += securities
        if "Bất động sản" in sector_choice: selected_symbols += real_estate
        if "Thép" in sector_choice: selected_symbols += steel
        if "Thủy sản (MPC, VHC...)" in sector_choice: selected_symbols += seafood
        if "VN30" in sector_choice: selected_symbols += vn30_other
        if "Midcap Khác" in sector_choice: selected_symbols += midcap

    # Lọc trùng và thêm đuôi .VN
    unique_symbols = list(set(selected_symbols))
    return [f"{sym}.VN" for sym in unique_symbols]

# --- 3. HÀM LẤY INFO AN TOÀN ---
def get_financial_info(ticker_obj):
    """Lấy thông tin tài chính với cơ chế thử lại"""
    try:
        return ticker_obj.info
    except:
        return {}

# --- 4. HÀM PHÂN TÍCH CHUYÊN NGHIỆP ---
def analyze_stock_pro(symbol):
    try:
        # BƯỚC 1: TẢI DỮ LIỆU GIÁ (NHANH)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or len(df) < 50: return None
        
        latest = df.iloc[-1]
        
        # --- LỌC SƠ BỘ (Pre-Filter) ---
        # Chỉ những mã có Vol tốt và giá > 5k mới phân tích tiếp
        if latest['Volume'] < 10000 or latest['Close'] < 5000: return None

        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        # --- CHẤM ĐIỂM KỸ THUẬT ---
        tech_score = 0
        reasons = []
        
        # Trend
        if latest['Close'] > latest['SMA_20']: tech_score += 20
        if latest['SMA_20'] > latest['SMA_50']: tech_score += 20
        
        # Tích lũy
        df_last = df.tail(20)
        fluctuation = (df_last['High'].max() - df_last['Low'].min()) / df_last['Low'].min()
        if fluctuation < 0.15: 
            tech_score += 30
            reasons.append("Nền chặt")
            
        # Tiền vào
        if latest['Volume'] > df['Volume'].tail(20).mean(): 
            tech_score += 30
            reasons.append("Tiền vào")
            
        # Nếu điểm kỹ thuật quá thấp (<40), bỏ qua luôn để tiết kiệm thời gian lấy P/E
        if tech_score < 40: return None

        # BƯỚC 2: TẢI CHỈ SỐ TÀI CHÍNH (CHẬM - CHỈ LÀM CHO MÃ TỐT)
        time.sleep(0.1) # Nghỉ nhẹ để tránh bị chặn
        info = get_financial_info(ticker)
        
        pe = info.get('trailingPE', '-')
        eps = info.get('trailingEps', '-')
        pb = info.get('priceToBook', '-')
        roe = info.get('returnOnEquity', '-')
        div = info.get('dividendYield', '-')

        # Format số liệu đẹp
        pe_str = f"{round(pe, 1)}" if pe != '-' else "-"
        eps_str = f"{int(eps):,}" if eps != '-' else "-"
        pb_str = f"{round(pb, 1)}" if pb != '-' else "-"
        roe_str = f"{round(roe*100, 1)}%" if roe != '-' else "-"
        div_str = f"{round(div*100, 1)}%" if div != '-' else "-"

        # Xếp hạng
        total_score = tech_score
        rating = "THEO DÕI"
        if total_score >= 80: rating = "MUA MẠNH"
        elif total_score >= 60: rating = "MUA"

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm": total_score,
            "Xếp hạng": rating,
            "P/E": pe_str, "EPS": eps_str, "P/B": pb_str, "ROE": roe_str, "Cổ tức": div_str,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }
    except Exception:
        return None

# --- 5. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    
    # Nến
    fig.add_trace(go.Candlestick(
        x=df.index, open=df['Open'], high=df['High'], 
        low=df['Low'], close=df['Close'], name='Giá'
    ))
    # MA
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    
    fig.update_layout(
        title=f"Biểu đồ kỹ thuật: {symbol} (Điểm: {data['Điểm']})",
        height=500, xaxis_rangeslider_visible=False
    )
    st.plotly_chart(fig, use_container_width=True)

# --- 6. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BỘ LỌC THÔNG MINH")
    
    sectors = [
        "QUÉT TOÀN BỘ (VN100 & ALL)", 
        "Ngân hàng", 
        "Chứng khoán", 
        "Bất động sản", 
        "Thép",
        "Thủy sản (MPC, VHC...)",
        "VN30",
        "Midcap Khác"
    ]
    
    choice = st.multiselect("Chọn ngành:", sectors, default=["Thủy sản (MPC, VHC...)"])
    min_score = st.slider("Điểm lọc tối thiểu", 0, 100, 50)
    
    btn_scan = st.button("QUÉT NGAY 🚀", type="primary")

if btn_scan:
    symbols = get_stock_universe(choice)
    st.toast(f"Đang bắt đầu quét {len(symbols)} mã...", icon="⏳")
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    results = []
    
    for i, sym in enumerate(symbols):
        status_text.text(f"Đang phân tích: {sym} ({i+1}/{len(symbols)})")
        
        data = analyze_stock_pro(sym)
        if data and data['Điểm'] >= min_score:
            results.append(data)
            
        progress_bar.progress((i+1)/len(symbols))
        
    status_text.empty()
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        st.success(f"🎉 Xong! Tìm thấy {len(df_res)} mã tiềm năng.")
        
        # Hiển thị bảng
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'P/B', 'ROE', 'Cổ tức', 'Lý do']],
            use_container_width=True,
            height=600
        )
        
        # Hiển thị biểu đồ
        st.divider()
        st.subheader("📈 Soi Biểu Đồ")
        stock_list = df_res['Mã'].tolist()
        if stock_list:
            selected = st.selectbox("Chọn mã:", stock_list)
            item = next((x for x in results if x['Mã'] == selected), None)
            if item:
                plot_chart(item)
    else:
        st.warning("Không tìm thấy mã nào đạt chuẩn. Hãy thử hạ điểm số hoặc chọn ngành khác.")
