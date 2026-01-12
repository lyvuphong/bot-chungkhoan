import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Pro Stock Scanner", layout="wide", page_icon="⚡")
st.title("⚡ HỆ THỐNG QUÉT CỔ PHIẾU (DATA FIX)")
st.caption("Chế độ: Quét chậm để lấy đầy đủ chỉ số Tài chính (P/E, EPS, P/B...)")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # NGÂN HÀNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    # CHỨNG KHOÁN
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    # BẤT ĐỘNG SẢN & KCN
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    # THÉP & SẢN XUẤT
    production = ["HPG", "HSG", "NKG", "DGC", "CSV", "VHC", "ANV", "FMC", "PTB", "DGW", "FRT", "MWG", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]

    selected_symbols = []
    if "QUÉT TOÀN BỘ (ALL)" in sector_choice:
        selected_symbols = list(set(banks + securities + real_estate + production))
    else:
        if "Ngân hàng" in sector_choice: selected_symbols += banks
        if "Chứng khoán" in sector_choice: selected_symbols += securities
        if "Bất động sản" in sector_choice: selected_symbols += real_estate
        if "Thép & SX" in sector_choice: selected_symbols += production

    return [f"{sym}.VN" for sym in list(set(selected_symbols))]

# --- 3. HÀM XỬ LÝ SỐ LIỆU ---
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def get_financial_info(ticker_obj):
    """Hàm lấy chỉ số tài chính (Có thử lại nếu lỗi)"""
    info = {}
    try:
        # Cách lấy info an toàn hơn
        info = ticker_obj.info
    except:
        pass # Nếu lỗi lần 1, bỏ qua
    return info

def analyze_stock_detailed(symbol):
    try:
        # 1. LẤY DỮ LIỆU GIÁ
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or len(df) < 50: return None
        
        # --- LỌC KỸ THUẬT (Sơ bộ) ---
        latest = df.iloc[-1]
        
        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        # 2. LẤY CHỈ SỐ TÀI CHÍNH (QUAN TRỌNG)
        # Thêm độ trễ để Yahoo không chặn (0.2s)
        time.sleep(0.2) 
        info = get_financial_info(ticker)
        
        # Trích xuất dữ liệu (Nếu không có thì để -)
        pe = info.get('trailingPE', '-')
        if pe != '-': pe = round(pe, 1)
        
        eps = info.get('trailingEps', '-')
        if eps != '-': eps = f"{int(eps):,}"
        
        pb = info.get('priceToBook', '-')
        if pb != '-': pb = round(pb, 1)
        
        roe = info.get('returnOnEquity', '-')
        if roe != '-': roe = f"{round(roe*100, 1)}%"
        
        div = info.get('dividendYield', '-')
        if div != '-': div = f"{round(div*100, 1)}%"
        
        # 3. CHẤM ĐIỂM
        score = 0
        reasons = []

        # Kỹ thuật (50đ)
        if latest['Close'] > latest['SMA_20']: score += 15
        if latest['SMA_20'] > latest['SMA_50']: score += 20
        if safe_float(latest['RSI_14']) > 50: score += 15
        
        # Tích lũy (30đ)
        df_last = df.tail(20)
        fluctuation = (df_last['High'].max() - df_last['Low'].min()) / df_last['Low'].min()
        if fluctuation < 0.15: 
            score += 30
            reasons.append("Nền chặt")
        elif fluctuation < 0.25:
            score += 15
            
        # Tiền vào (20đ)
        if latest['Volume'] > df['Volume'].tail(20).mean(): 
            score += 20
            reasons.append("Tiền vào")

        # Xếp hạng
        rating = "THEO DÕI"
        if score >= 70: rating = "MUA"
        if score >= 85: rating = "MUA MẠNH"

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm": score,
            "Xếp hạng": rating,
            "P/E": pe, "EPS": eps, "P/B": pb, "ROE": roe, "Cổ tức": div,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }

    except Exception as e:
        return None

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.update_layout(title=f"Biểu đồ: {symbol}", height=500, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BẢNG ĐIỀU KHIỂN")
    sectors = ["QUÉT TOÀN BỘ (ALL)", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép & SX"]
    choice = st.multiselect("Chọn ngành:", sectors, default=["Ngân hàng"])
    
    st.info("⚠️ Lưu ý: Để lấy được P/E, EPS, tốc độ quét sẽ chậm hơn bình thường một chút.")
    min_score = st.slider("Điểm tối thiểu", 0, 100, 50)
    
    btn_scan = st.button("BẮT ĐẦU QUÉT NGAY 🚀", type="primary")

# LOGIC CHẠY
if btn_scan:
    symbols = get_stock_universe(choice)
    
    status_text = st.empty()
    progress = st.progress(0)
    
    results = []
    
    # Quét từng mã
    for i, sym in enumerate(symbols):
        status_text.text(f"Đang tải dữ liệu tài chính: {sym} ({i+1}/{len(symbols)})...")
        
        data = analyze_stock_detailed(sym)
        if data and data['Điểm'] >= min_score:
            results.append(data)
            
        progress.progress((i+1)/len(symbols))
            
    # HIỂN THỊ KẾT QUẢ
    status_text.empty()
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        st.success(f"🎉 Hoàn tất! Tìm thấy {len(df_res)} mã.")
        
        # Bảng
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'P/B', 'ROE', 'Cổ tức', 'Lý do']],
            use_container_width=True,
            height=600
        )
        
        # Chart
        st.divider()
        st.subheader("📈 Xem Biểu Đồ")
        stock_options = df_res['Mã'].tolist()
        if stock_options:
            selected = st.selectbox("Chọn mã:", stock_options)
            item = next((x for x in results if x['Mã'] == selected), None)
            if item:
                plot_chart(item)
    else:
        st.error("Không tìm thấy mã nào! Hãy thử hạ điểm số.")

else:
    st.info("👈 Chọn ngành bên trái và bấm nút để chạy.")
