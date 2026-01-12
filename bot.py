import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
import time

# --- 1. CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="AI Pro Stock Scanner", layout="wide", page_icon="⚡")
st.title("⚡ HỆ THỐNG QUÉT CỔ PHIẾU (VN100 & MIDCAP)")
st.caption("Dữ liệu: VN30, VN100, Midcap, Thủy sản (MPC, VHC), Bank, Chứng, Thép...")

# --- 2. KHO DỮ LIỆU MỞ RỘNG (VN100 + MIDCAP) ---
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

    # 8. VN100 (Mô phỏng danh sách VN100)
    # Thực tế VN100 = VN30 + 70 Midcap lớn nhất. Ta gộp các list trên lại là đủ bao phủ.
    vn100_all = list(set(banks + securities + real_estate + steel + seafood + vn30_other + midcap))

    selected_symbols = []
    
    # Logic chọn ngành
    if "QUÉT TOÀN BỘ (ALL)" in sector_choice:
        selected_symbols = vn100_all
    else:
        if "Ngân hàng" in sector_choice: selected_symbols += banks
        if "Chứng khoán" in sector_choice: selected_symbols += securities
        if "Bất động sản" in sector_choice: selected_symbols += real_estate
        if "Thép" in sector_choice: selected_symbols += steel
        if "Thủy sản (MPC, VHC...)" in sector_choice: selected_symbols += seafood
        if "VN30" in sector_choice: selected_symbols += vn30_other
        if "Midcap Khác" in sector_choice: selected_symbols += midcap
        if "VN100" in sector_choice: selected_symbols += vn100_all

    # Lọc trùng và thêm đuôi .VN
    unique_symbols = list(set(selected_symbols))
    return [f"{sym}.VN" for sym in unique_symbols]

# --- 3. HÀM XỬ LÝ SỐ LIỆU ---
def safe_float(val):
    try:
        return float(val)
    except:
        return 0.0

def get_financial_info(ticker_obj):
    info = {}
    try:
        info = ticker_obj.info
    except:
        pass 
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
        
        # 2. LẤY CHỈ SỐ TÀI CHÍNH
        # Thêm độ trễ nhỏ
        time.sleep(0.1) 
        info = get_financial_info(ticker)
        
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
    fig.add_trace(go.Candlestick(x=df.index, open=df['Open
