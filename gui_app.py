import streamlit as st
import trading_bot as tb
import os
import matplotlib.pyplot as plt
import pandas as pd

# --- Streamlit Page Settings ---
st.set_page_config(
    page_title="Binance Portfolio Dashboard",
    layout="wide",
    page_icon="💹"
)

# --- Custom Dark Theme + Animated Banners ---
st.markdown(
    """
    <style>
    body {
        color: #E0E0E0;
        background-color: #0E1117;
    }
    .main {
        background-color: #0E1117;
        padding: 20px;
    }
    h1, h2, h3 {
        color: #33FF9C;
        margin-top: 25px;
        margin-bottom: 15px;
    }
    .stButton>button {
        background-color: #33FF9C;
        color: #000000;
        border-radius: 8px;
        border: none;
        font-weight: bold;
        padding: 0.4em 1em;
    }
    .stButton>button:hover {
        background-color: #28CC7A;
        color: #FFFFFF;
    }
    .banner {
        animation: slideDown 0.6s ease-out;
        padding: 10px;
        border-radius: 8px;
        text-align: center;
        font-weight: bold;
        margin-bottom: 15px;
    }
    .banner-warning {
        background-color: #ff4d4d;
        color: white;
    }
    .banner-success {
        background-color: #33cc66;
        color: white;
    }
    @keyframes slideDown {
        0% { transform: translateY(-50px); opacity: 0; }
        100% { transform: translateY(0); opacity: 1; }
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Sidebar: Mode & API Configuration ---
st.sidebar.header("🔑 API Configuration")

mode = st.sidebar.radio("Select Mode:", ["Mock Mode", "Real Mode"], index=0)
use_real = mode == "Real Mode"

# --- API Key Input & Saving ---
if use_real:
    st.sidebar.success("🟢 Real Mode active — Binance Testnet connection enabled.")
    api_key_input = st.sidebar.text_input("Enter API Key", type="password")
    api_secret_input = st.sidebar.text_input("Enter API Secret", type="password")

    if st.sidebar.button("💾 Save API Keys"):
        if api_key_input and api_secret_input:
            st.session_state["api_key"] = api_key_input
            st.session_state["api_secret"] = api_secret_input
            st.sidebar.success("✅ API keys saved for this session.")
        else:
            st.sidebar.warning("⚠️ Please enter both API key and secret.")
else:
    st.sidebar.info("⚫ Mock Mode active — using local JSON data (no API keys required).")

# Load keys
api_key = st.session_state.get("api_key", os.getenv("BINANCE_API_KEY"))
api_secret = st.session_state.get("api_secret", os.getenv("BINANCE_API_SECRET"))

# --- Initialize bot ---
bot = None
connection_error = None
connected = False

if use_real:
    try:
        if api_key and api_secret:
            bot = tb.build_bot(api_key=api_key, api_secret=api_secret, use_real=True)
            connected = True
        else:
            connection_error = "🚫 No API connection detected — please enter your Binance Testnet API keys in the sidebar."
    except Exception as e:
        connection_error = f"❌ Failed to connect to Binance API: {e}"
else:
    bot = tb.build_bot(api_key=None, api_secret=None, use_real=False)

# --- Display banners ---
if use_real and not st.session_state.get("hide_banner", False):
    if connection_error:
        # Red warning banner
        col1, col2 = st.columns([0.9, 0.1])
        with col1:
            st.markdown(
                f"<div class='banner banner-warning'>{connection_error}</div>",
                unsafe_allow_html=True
            )
        with col2:
            if st.button("Dismiss", key="dismiss_banner"):
                st.session_state["hide_banner"] = True
    elif connected:
        # Green success banner
        st.markdown(
            "<div class='banner banner-success'>🟢 Connected to Binance Testnet — Live Mode Active</div>",
            unsafe_allow_html=True
        )

# --- Dynamic Title ---
if use_real:
    st.title("💹 Binance Portfolio Dashboard — Real Mode")
    st.markdown("### Live Binance Testnet trading environment.")
else:
    st.title("💹 Binance Portfolio Dashboard — Mock Mode")
    st.markdown("### Offline simulation using mock Binance data.")
st.markdown("---")

# --- Sidebar Menu ---
st.sidebar.header("📊 Actions")
action = st.sidebar.radio(
    "Choose an option:",
    ["View Prices", "Portfolio", "Buy", "Sell", "Calc Size"]
)

# --- View Prices ---
if action == "View Prices":
    st.subheader("📈 Current Market Prices")

    if use_real and not connected:
        df_unavailable = pd.DataFrame({
            "symbol": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
            "price": ["Unavailable (no API connection)"] * 4
        })
        st.table(df_unavailable)
    else:
        try:
            prices = bot.get_all_prices()
            st.table(prices)
            if not use_real:
                st.caption("Showing simulated prices — switch to Real Mode for live data.")
        except Exception:
            st.error("❌ Unable to fetch prices from Binance API.")
            df_unavailable = pd.DataFrame({
                "symbol": ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"],
                "price": ["Unavailable (API error)"] * 4
            })
            st.table(df_unavailable)

# --- Portfolio Overview ---
elif action == "Portfolio":
    st.subheader("💼 Portfolio Overview")
    try:
        bal = bot.show_balance() if bot else {}
        st.json(bal)
        if not use_real:
            st.caption("Mock balance stored locally in `data/mock_balance.json`")

        if bal:
            st.markdown("#### Portfolio Distribution")
            labels = list(bal.keys())
            values = list(bal.values())

            fig, ax = plt.subplots(facecolor="#0E1117")
            wedges, texts, autotexts = ax.pie(
                values,
                labels=labels,
                autopct="%1.1f%%",
                startangle=90,
                colors=["#33FF9C", "#009EFF", "#FF5C5C", "#FFD43B", "#AB63FA"]
            )
            for text in texts + autotexts:
                text.set_color("white")
            ax.axis("equal")
            st.pyplot(fig)
    except Exception as e:
        st.error(f"❌ Could not retrieve portfolio: {e}")

# --- Buy Order ---
elif action == "Buy":
    st.subheader("🟢 Buy Order")
    try:
        prices = bot.get_all_prices()
        symbols = [p["symbol"] for p in prices]
    except Exception:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    symbol = st.selectbox("Select Symbol", symbols)
    amount = st.number_input("Amount to Buy", min_value=0.001, step=0.001, format="%.6f")

    if st.button("🚀 Execute Buy"):
        try:
            res = bot.place_market_order(symbol, tb.SIDE_BUY, float(amount))
            st.success(f"✅ Bought {amount} {symbol.replace('USDT','')} successfully.")
            st.json(res)
        except Exception as e:
            st.error(f"❌ Error: {e}")

# --- Sell Order ---
elif action == "Sell":
    st.subheader("🔴 Sell Order")
    try:
        prices = bot.get_all_prices()
        symbols = [p["symbol"] for p in prices]
    except Exception:
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT"]

    symbol = st.selectbox("Select Symbol", symbols)
    amount = st.number_input("Amount to Sell", min_value=0.001, step=0.001, format="%.6f")

    if st.button("📉 Execute Sell"):
        try:
            res = bot.place_market_order(symbol, tb.SIDE_SELL, float(amount))
            st.success(f"✅ Sold {amount} {symbol.replace('USDT','')} successfully.")
            st.json(res)
        except Exception as e:
            st.error(f"❌ Error: {e}")

# --- Position Size Calculator ---
elif action == "Calc Size":
    st.subheader("🧮 Position Size Calculator")
    symbol = st.text_input("Symbol (e.g., BTCUSDT)", value="BTCUSDT")
    risk = st.number_input("Risk % of balance", value=1.0, min_value=0.1, step=0.1)
    stop = st.number_input("Stop Loss (fraction, e.g. 0.01 = 1%)", value=0.01, step=0.005)
    lev = st.number_input("Leverage", value=1, min_value=1, step=1)

    if st.button("📏 Calculate Size"):
        try:
            qty, price = tb.calculate_position_size(bot, symbol.upper(), risk, stop, int(lev))
            st.success(f"📊 Quantity: **{qty:.6f}** units @ **{price:.2f} USDT**")
        except Exception as e:
            st.error(f"❌ Error: {e}")

# --- Footer ---
st.markdown("---")
if use_real:
    st.caption("🟢 Real Mode | Connected to Binance Testnet | Built with Streamlit & Python 3.11+")
else:
    st.caption("⚫ Mock Mode | Using simulated data | Built with Streamlit & Python 3.11+")
