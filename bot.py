import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import time

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(
    page_title="AI Stock Pro (Full Market)",
    layout="wide",
    page_icon="🔥",
    initial_sidebar_state="expanded"
)

# --- CSS TÙY CHỈNH (GIAO DIỆN ĐẸP) ---
st.markdown("""
<style>
    .main {background-color: #f4f6f9;}
    div[data-testid="stMetric"] {
        background-color: white; border: 1px solid #ddd; padding: 10px; border-radius: 8px;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] {
        background-color: white; border-radius: 5px; padding: 10px 20px;
    }
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        background-color: #e3f2fd; color: #1976d2; border: 1px solid #1976d2;
    }
    .stButton>button {
        background-color: #0e1117; color: white; border-radius: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 2. KHO DỮ LIỆU CỔ PHIẾU (ĐẦY ĐỦ NHẤT) ---

def get_market_symbols(selected_groups):
    # 1. CÁC CHỈ SỐ LỚN
    vn30 = ["ACB", "BCM", "BID", "BVH", "CTG", "FPT", "GAS", "GVR", "HDB", "HPG", "MBB", "MSN", "MWG", "PLX", "POW", "SAB", "SHB", "SSB", "SSI", "STB", "TCB", "TPB", "VCB", "VHM", "VIB", "VIC", "VJC", "VNM", "VPB", "VRE"]
    
    hnx30 = ["CEO", "DTD", "HUT", "IDC", "L14", "L18", "MBS", "PVS", "SHS", "TNG", "VC3", "VGS", "APS", "API", "IDJ", "BVS", "LAS", "PVC", "DDG"]
    
    # VN100 = VN30 + 70 Midcap lớn nhất HOSE (Danh sách mô phỏng)
    vn100_mid = ["DGC", "VHC", "ANV", "KBC", "DIG", "DXG", "PDR", "NLG", "KDH", "VCI", "VND", "HCM", "VIX", "GMD", "REE", "PC1", "GEG", "NT2", "HDG", "PVT", "PTB", "DGW", "FRT", "PET", "HAH", "DPM", "DCM", "CSV", "PAN", "VPI", "SJS", "EIB", "LPB", "MSB", "OCB", "VDS", "ORS", "FTS", "BSI", "CTS", "AGR", "IJC", "HDC", "SZC", "TCH", "KHG", "HHV", "LCG", "VCG", "VGC", "SBT", "HAG", "DBC"]
    vn100 = list(set(vn30 + vn100_mid))

    # 2. NHÓM NGÀNH CHI TIẾT
    groups = {
        "Ngân hàng": ["VCB", "BID", "CTG", "TCB", "VPB", "MBB", "ACB", "STB", "HDB", "SHB", "SSB", "MSB", "OCB", "TPB", "VIB", "LPB", "EIB", "BAB", "NAB", "BVB", "ABB"],
        "Chứng khoán": ["SSI", "VND", "VCI", "HCM", "SHS", "MBS", "FTS", "BSI", "CTS", "VIX", "ORS", "AGR", "VDS", "BVS", "APS", "TVS"],
        "Bất động sản": ["VHM", "VIC", "VRE", "NVL", "PDR", "KDH", "DIG", "CEO", "DXG", "NLG", "HDG", "TCH", "IJC", "HDC", "KHG", "DXS", "CRE", "SCR", "HQC"],
        "BĐS Công nghiệp": ["KBC", "IDC", "SZC", "GVR", "PHR", "NTC", "SIP", "VGC", "BCM", "ITA", "D2D", "LHG", "TIP"],
        "Thép": ["HPG", "HSG", "NKG", "VGS", "TLH", "SMC", "TVN", "POM"],
        "Dầu khí": ["GAS", "PLX", "PVS", "PVD", "BSR", "OIL", "PVT", "PVC", "PVB", "CNG", "ASP"],
        "Thủy sản": ["VHC", "ANV", "FMC", "MPC", "IDI", "CMX", "ACL"],
        "Dệt may": ["TNG", "GIL", "MSH", "VGT", "STK", "ADS", "EVE"],
        # Nhóm đặc biệt: Nhà nước sở hữu >= 70% (Dựa trên dữ liệu sở hữu)
        "NN nắm >70%": ["GAS", "ACV", "GVR", "BSR", "OIL", "PLX", "VEA", "VGI", "VCB", "BID", "HVN", "DCM", "DPM", "PVM"]
    }

    final_list = []
    
    # Logic gộp danh sách
    if "QUÉT TOÀN BỘ" in selected_groups:
        # Gộp tất cả các list lại
        all_stocks = vn100 + hnx30
        for g in groups.values(): all_stocks += g
        final_list = all_stocks
    else:
        if "VN30" in selected_groups: final_list += vn30
        if "VN100" in selected_groups: final_list += vn100
        if "HNX30" in selected_groups: final_list += hnx30
        
        # Thêm các nhóm ngành được chọn
        for group_name, symbols in groups.items():
            if group_name in selected_groups:
                final_list += symbols

    # Lọc trùng và thêm đuôi .VN
    unique_list = list(set(final_list))
    return [f"{s}.VN" for s in unique_list if len(s) == 3] # Chỉ lấy mã 3 chữ cái hợp lệ

# --- 3. HÀM PHÂN TÍCH (LÕI XỬ LÝ) ---

@st.cache_data(ttl=600, show_spinner=False)
def fetch_stock_data_cached(symbol):
    try:
        if not symbol.endswith(".VN"): symbol += ".VN"
        ticker = yf.Ticker(symbol)
        
        df = pd.DataFrame()
        # Retry logic
        for _ in range(3):
            try:
                df = ticker.history(period="1y")
                if not df.empty: break
                time.sleep(0.5)
            except: time.sleep(0.5)
        
        if df.empty: return None, None, "No Data"

        info = {}
        try: info = ticker.info
        except: pass

        return df, info, None
    except Exception as e:
        return None, None, str(e)

def calculate_trade_plan(df, current_price):
    support_level = df['Low'].tail(20).min()
    risk_pct = (current_price - support_level) / current_price
    
    # Stoploss logic
    stop_loss = current_price * 0.93 if risk_pct > 0.07 else support_level
    
    # Take Profit (R:R = 1:2)
    risk_amt = current_price - stop_loss
    if risk_amt <= 0: risk_amt = current_price * 0.05
    take_profit = current_price + (risk_amt * 2)
    
    return int(stop_loss), int(take_profit)

def analyze_single_stock(symbol):
    df_raw, info, err = fetch_stock_data_cached(symbol)
    if err: return None, err
    
    try:
        df = df_raw.copy()
        
        # Chỉ báo kỹ thuật
        df['SMA_20'] = ta.sma(df['Close'], length=20)
        df['SMA_50'] = ta.sma(df['Close'], length=50)
        df['RSI'] = ta.rsi(df['Close'], length=14)
        
        latest = df.iloc[-1]
        
        # Chấm điểm
        score = 0
        reasons = []
        
        # Technical
        if latest['Close'] > latest['SMA_20']: score += 20; reasons.append("Giá > MA20")
        if latest['SMA_20'] > latest['SMA_50']: score += 20; reasons.append("Trend Tăng")
        if 50 <= latest['RSI'] <= 70: score += 10; reasons.append("RSI Mạnh")
        if latest['Volume'] > df['Volume'].tail(20).mean(): score += 20; reasons.append("Tiền vào")
        
        # Fundamental (P/E)
        pe = info.get('trailingPE', 0) if info else 0
        if pe and 5 < pe < 20: score += 15; reasons.append("P/E Tốt")
        
        # Trade Plan
        sl, tp = calculate_trade_plan(df, latest['Close'])
        
        # Khuyến nghị
        rec = "THEO DÕI"
        if score >= 80: rec = "MUA MẠNH"
        elif score >= 60: rec = "MUA"
        elif score < 40: rec = "BÁN"

        return {
            "Symbol": symbol.replace(".VN", ""),
            "Price": latest['Close'],
            "Score": score,
            "Rec": rec,
            "SL": sl,
            "TP": tp,
            "PE": round(pe, 1) if pe else 0,
            "Reasons": ", ".join(reasons),
            "DF": df
        }, None
    except Exception as e:
        return None, str(e)

# --- 4. VẼ BIỂU ĐỒ ---
def plot_chart_pro(data):
    df = data['DF']
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.03)

    # Nến
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'], name='Giá'), row=1, col=1)
    if 'SMA_20' in df.columns: fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'), row=1, col=1)
    
    # Plan Lines
    fig.add_hline(y=data['Price'], line_dash="dot", line_color="gray", annotation_text="ENTRY", row=1, col=1)
    fig.add_hline(y=data['SL'], line_dash="dash", line_color="red", annotation_text=f"SL: {data['SL']:,}", row=1, col=1)
    fig.add_hline(y=data['TP'], line_dash="dash", line_color="#00CC96", annotation_text=f"TP: {data['TP']:,}", row=1, col=1)

    # Vol
    colors = ['red' if row['Open'] > row['Close'] else 'green' for i, row in df.iterrows()]
    fig.add_trace(go.Bar(x=df.index, y=df['Volume'], marker_color=colors, name='Vol'), row=2, col=1)

    fig.update_layout(height=600, xaxis_rangeslider_visible=False, template="plotly_white", title=f"Chart: {data['Symbol']}")
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
st.title("🔥 AI STOCK SNIPER PRO (FULL MARKET)")

tab1, tab2 = st.tabs(["🔍 TRA CỨU MÃ", "⚡ BỘ LỌC THÔNG MINH"])

# === TAB 1: TRA CỨU ===
with tab1:
    col1, col2 = st.columns([3, 1])
    with col1:
        txt_symbol = st.text_input("Nhập mã (VD: GVR, IDC, PVS...):", "").upper()
    with col2:
        st.write("")
        st.write("")
        btn_check = st.button("PHÂN TÍCH NGAY", type="primary", use_container_width=True)

    if btn_check and txt_symbol:
        with st.spinner(f"Đang phân tích {txt_symbol}..."):
            d, e = analyze_single_stock(txt_symbol)
            if d:
                # Scorecard
                sc = d['Score']
                clr = "green" if sc >= 80 else "orange" if sc >= 60 else "red"
                
                c1, c2, c3, c4 = st.columns(4)
                c1.metric("Giá", f"{int(d['Price']):,} đ")
                c2.metric("Điểm AI", f"{sc}/100")
                c3.metric("P/E", d['PE'])
                c4.markdown(f"<h3 style='color:{clr}; text-align:center; border:1px solid {clr}; border-radius:5px'>{d['Rec']}</h3>", unsafe_allow_html=True)
                
                st.markdown("---")
                # Plan info
                cp1, cp2, cp3 = st.columns(3)
                cp1.success(f"🎯 TARGET: {d['TP']:,}")
                cp2.info(f"🔵 ENTRY: {int(d['Price']):,}")
                cp3.error(f"🛑 STOPLOSS: {d['SL']:,}")
                st.caption(f"Lý do: {d['Reasons']}")
                
                plot_chart_pro(d)
            elif e:
                st.error(f"Lỗi: {e}")

# === TAB 2: BỘ LỌC ===
with tab2:
    st.markdown("### ⚙️ Cấu Hình Quét")
    
    # DANH MỤC LỰA CHỌN MỚI
    all_sectors = [
        "QUÉT TOÀN BỘ", "VN30", "VN100", "HNX30",
        "Ngân hàng", "Chứng khoán", "Bất động sản", "BĐS Công nghiệp",
        "Thép", "Dầu khí", "Thủy sản", "Dệt may", 
        "NN nắm >70%"
    ]
    
    c_sel, c_sli = st.columns([2, 1])
    with c_sel:
        chosen_sectors = st.multiselect("Chọn nhóm ngành/Chỉ số:", all_sectors, default=["VN30", "Ngân hàng"])
    with c_sli:
        min_point = st.slider("Điểm tối thiểu:", 0, 100, 60)
        
    if st.button("🚀 BẮT ĐẦU QUÉT", type="primary"):
        # Lấy danh sách mã theo lựa chọn
        symbols = get_market_symbols(chosen_sectors)
        
        if not symbols:
            st.warning("Vui lòng chọn ít nhất một nhóm ngành.")
        else:
            st.toast(f"Đang quét {len(symbols)} mã...", icon="⏳")
            
            res_list = []
            bar = st.progress(0)
            status = st.empty()
            
            for i, s in enumerate(symbols):
                status.caption(f"Đang xử lý: {s} ({i+1}/{len(symbols)})")
                d, e = analyze_single_stock(s)
                if d and d['Score'] >= min_point:
                    res_list.append(d)
                bar.progress((i+1)/len(symbols))
            
            status.empty()
            
            if res_list:
                df_r = pd.DataFrame(res_list).sort_values(by="Score", ascending=False)
                st.success(f"Tìm thấy {len(df_r)} cơ hội đầu tư!")
                
                st.dataframe(
                    df_r[['Symbol', 'Price', 'Score', 'Rec', 'SL', 'TP', 'PE', 'Reasons']],
                    use_container_width=True,
                    column_config={
                        "Score": st.column_config.ProgressColumn("Điểm", max_value=100),
                        "Price": st.column_config.NumberColumn("Giá", format="%d"),
                        "SL": st.column_config.NumberColumn("Cắt Lỗ", format="%d"),
                        "TP": st.column_config.NumberColumn("Chốt Lời", format="%d"),
                    }
                )
            else:
                st.warning("Không tìm thấy mã nào đạt điểm yêu cầu.")

