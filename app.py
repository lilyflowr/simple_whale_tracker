import os
import requests
import pandas as pd
import streamlit as st
import plotly.express as px
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()
ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY")

if not ALCHEMY_API_KEY:
    st.error("Missing ALCHEMY_API_KEY in .env")
    st.stop()

BASE_URL = f"https://eth-mainnet.g.alchemy.com/v2/{ALCHEMY_API_KEY}"
COINGECKO_URL = "https://api.coingecko.com/api/v3/simple/price?ids=ethereum&vs_currencies=usd"


st.set_page_config(page_title="ETH Whale Tracker", page_icon="🐋", layout="wide")

st.markdown("""
    <style>
    .main {
        background-color: #0d1117;
        color: white;
    }
    div[data-testid="stMetricValue"] {
        color: #00ffaa;
    }
    h1, h2, h3 {
        color: #00d4ff;
    }
    </style>
""", unsafe_allow_html=True)

st.title("🐋 Ethereum Whale Tracker Dashboard")

# Sidebar Controls
st.sidebar.header("⚙️ Settings")
MIN_ETH = st.sidebar.number_input("Minimum ETH to Track", value=10.0)
DAYS = st.sidebar.slider("Lookback Days", 1, 7, 1)

st.info(f"🔎 Fetching transfers ≥ {MIN_ETH} ETH from the past {DAYS} days...")


latest_block_resp = requests.post(BASE_URL, json={
    "jsonrpc": "2.0",
    "id": 1,
    "method": "eth_blockNumber",
    "params": []
})
latest_block = int(latest_block_resp.json()["result"], 16)

blocks_back = DAYS * 7200
from_block = max(0, latest_block - blocks_back)

payload = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "alchemy_getAssetTransfers",
    "params": [{
        "fromBlock": hex(from_block),
        "toBlock": "latest",
        "category": ["external"],
        "withMetadata": True,
        "maxCount": "0x64",
        "excludeZeroValue": True
    }]
}

try:
    resp = requests.post(BASE_URL, json=payload)
    resp.raise_for_status()
    data = resp.json()
    transfers = data.get("result", {}).get("transfers", [])

    if not transfers:
        st.warning("No ETH transactions found in this range.")
        st.stop()

    df = pd.DataFrame(transfers)
    df = df[df["asset"] == "ETH"]
    df["value_eth"] = pd.to_numeric(df["value"], errors="coerce")
    df = df[df["value_eth"] >= MIN_ETH]

    if len(df) == 0:
        st.warning(f"No transactions ≥ {MIN_ETH} ETH in last {DAYS} days.")
        st.stop()


    # Live Price
    price_data = requests.get(COINGECKO_URL).json()
    eth_usd = price_data.get("ethereum", {}).get("usd", 0)

    df["value_usd"] = df["value_eth"] * eth_usd
    df["tx_link"] = "https://etherscan.io/tx/" + df["hash"]

    total_eth = df["value_eth"].sum()
    total_usd = df["value_usd"].sum()
    total_txs = len(df)
    top_whales = df.groupby("from")["value_eth"].sum().sort_values(ascending=False).head(10)

    col1, col2, col3 = st.columns(3)
    col1.metric("💰 Total ETH Moved", f"{total_eth:,.2f} ETH")
    col2.metric("💵 USD Value", f"${total_usd:,.2f}")
    col3.metric("📊 Total Transactions", f"{total_txs}")


    st.subheader("🏦 Top 10 Whale Addresses (by ETH Sent)")
    fig1 = px.bar(
        top_whales,
        x=top_whales.index,
        y=top_whales.values,
        color=top_whales.values,
        color_continuous_scale="teal",
        labels={"x": "Whale Address", "y": "Total ETH Sent"},
        title="Top 10 Whales"
    )
    st.plotly_chart(fig1, use_container_width=True)

    # Volume by destination
    st.subheader("🎯 Top Receivers (by Total ETH Received)")
    top_receivers = df.groupby("to")["value_eth"].sum().sort_values(ascending=False).head(10)
    fig2 = px.bar(
        top_receivers,
        x=top_receivers.index,
        y=top_receivers.values,
        color=top_receivers.values,
        color_continuous_scale="mint",
        labels={"x": "Receiver", "y": "ETH Received"},
        title="Top Receivers"
    )
    st.plotly_chart(fig2, use_container_width=True)


    st.subheader("📋 Whale Transactions")
    st.dataframe(df[["from", "to", "value_eth", "value_usd", "tx_link"]])

  #export
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label="⬇️ Download CSV Data",
        data=csv,
        file_name="whale_transactions.csv",
        mime="text/csv",
    )

except Exception as e:
    st.error(f"Error fetching data: {e}")
