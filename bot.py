import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from datetime import datetime, timedelta

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Sniper Pro (Trading Plan)", layout="wide", page_icon="🎯")
st.title("🎯 AI TRADING PLAN: TÍCH LŨY & ĐIỂM RA VÀO")
st.caption("Chiến lược: Nền giá siêu chặt (<15%) | Tự động tính Risk/Reward")

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

# --- 3. HÀM TÍNH TOÁN KẾ HOẠCH GIAO DỊCH ---
def analyze_stock_plan(symbol):
    try:
        # Lấy dữ liệu 1 năm
        df = yf.download(symbol, period="1y", progress=False)
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(1)
            
        if df is None or len(df) < 70: return None

        # Tính chỉ báo
        df.ta.sma(length=20, append=True)
        df.ta.sma(length=50, append=True)
        df.ta.rsi(length=14, append=True)
        
        latest = df.iloc[-1]
        
        # --- LOGIC TÍCH LŨY 3 THÁNG (<15%) ---
        df_3m = df.tail(60) # 60 phiên ~ 3 tháng
        max_price = df_3m['High'].max()
        min_price = df_3m['Low'].min()
        
        # Biên độ dao động
        fluctuation = (max_price - min_price) / min_price
        is_tight = fluctuation < 0.15  # ĐIỀU KIỆN MỚI: < 15%
        
        # --- CHẤM ĐIỂM ---
        score = 0
        reasons = []
        
        if latest['Close'] < 5000: return None # Bỏ penny rác

        # 1. Tích lũy (Quan trọng nhất)
        if is_tight:
            score += 50
            reasons.append(f"Nền siêu chặt ({round(fluctuation*100, 1)}%)")
        elif fluctuation < 0.20:
            score += 20
            reasons.append(f"Nền ổn ({round(fluctuation*100, 1)}%)")
            
        # 2. Xu hướng
        if latest['Close'] > latest['SMA_20'] and latest['SMA_20'] > latest['SMA_50']:
            score += 20
            reasons.append("Uptrend")
            
        # 3. Dòng tiền
        if latest['Volume'] > df['Volume'].tail(20).mean():
            score += 20
            reasons.append("Tiền vào")
            
        # 4. RSI
        if 40 <= latest['RSI_14'] <= 70: score += 10

        # --- LẬP KẾ HOẠCH TRADE (ENTRY - STOPLOSS - TARGET) ---
        # Stoploss: Thủng đáy hộp 3 tháng - 1% (cho phép sai số)
        stop_loss_price = int(min_price * 0.99)
        
        # Entry: Giá hiện tại
        current_price = int(latest['Close'])
        
        # Target: Kỳ vọng lãi gấp 3 lần lỗ (R:R = 1:3) hoặc tối thiểu 15%
        risk = current_price - stop_loss_price
        if risk <= 0: risk = current_price * 0.05 # Phòng hờ lỗi dữ liệu
        
        target_price = int(current_price + (risk * 3))
        # Nếu target quá thấp (<15%), ép target lên 15%
        if (target_price - current_price)/current_price < 0.15:
            target_price = int(current_price * 1.15)

        return {
            "Mã": symbol.replace(".VN", ""),
            "Giá Mua": f"{current_price:,}",
            "Cắt Lỗ": f"{stop_loss_price:,}",
            "Chốt Lời": f"{target_price:,}",
            "Biên độ": f"{round(fluctuation*100, 1)}%",
            "Điểm AI": score,
            "Lý do": ", ".join(reasons),
            "Dataframe": df,
            "Box_High": max_price, # Để vẽ biểu đồ
            "Box_Low": min_price
        }
    except:
        return None

# --- 4. VẼ BIỂU ĐỒ TRADE PLAN ---
def plot_trade_plan(data):
    df = data['Dataframe']
    symbol = data['Mã']
    
    fig = go.Figure()

    # 1. Nến giá
    fig.add_trace(go.Candlestick(x=df.index,
                open=df['Open'], high=df['High'],
                low=df['Low'], close=df['Close'], name='Giá'))
    
    # 2. Vùng Tích Lũy (Hộp Darvas)
    fig.add_hrect(y0=data['Box_Low'], y1=data['Box_High'], 
                  line_width=0, fillcolor="yellow", opacity=0.15,
                  annotation_text="Vùng Gom Hàng (3 Tháng)")

    # 3. Đường Cắt Lỗ (Đỏ)
    sl_price = int(data['Cắt Lỗ'].replace(",",""))
    fig.add_hline(y=sl_price, line_dash="dash", line_color="red", 
                  annotation_text=f"STOPLOSS: {sl_price:,}", annotation_position="bottom right")

    # 4. Đường Chốt Lời (Xanh lá)
    tp_price = int(data['Chốt Lời'].replace(",",""))
    fig.add_hline(y=tp_price, line_dash="dash", line_color="green", 
                  annotation_text=f"TARGET: {tp_price:,}", annotation_position="top right")

    # 5. MA20, MA50
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_20'], line=dict(color='orange', width=1), name='MA20'))
    
    fig.update_layout(title=f"KẾ HOẠCH GIAO DỊCH: {symbol} (R:R Tối ưu)", 
                      xaxis_rangeslider_visible=False, height=550)
    st.plotly_chart(fig, use_container_width=True)

# --- 5. GIAO DIỆN CHÍNH ---
with st.sidebar:
    st.header("⚙️ THIẾT LẬP CHIẾN LƯỢC")
    min_score = st.slider("Điểm AI tối thiểu", 0, 100, 40)
    st.info("💡 Mẹo: Cổ phiếu có 'Biên độ' < 15% là những cơ hội tốt nhất.")
    
    if st.button("TÌM CƠ HỘI ĐẦU TƯ 🚀", type="primary"):
        run_app = True
    else:
        run_app = False

if run_app:
    symbols = get_symbol_list()
    status = st.status("🤖 AI đang tính toán điểm Mua/Bán...", expanded=True)
    
    results = []
    bar = status.progress(0)
    
    for i, sym in enumerate(symbols):
        data = analyze_stock_plan(sym)
        if data and data['Điểm AI'] >= min_score:
            results.append(data)
        bar.progress((i+1)/len(symbols))
        
    status.update(label="✅ Hoàn tất!", state="complete", expanded=False)
    
    if results:
        df_res = pd.DataFrame(results).sort_values(by="Điểm AI", ascending=False)
        
        st.success(f"Phát hiện {len(df_res)} mã tiềm năng!")
        
        # HIỂN THỊ BẢNG KẾ HOẠCH (Highlight các cột quan trọng)
        st.dataframe(
            df_res[['Mã', 'Giá Mua', 'Cắt Lỗ', 'Chốt Lời', 'Biên độ', 'Điểm AI', 'Lý do']],
            use_container_width=True
        )
        
        st.divider()
        st.subheader("📊 BIỂU ĐỒ KẾ HOẠCH GIAO DỊCH")
        col1, col2 = st.columns([1, 3])
        
        with col1:
            choice = st.radio("Chọn mã xem chi tiết:", df_res['Mã'])
            
            # Hiển thị lại thông số nhanh
            selected_data = next(item for item in results if item["Mã"] == choice)
            st.markdown("---")
            st.metric("Mục tiêu Lợi nhuận", selected_data['Chốt Lời'])
            st.metric("Rủi ro Cắt lỗ", selected_data['Cắt Lỗ'], delta_color="inverse")
            
        with col2:
            plot_trade_plan(selected_data)
            
    else:
        st.warning("Thị trường biến động mạnh! Không có mã nào tích lũy < 15% và đủ điểm.")
else:
    st.info("👈 Bấm nút để AI lập kế hoạch giao dịch cho bạn.")
