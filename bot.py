import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Stock Sniper", layout="wide", page_icon="🎯")
st.title("🎯 HỆ THỐNG TÍN HIỆU CHỨNG KHOÁN (FINAL STABLE)")
st.caption("Trạng thái: Đã sửa lỗi SMA_20 & Kết nối Yahoo Finance")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # DANH SÁCH MÃ QUAN TRỌNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    steel = ["HPG", "HSG", "NKG", "VGS"]
    seafood = ["VHC", "ANV", "FMC", "MPC", "IDI", "CMX"]
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]
    midcap = ["DGC", "CSV", "DPM", "DCM", "DGW", "FRT", "PET", "PC1", "GEG", "HAH", "VOS", "PVT", "TNG", "GIL", "PVS", "PVD", "DBC", "HAG", "PAN"]

    selected_symbols = []
    if "QUÉT TOÀN BỘ" in str(sector_choice):
        selected_symbols = list(set(banks + securities + real_estate + steel + seafood + vn30_other + midcap))
    else:
        if "Ngân hàng" in str(sector_choice): selected_symbols += banks
        if "Chứng khoán" in str(sector_choice): selected_symbols += securities
        if "Bất động sản" in str(sector_choice): selected_symbols += real_estate
        if "Thép" in str(sector_choice): selected_symbols += steel
        if "Thủy sản" in str(sector_choice): selected_symbols += seafood
        if "VN30" in str(sector_choice): selected_symbols += vn30_other

    return [f"{sym}.VN" for sym in list(set(selected_symbols))]

# --- 3. HÀM PHÂN TÍCH (SỬA LỖI KEY ERROR) ---
def analyze_stock_final(symbol):
    try:
        # 1. TẢI DATA (Dùng Ticker.history ổn định hơn download)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        # Kiểm tra dữ liệu rỗng
        if df is None or df.empty or len(df) < 50:
            return None, "❌ Không có dữ liệu (Yahoo chặn hoặc mã lỗi)"

        # 2. TÍNH CHỈ BÁO (GÁN THỦ CÔNG ĐỂ TRÁNH LỖI SMA_20)
        # Thay vì dùng append=True, ta gán thẳng vào cột mới
        try:
            # Lưu ý: Pandas TA trả về Series, ta gán trực tiếp
            df['SMA_20'] = ta.sma(df['Close'], length=20)
            df['SMA_50'] = ta.sma(df['Close'], length=50)
            df['RSI_14'] = ta.rsi(df['Close'], length=14)
        except Exception as e:
            return None, f"❌ Lỗi tính toán chỉ báo: {str(e)}"

        # Kiểm tra xem cột đã có chưa (Double check)
        if 'SMA_20' not in df.columns:
            return None, "❌ Lỗi: Không tạo được cột SMA_20"

        latest = df.iloc[-1]
        
        # 3. CHẤM ĐIỂM
        score = 0
        reasons = []

        # Kỹ thuật (50đ)
        # Dùng .get để tránh lỗi nếu giá trị NaN
        close = latest['Close']
        sma20 = latest.get('SMA_20', 0)
        sma50 = latest.get('SMA_50', 0)
        rsi = latest.get('RSI_14', 50)

        if close > sma20: score += 15
        if sma20 > sma50: score += 20
        if 50 <= rsi <= 70: score += 15
        
        # Tích lũy (30đ)
        df_last = df.tail(20)
        fluctuation = (df_last['High'].max() - df_last['Low'].min()) / df_last['Low'].min()
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

        # 4. LẤY INFO TÀI CHÍNH (Cố gắng lấy, lỗi thì bỏ qua)
        pe, eps, roe = "-", "-", "-"
        # Chỉ lấy info cho mã có điểm khá để tiết kiệm thời gian
        if score >= 40:
            try:
                info = ticker.info
                pe = info.get('trailingPE', '-')
                if pe != '-' and pe is not None: pe = round(pe, 1)
                
                eps = info.get('trailingEps', '-')
                if eps != '-' and eps is not None: eps = f"{int(eps):,}"
                
                roe = info.get('returnOnEquity', '-')
                if roe != '-' and roe is not None: roe = f"{round(roe*100, 1)}%"
            except:
                pass # Bỏ qua lỗi info

        rating = "THEO DÕI"
        if score >= 70: rating = "MUA"
        if score >= 85: rating = "MUA MẠNH"

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": f"{int(latest['Close']):,}",
            "Điểm": score,
            "Xếp hạng": rating,
            "P/E": pe, "EPS": eps, "ROE": roe,
            "Lý do": ", ".join(reasons),
            "Dataframe": df
        }, "OK"

    except Exception as e:
        return None, f"❌ Lỗi hệ thống: {str(e)}"

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    
    if 'SMA_20' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    if 'SMA_50' in df.columns:
        fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
        
    fig.update_layout(title=f"Chart: {symbol} ({data['Điểm']}đ)", height=500, xaxis_rangeslider_visible=False)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🎛️ BỘ LỌC")
    sectors = ["QUÉT TOÀN BỘ", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép", "Thủy sản"]
    choice = st.multiselect("Ngành:", sectors, default=["QUÉT TOÀN BỘ"])
    min_score = st.slider("Điểm tối thiểu", 0, 100, 40)
    btn_scan = st.button("CHẠY QUÉT 🚀", type="primary")

if btn_scan:
    symbols = get_stock_universe(choice)
    
    st.subheader("📝 Nhật Ký Hoạt Động")
    log_box = st.empty()
    progress = st.progress(0)
    
    results = []
    
    for i, sym in enumerate(symbols):
        log_box.text(f"Đang xử lý: {sym} ({i+1}/{len(symbols)})...")
        
        # Thêm độ trễ cực nhỏ để tránh bị Yahoo chặn (quan trọng)
        time.sleep(0.1)
        
        data, msg = analyze_stock_final(sym)
        
        if data:
            if data['Điểm'] >= min_score:
                results.append(data)
    
        progress.progress((i+1)/len(symbols))
        
    log_box.text("✅ Đã hoàn tất!")

    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
        st.success(f"🎉 Tìm thấy {len(df_res)} mã.")
        
        st.dataframe(
            df_res[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'ROE', 'Lý do']],
            use_container_width=True, 
            height=600
        )
        
        st.divider()
        stock_list = df_res['Mã'].tolist()
        if stock_list:
            selected = st.selectbox("Xem Biểu Đồ:", stock_list)
            item = next((x for x in results if x['Mã'] == selected), None)
            if item: plot_chart(item)
    else:
        st.warning("Không tìm thấy mã nào! (Hãy thử kéo điểm về 0 để kiểm tra)")
