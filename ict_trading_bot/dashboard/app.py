import streamlit as st
import pandas as pd
import time

# =========================
# PAGE CONFIG
# =========================
st.set_page_config(
    page_title="ICT Quant Dashboard",
    layout="wide"
)

st.title("📊 ICT Quant Trading Dashboard")

# =========================
# SESSION STATE
# =========================
if "trades" not in st.session_state:
    st.session_state.trades = []

# =========================
# SIDEBAR
# =========================
st.sidebar.header("⚙️ Controls")
auto_refresh = st.sidebar.checkbox("Auto Refresh", True)
refresh_rate = st.sidebar.slider("Refresh (sec)", 1, 10, 3)

# =========================
# MOCK LIVE DATA HOOK
# (replace with real engine feed)
# =========================
def get_live_trades():
    return st.session_state.trades

def get_portfolio_stats(trades):
    if not trades:
        return {}

    df = pd.DataFrame(trades)
    return {
        "Trades": len(df),
        "Win Rate": round((df["result"] > 0).mean() * 100, 2),
        "Avg R": round(df["result"].mean(), 2),
        "PnL": round(df["pnl"].sum(), 2)
    }

# =========================
# PORTFOLIO OVERVIEW
# =========================
st.subheader("📈 Portfolio Overview")

trades = get_live_trades()
stats = get_portfolio_stats(trades)

cols = st.columns(4)
for col, (k, v) in zip(cols, stats.items()):
    col.metric(k, v)

# =========================
# LIVE TRADES TABLE
# =========================
st.subheader("🟢 Live / Recent Trades")

if trades:
    df = pd.DataFrame(trades)
    st.dataframe(
        df[[
            "symbol",
            "direction",
            "entry",
            "sl",
            "tp",
            "ml_probability",
            "status"
        ]]
    )
else:
    st.info("No trades yet")

# =========================
# ML CONFIDENCE PANEL
# =========================
st.subheader("🧬 ML Confidence")

if trades:
    for t in trades[-5:]:
        st.progress(
            int(t["ml_probability"] * 100),
            text=f'{t["symbol"]} → {round(t["ml_probability"]*100,1)}%'
        )

# =========================
# AUTO REFRESH
# =========================
if auto_refresh:
    time.sleep(refresh_rate)
    st.rerun()
