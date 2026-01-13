
# -*- coding: utf-8 -*-
"""
AI Stock Sniper (VN) – Clean Rebuild
- Provider: Yahoo (default) / VNStock (optional)
- Proper intraday merge to daily OHLCV
- Indicators: SMA20/50/200, RSI14, ATR22, Donchian55
- Risk: ATR-based SL/TP, position sizing by %risk
- Streamlit UI with caching & progress
"""

import streamlit as st
import pandas as pd
import pandas_ta as ta
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import pytz

# ======================
# 1) PAGE CONFIG & STYLE
# ======================
st.set_page_config(
    page_title="AI Stock Sniper (VN) – Clean",
    layout="wide",
    page_icon="⚡",
    initial_sidebar_state="expanded"
)
st.markdown(
    """
    <style>
    .stProgress > div > div > div > div { background-color: #4CAF50; }
    .metrics { font-size: 14px; }
    </style>
    """,
    unsafe_allow_html=True
)

# ==========================================
# 2) DATA PROVIDERS & INTRADAY MERGE LOGIC
# ==========================================
class DataProvider:
    def __init__(self, provider: str = "yahoo", yahoo_suffix: str = ".VN"):
        """
        provider: 'yahoo' | 'vnstock'
        yahoo_suffix: default '.VN' for Vietnam tickers on Yahoo
        """
        self.provider = provider.lower()
        self.yahoo_suffix = yahoo_suffix
        self.vnstock_ok = False
        if self.provider == "vnstock":
            try:
                # Lazy import to avoid hard dependency
                from vnstock import stock_historical_data  # noqa: F401
                self.vnstock_ok = True
            except Exception:
                self.vnstock_ok = False
                st.warning("⚠️ Không tìm thấy thư viện 'vnstock'. Sử dụng Yahoo thay thế.")

    def _yahoo_symbol(self, symbol: str) -> str:
        """Append suffix if not present (best-effort)."""
        s = symbol.strip().upper()
        if not s.endswith(self.yahoo_suffix):
            s = s + self.yahoo_suffix
        return s

    def fetch_daily(self, symbol: str, lookback_days: int = 365) -> pd.DataFrame:
        """
        Fetch daily OHLCV for the last `lookback_days`.
        Return DataFrame with columns: Open, High, Low, Close, Volume, and Datetime index.
        """
        tz_vn = pytz.timezone('Asia/Ho_Chi_Minh')
        now_vn = datetime.now(tz_vn)
        end_date = now_vn + timedelta(days=1)  # ensure today included
        start_date = now_vn - timedelta(days=lookback_days)

        if self.provider == "vnstock" and self.vnstock_ok:
            try:
                from vnstock import stock_historical_data
                df = stock_historical_data(
                    symbol.strip().upper(),
                    start_date.strftime("%Y-%m-%d"),
                    end_date.strftime("%Y-%m-%d"),
                    "1D"
                )
                # Normalize column names
                cols_map = {
                    'open': 'Open', 'high': 'High', 'low': 'Low',
                    'close': 'Close', 'volume': 'Volume'
                }
                df = df.rename(columns=lambda c: cols_map.get(c.lower(), c))
                df.index = pd.to_datetime(df.index)
                return df[['Open','High','Low','Close','Volume']].sort_index()
            except Exception as e:
                st.warning(f"VNStock daily lỗi: {e}. Chuyển sang Yahoo.")
                # fallthrough to yahoo

        # Yahoo fallback
        ysym = self._yahoo_symbol(symbol)
        df = yf.Ticker(ysym).history(start=start_date, end=end_date, interval="1d")
        if df is None or df.empty:
            return pd.DataFrame()
        # Standardize columns
        df = df.rename(columns=str.title)
        return df[['Open','High','Low','Close','Volume']].sort_index()

    def fetch_intraday_today(self, symbol: str, interval: str = "1m") -> pd.DataFrame:
        """
        Fetch today's intraday data (1m by default) and normalize OHLCV.
        Intraday limits apply on Yahoo; VNStock route can be implemented when available.
        """
        if self.provider == "vnstock" and self.vnstock_ok:
            # NOTE: vnstock intraday API may vary; if available, implement here.
            # For now, we return empty to avoid broken assumptions.
            return pd.DataFrame()

        # Yahoo fallback
        ysym = self._yahoo_symbol(symbol)
        try:
            df_i = yf.Ticker(ysym).history(period="1d", interval=interval)
            if df_i is None or df_i.empty:
                return pd.DataFrame()
            df_i = df_i.rename(columns=str.title)
            return df_i[['Open','High','Low','Close','Volume']].sort_index()
        except Exception:
            return pd.DataFrame()

def merge_intraday_to_daily(df_day: pd.DataFrame, df_intraday: pd.DataFrame) -> pd.DataFrame:
    """
    Update the last daily bar using intraday OHLCV for accuracy.
    - Close = last intraday Close
    - High = max intraday High
    - Low  = min intraday Low
    - Open = first intraday Open
    - Volume = sum intraday Volume
    """
    if df_day is None or df_day.empty:
        return df_day
    if df_intraday is None or df_intraday.empty:
        return df_day

    # Identify today's row to update
    last_idx = df_day.index[-1]
    try:
        o = float(df_intraday["Open"].iloc[0])
        h = float(df_intraday["High"].max())
        l = float(df_intraday["Low"].min())
        c = float(df_intraday["Close"].iloc[-1])
        v = float(df_intraday["Volume"].fillna(0).sum())

        df_day.loc[last_idx, ["Open", "High", "Low", "Close", "Volume"]] = [o, h, l, c, v]
    except Exception:
        pass
    return df_day

# ==============================
# 3) INDICATORS & STRATEGY LOGIC
# ==============================
def add_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    Add SMA20/50/200, RSI14, ATR22, Donchian(55).
    """
    df["SMA20"] = ta.sma(df["Close"], length=20)
    df["SMA50"] = ta.sma(df["Close"], length=50)
    df["SMA200"] = ta.sma(df["Close"], length=200)
    df["RSI14"] = ta.rsi(df["Close"], length=14)
    df["ATR22"] = ta.atr(df["High"], df["Low"], df["Close"], length=22)

    dc = ta.donchian(df["High"], df["Low"], lower_length=55, upper_length=55)
    # Some pandas_ta versions return different column names; handle robustly:
    dcU = [c for c in dc.columns if "U" in c.upper()]
    dcL = [c for c in dc.columns if "L" in c.upper()]
    df["DCU"] = dc[dcU[0]] if dcU else pd.NA
    df["DCL"] = dc[dcL[0]] if dcL else pd.NA
    return df

def compute_liquidity(df: pd.DataFrame) -> float:
    """
    Average Turnover (Close*Volume) in VND over last 20 bars, returned in billions.
    """
    turnover = df["Close"] * df["Volume"]
    avg_val_20 = turnover.rolling(window=20).mean().iloc[-1]
    return (avg_val_20 or 0.0) / 1_000_000_000

def score_and_plan(df: pd.DataFrame, min_liq_bil: float, risk_pct: float, capital_vnd: float):
    """
    Build recommendation & trade plan using rule-based checks.
