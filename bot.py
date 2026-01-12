import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Stock Scanner (Debug Mode)", layout="wide", page_icon="🛠️")
st.title("🛠️ HỆ THỐNG QUÉT & GỠ LỖI (DEBUG MODE)")
st.caption("Chế độ này giúp đảm bảo dữ liệu luôn hiển thị, bất chấp lỗi từ Yahoo Finance.")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # DANH SÁCH RÚT GỌN ĐỂ TEST NHANH TRƯỚC (Sau đó mới mở rộng)
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "LPB", "EIB"]
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "VIX"]
    real_estate = ["VHM", "VIC", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "KBC", "IDC"]
    steel = ["HPG", "HSG", "NKG"]
    seafood = ["VHC", "ANV", "FMC", "MPC", "IDI"]
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "VNM", "REE"]
    
    # DANH SÁCH FULL (VN100 + MIDCAP)
    full_list = list(set(banks + securities + real_estate + steel + seafood + vn30_other))

    selected_symbols = []
    if "QUÉT TOÀN BỘ" in str(sector_choice):
        selected_symbols = full_list
    else:
        if "Ngân hàng" in str(sector_choice): selected_symbols += banks
        if "Chứng khoán" in str(sector_choice): selected_symbols += securities
        if "Bất động sản" in str(sector_choice): selected_symbols += real_estate
        if "Thép" in str(sector_choice): selected_symbols += steel
        if "Thủy sản" in str(sector_choice): selected_symbols += seafood
        if "VN30" in str(sector_choice): selected_symbols += vn30_other

    return [f"{sym}.VN" for sym in list(set(selected_symbols))]

# --- 3. HÀM PHÂN TÍCH SIÊU BỀN (FAIL-SAFE) ---
def analyze_stock_debug(symbol):
    log_status = "Khởi tạo"
    try:
        # 1. TẢI GIÁ (Dùng yf.download thay vì Ticker để ổn định hơn)
        # threads=False giúp tránh bị Yahoo chặn IP trên Cloud
        df = yf.download(symbol, period="1y", progress=False, threads=False)
        
        # Xử lý lỗi MultiIndex của Yahoo mới
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 50:
            return None, f"❌ Không đủ dữ liệu giá (Row: {len(df) if df is not None else 0})"

        latest = df.iloc[-1]
        
        # 2. CHẤM ĐIỂM KỸ THUẬT
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        score = 0
        reasons = []
        
        # Trend (50đ)
        if latest['Close'] > latest['SMA_20']: score += 20
        if latest['SMA_20'] > latest['SMA_50']: score += 20
        try:
            if latest['RSI_14'] > 50: score += 10
        except: pass
        
        # Tiền vào (20đ)
        avg_vol = df['Volume'].tail(20).mean()
        if latest['Volume'] > avg_vol: 
            score += 20
            reasons.append("Tiền vào")
            
        # Tích lũy (30đ)
        df_last = df.tail(20)
        fluctuation = (df_last['High'].max() - df_last['Low'].min()) / df_last['Low'].min()
        if fluctuation < 0.15: 
            score += 30
            reasons.append("Nền chặt")
        elif fluctuation < 0.25:
            score += 10

        # 3. LẤY INFO (CỐ GẮNG NHƯNG KHÔNG BẮT BUỘC)
        pe, eps, roe = "-", "-", "-"
        try:
            # Chỉ lấy info nếu điểm cao để tiết kiệm thời gian
            if score >= 40: 
                ticker = yf.Ticker(symbol)
                info = ticker.info
                pe = info.get('trailingPE', '-')
                if pe != '-': pe = round(pe, 1)
                
                eps = info.get('trailingEps', '-')
                if eps != '-': eps = f"{int(eps):,}"
                
                roe = info.get('returnOnEquity', '-')
                if roe != '-': roe = f"{round(roe*100, 1)}%"
        except:
            log_status = "⚠️ Lấy giá OK, nhưng lỗi Info tài chính"

        rating = "THEO DÕI"
        if score >= 80: rating = "MUA MẠNH"
        elif score >= 60: rating = "MUA"

        data = {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm": score,
            "Xếp hạng": rating,
            "P/E": pe, "EPS": eps, "ROE": roe,
            "Lý do": ", ".join(reasons) if reasons else "Không rõ",
            "Dataframe": df
        }
        return data, "✅ Thành công"

    except Exception as e:
        return None, f"❌ Lỗi Code: {str(e)}"

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.update_layout(title=f"Chart: {symbol} ({data['Điểm']}đ)", height=500, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BỘ LỌC")
    sectors = ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"]
    choice = st.multiselect("Ngành:", sectors, default=["QUÉT TOÀN BỘ"])
    min_score = st.slider("Điểm tối thiểu (Để 0 để xem tất cả)", 0, 100, 40)
    btn_scan = st.button("CHẠY QUÉT 🚀", type="primary")

if btn_scan:
    symbols = get_stock_universe(choice)
    
    # KHU VỰC NHẬT KÝ (LOG) - QUAN TRỌNG ĐỂ BIẾT LỖI
    st.subheader("📝 Nhật Ký Hoạt Động")
    log_box = st.empty()
    progress = st.progress(0)
    
    results = []
    logs = []
    
    for i, sym in enumerate(symbols):
        # Hiện trạng thái
        log_box.text(f"Đang xử lý: {sym} ({i+1}/{len(symbols)})...")
        
        data, msg = analyze_stock_debug(sym)
        
        if data:
            if data['Điểm'] >= min_score:
                results.append(data)
                logs.append(f"🟢 {sym}: {msg} (Điểm: {data['Điểm']})")
            else:
                logs.append(f"⚪ {sym}: Điểm thấp ({data['Điểm']})")
        else:
            logs.append(f"🔴 {sym}: {msg}")
            
        progress.progress((i+1)/len(symbols))
        
    log_box.text("Đã hoàn tất!")
    
    # Hiển thị nhật ký rút gọn (để bạn biết mã nào lỗi)
    with st.expander("Xem chi tiết Nhật ký quét (Bấm vào đây)"):
        for log in logs:
            st.write(log)

    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        st.success(f"🎉 Tìm thấy {len(df_res)} mã.")
        
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'ROE', 'Lý do']],
            use_container_width=True, 
            height=500
        )
        
        st.divider()
        stock_list = df_res['Mã'].tolist()
        if stock_list:
            selected = st.selectbox("Xem Biểu Đồ:", stock_list)
            item = next((x for x in results if x['Mã'] == selected), None)
            if item: plot_chart(item)
    else:
        st.error("Vẫn không tìm thấy mã nào! Hãy kiểm tra phần 'Nhật ký quét' ở trên xem lỗi gì.")
