import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN CHUẨN ---
st.set_page_config(page_title="AI Pro Stock Scanner", layout="wide", page_icon="⚡")
st.title("⚡ HỆ THỐNG QUÉT CỔ PHIẾU (PHIÊN BẢN ỔN ĐỊNH)")
st.caption("Chiến lược: Ưu tiên hiển thị dữ liệu - Không bỏ sót cơ hội")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # NGÂN HÀNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    # CHỨNG KHOÁN
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    # BẤT ĐỘNG SẢN & KCN
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    # THÉP & SẢN XUẤT
    production = ["HPG", "HSG", "NKG", "DGC", "CSV", "VHC", "ANV", "FMC", "PTB", "DGW", "FRT"]
    # VN30 KHÁC
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]

    selected_symbols = []
    if "QUÉT TOÀN BỘ (ALL)" in sector_choice:
        selected_symbols = list(set(banks + securities + real_estate + production + vn30_other))
    else:
        if "Ngân hàng" in sector_choice: selected_symbols += banks
        if "Chứng khoán" in sector_choice: selected_symbols += securities
        if "Bất động sản" in sector_choice: selected_symbols += real_estate
        if "Thép & SX" in sector_choice: selected_symbols += production
        if "VN30" in sector_choice: selected_symbols += vn30_other

    # Thêm đuôi .VN
    return [f"{sym}.VN" for sym in list(set(selected_symbols))]

# --- 3. HÀM XỬ LÝ AN TOÀN ---
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def analyze_stock_robust(symbol):
    """Hàm phân tích không bao giờ crash"""
    try:
        # 1. LẤY DỮ LIỆU GIÁ (Dùng yf.download nhanh hơn Ticker.history)
        df = yf.download(symbol, period="1y", progress=False)
        
        # Xử lý MultiIndex nếu có (Yahoo mới update hay bị lỗi này)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 50: 
            return None # Không đủ dữ liệu giá

        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        # Lấy dòng mới nhất
        latest = df.iloc[-1]
        
        # 2. LẤY THÔNG TIN CƠ BẢN (INFO) - Dùng try/except riêng
        # Mặc định là N/A nếu lỗi, để không chết chương trình
        pe, eps, pb, div, roe, cap = "-", "-", "-", "-", "-", "-"
        
        try:
            # Chỉ lấy info nếu cần thiết (Có thể bỏ qua để tăng tốc)
            t = yf.Ticker(symbol)
            info = t.info
            
            _pe = info.get('trailingPE')
            if _pe: pe = round(_pe, 1)
            
            _eps = info.get('trailingEps')
            if _eps: eps = f"{int(_eps):,}"
            
            _pb = info.get('priceToBook')
            if _pb: pb = round(_pb, 1)
            
            _div = info.get('dividendYield')
            if _div: div = f"{round(_div*100, 1)}%"
            
            _roe = info.get('returnOnEquity')
            if _roe: roe = f"{round(_roe*100, 1)}%"
            
            _cap = info.get('marketCap')
            if _cap: 
                if _cap > 1_000_000_000_000: cap = f"{round(_cap/1_000_000_000_000, 1)} Tỷ USD" # Yahoo hay trả về tiền VND quy đổi lung tung, hiển thị số thô cho an toàn
                else: cap = f"{int(_cap):,}"
        except:
            pass # Lỗi lấy Info thì bỏ qua, vẫn hiện chart

        # 3. CHẤM ĐIỂM
        score = 0
        reasons = []

        # Trend (50đ)
        if latest['Close'] > latest['SMA_20']: score += 15
        if latest['SMA_20'] > latest['SMA_50']: score += 20
        if safe_float(latest['RSI_14']) > 50: score += 15
        
        # Tích lũy (30đ)
        df_last = df.tail(20)
        high = df_last['High'].max()
        low = df_last['Low'].min()
        fluctuation = (high - low) / low
        
        if fluctuation < 0.15: 
            score += 30
            reasons.append("Nền chặt")
        elif fluctuation < 0.25:
            score += 15
            
        # Tiền vào (20đ)
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol: 
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
        return None # Lỗi không xác định

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    
    fig.update_layout(title=f"Chart: {symbol} (Score: {data['Điểm']})", height=500, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BẢNG ĐIỀU KHIỂN")
    sectors = ["QUÉT TOÀN BỘ (ALL)", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép & SX", "VN30"]
    choice = st.multiselect("Chọn ngành:", sectors, default=["VN30"])
    
    # Quan trọng: Cho phép lọc điểm = 0 để xem tất cả
    min_score = st.slider("Điểm tối thiểu (Để 0 để xem tất cả)", 0, 100, 50)
    
    btn_scan = st.button("BẮT ĐẦU QUÉT NGAY 🚀", type="primary")

# LOGIC CHẠY
if btn_scan:
    symbols = get_stock_universe(choice)
    
    # Khu vực Log trạng thái
    status_log = st.expander("📝 Nhật ký quét (Bấm để xem chi tiết)", expanded=True)
    status_text = st.empty()
    progress = st.progress(0)
    
    results = []
    
    with status_log:
        st.write(f"Đang chuẩn bị quét {len(symbols)} mã...")
        
        for i, sym in enumerate(symbols):
            status_text.text(f"Đang xử lý: {sym} ({i+1}/{len(symbols)})")
            
            # Xử lý
            data = analyze_stock_robust(sym)
            
            if data:
                if data['Điểm'] >= min_score:
                    results.append(data)
                    st.write(f"✅ {sym}: OK (Điểm: {data['Điểm']})")
                else:
                    # Vẫn log ra nhưng màu xám để biết là đã quét
                    st.write(f"⚠️ {sym}: Điểm thấp ({data['Điểm']}) - Bỏ qua")
            else:
                st.write(f"❌ {sym}: Lỗi dữ liệu hoặc không giao dịch")
            
            progress.progress((i+1)/len(symbols))
            
    # HIỂN THỊ KẾT QUẢ
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        st.success(f"🎉 Hoàn tất! Tìm thấy {len(df_res)} mã.")
        
        # Bảng
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'P/B', 'ROE', 'Cổ tức', 'Lý do']],
            use_container_width=True,
            height=500
        )
        
        # Chart
        st.divider()
        st.subheader("📈 Xem Biểu Đồ")
        stock_options = df_res['Mã'].tolist()
        selected = st.selectbox("Chọn mã:", stock_options)
        
        # Tìm data để vẽ
        item = next((x for x in results if x['Mã'] == selected), None)
        if item:
            plot_chart(item)
    else:
        st.error("Không tìm thấy mã nào! Hãy thử kéo thanh điểm về 0 để kiểm tra.")

else:
    st.info("👈 Chọn ngành bên trái và bấm nút để chạy.")
