import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Trading Pro + Financials", layout="wide", page_icon="💎")
st.title("💎 HỆ THỐNG ĐỊNH GIÁ & TÍN HIỆU (FULL OPTION)")
st.caption("Kết hợp: Phân tích Kỹ thuật (VSA) + Phân tích Cơ bản (P/E, EPS, P/B, Cổ tức)")

# --- 2. KHO DỮ LIỆU ---
def get_stock_universe(sector_choice):
    # NGÂN HÀNG
    banks = ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB"]
    # CHỨNG KHOÁN
    securities = ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS"]
    # BẤT ĐỘNG SẢN & KCN
    real_estate = ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "KBC", "IDC", "SZC", "GVR", "HDG", "NTC", "SIP", "PHR"]
    # THÉP & SẢN XUẤT
    production = ["HPG", "HSG", "NKG", "DGC", "CSV", "VHC", "ANV", "FMC", "PTB"]
    # VN30 KHÁC
    vn30_other = ["MWG", "FPT", "PNJ", "MSN", "GAS", "PLX", "POW", "SAB", "VNM", "BVH", "REE", "GMD"]

    selected_symbols = []
    if "Ngân hàng" in sector_choice: selected_symbols += banks
    if "Chứng khoán" in sector_choice: selected_symbols += securities
    if "Bất động sản" in sector_choice: selected_symbols += real_estate
    if "Thép & SX" in sector_choice: selected_symbols += production
    if "VN30" in sector_choice: selected_symbols += vn30_other
    
    if "QUÉT TOÀN BỘ (ALL)" in sector_choice:
        selected_symbols = banks + securities + real_estate + production + vn30_other

    unique_symbols = list(set(selected_symbols))
    return [f"{sym}.VN" for sym in unique_symbols]

# --- 3. HÀM CHUYỂN ĐỔI SỐ LIỆU ---
def format_volume(num):
    if num >= 1_000_000_000: return f"{round(num/1_000_000_000, 2)} Tỷ"
    if num >= 1_000_000: return f"{round(num/1_000_000, 2)} Tr"
    return f"{num:,}"

def safe_get(data_dict, key, default="-"):
    val = data_dict.get(key)
    return val if val is not None else default

# --- 4. HÀM PHÂN TÍCH KÉP (KỸ THUẬT + CƠ BẢN) ---
def analyze_stock_full(symbol):
    try:
        # A. LẤY DỮ LIỆU KỸ THUẬT (History)
        ticker = yf.Ticker(symbol)
        df = ticker.history(period="1y")
        
        if df is None or len(df) < 150: return None
        
        # B. LẤY DỮ LIỆU CƠ BẢN (Financial Info)
        # Lưu ý: info có thể làm chậm tốc độ quét
        info = ticker.info 
        
        # --- XỬ LÝ KỸ THUẬT ---
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.sma(length=200, append=True)
        df.ta.rsi(length=14, append=True)
        latest = df.iloc[-1]
        
        # Điều kiện lọc rác
        if latest['Close'] < 5000 or latest['Volume'] < 20000: return None

        # Tính toán nền giá
        df_3m = df.tail(60)
        fluctuation = (df_3m['High'].max() - df_3m['Low'].min()) / df_3m['Low'].min()
        
        # --- C. CHẤM ĐIỂM (VIP SCORE) ---
        score = 0
        details = []

        # 1. Kỹ thuật (60đ)
        if latest['Close'] > latest['SMA_20']: score += 10
        if latest['SMA_20'] > latest['SMA_50']: score += 15
        if latest['Close'] > latest['SMA_200']: score += 10 # Uptrend dài hạn
        
        if fluctuation < 0.15: 
            score += 25
            details.append(f"Nền chặt ({round(fluctuation*100,1)}%)")
        elif fluctuation < 0.25:
            score += 10
        
        if latest['Volume'] > df['Volume'].tail(20).mean(): 
            score += 5
            details.append("Tiền vào")

        # 2. Cơ bản (40đ) - Dữ liệu lấy từ info
        pe = safe_get(info, 'trailingPE', None)
        pb = safe_get(info, 'priceToBook', None)
        roe = safe_get(info, 'returnOnEquity', 0)
        div_yield = safe_get(info, 'dividendYield', 0)
        
        # Logic chấm điểm cơ bản
        is_good_fundamental = False
        if pe and 5 < pe < 20: # P/E hợp lý
            score += 10
            is_good_fundamental = True
        if pb and pb < 3: # P/B không quá cao
            score += 10
        if roe and roe > 0.15: # ROE > 15%
            score += 10
            details.append("ROE cao")
        if div_yield and div_yield > 0.03: # Cổ tức > 3%
            score += 10
            details.append("Cổ tức tốt")

        # D. TỔNG HỢP DỮ LIỆU HIỂN THỊ
        market_cap = safe_get(info, 'marketCap', 0)
        shares = safe_get(info, 'sharesOutstanding', 0)
        eps = safe_get(info, 'trailingEps', 0)

        # Xếp hạng
        rating = "THEO DÕI"
        if score >= 80: rating = "💎 MUA MẠNH"
        elif score >= 65: rating = "✅ MUA/NẮM GIỮ"
        
        stop_loss = int(df_3m['Low'].min() * 0.98)
        target = int(latest['Close'] * 1.15)

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá": int(latest['Close']),
            "Điểm": score,
            "Xếp hạng": rating,
            # --- CHỈ SỐ TÀI CHÍNH MỚI ---
            "P/E": round(pe, 1) if pe else "-",
            "EPS": f"{int(eps):,}" if eps else "-",
            "P/B": round(pb, 1) if pb else "-",
            "Cổ tức": f"{round(div_yield*100, 1)}%" if div_yield else "0%",
            "ROE": f"{round(roe*100, 1)}%" if roe else "-",
            "Vốn hóa": format_volume(market_cap),
            "KLCP Lưu hành": format_volume(shares),
            # ---------------------------
            "Lý do": ", ".join(details),
            "Cắt Lỗ": f"{stop_loss:,}",
            "Chốt Lời": f"{target:,}",
            "Dataframe": df,
            "Box_High": df_3m['High'].max(),
            "Box_Low": df_3m['Low'].min()
        }
    except Exception as e:
        return None

# --- 5. VẼ BIỂU ĐỒ ---
def plot_chart(data):
    df = data['Dataframe']
    symbol = data['Mã']
    fig = go.Figure()
    
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_50'], line=dict(color='blue', width=1), name='MA50'))
    fig.add_hrect(y0=data['Box_Low'], y1=data['Box_High'], line_width=0, fillcolor="yellow", opacity=0.15, annotation_text="Nền Tích Lũy")
    
    fig.update_layout(title=f"BIỂU ĐỒ: {symbol} (P/E: {data['P/E']} | EPS: {data['EPS']})", xaxis_rangeslider_visible=False, height=500)
    st.plotly_chart(fig, use_container_width=True)

# --- 6. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("🔍 BỘ LỌC ĐA NĂNG")
    sector_options = ["QUÉT TOÀN BỘ (ALL)", "Ngân hàng", "Chứng khoán", "Bất động sản", "Thép & SX", "VN30"]
    selected_sectors = st.multiselect("Chọn ngành:", sector_options, default=["VN30"])
    
    min_score = st.slider("Điểm tối thiểu", 0, 100, 60)
    
    if st.button("QUÉT CHI TIẾT 🚀", type="primary"):
        st.session_state['trigger'] = True

if st.session_state.get('trigger'):
    symbols = get_stock_universe(selected_sectors)
    
    with st.spinner(f"Đang tải dữ liệu Kỹ thuật & Báo cáo tài chính cho {len(symbols)} mã... (Sẽ lâu hơn bình thường)"):
        results = []
        bar = st.progress(0)
        
        for i, sym in enumerate(symbols):
            res = analyze_stock_full(sym)
            if res and res['Điểm'] >= min_score:
                results.append(res)
            bar.progress((i+1)/len(symbols))
            
        if results:
            df_res = pd.DataFrame(results).sort_values(by="Điểm", ascending=False)
            st.session_state['results'] = df_res
            st.session_state['raw_data'] = results
        else:
            st.session_state['results'] = None
            
    st.session_state['trigger'] = False

# HIỂN THỊ KẾT QUẢ TỪ SESSION STATE
if 'results' in st.session_state and st.session_state['results'] is not None:
    df = st.session_state['results']
    data_list = st.session_state['raw_data']
    
    st.success(f"✅ Tìm thấy {len(df)} mã tiềm năng (Vừa có Trend, vừa có Cơ bản tốt)!")
    
    # 1. BẢNG DỮ LIỆU TỔNG HỢP
    st.dataframe(
        df[['Mã', 'Giá', 'Điểm', 'Xếp hạng', 'P/E', 'EPS', 'P/B', 'ROE', 'Cổ tức', 'Vốn hóa', 'Lý do']],
        use_container_width=True,
        height=400
    )
    
    st.divider()
    
    # 2. KHU VỰC SOI CHI TIẾT
    st.subheader("📊 HỒ SƠ DOANH NGHIỆP & BIỂU ĐỒ")
    c1, c2 = st.columns([1, 3])
    
    with c1:
        choice = st.selectbox("Chọn mã xem chi tiết:", df['Mã'].tolist())
        item = next((x for x in data_list if x["Mã"] == choice), None)
        
        if item:
            st.metric("Xếp hạng", item['Xếp hạng'], f"{item['Điểm']}/100")
            st.markdown("---")
            st.markdown(f"**💰 Giá:** {item['Giá']:,}")
            st.markdown(f"**📉 P/E:** {item['P/E']}")
            st.markdown(f"**💵 EPS:** {item['EPS']}")
            st.markdown(f"**📊 P/B:** {item['P/B']}")
            st.markdown(f"**🎁 Cổ tức:** {item['Cổ tức']}")
            st.markdown(f"**🏢 Vốn hóa:** {item['Vốn hóa']}")
            st.markdown(f"**📦 KLCP:** {item['KLCP Lưu hành']}")
            
            st.warning(f"🛑 Cắt lỗ: {item['Cắt Lỗ']}")
            st.success(f"🎯 Chốt lời: {item['Chốt Lời']}")
            
    with c2:
        if item:
            plot_chart(item)

elif 'results' in st.
