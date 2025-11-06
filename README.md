# Binance Portfolio Demo (CLI + GUI)

A portfolio-ready demo that simulates a Binance futures trading bot.  
Works in restricted regions by running in **mock mode** (no API keys required). If you have `python-binance` and testnet keys you can enable real testnet mode.

## Features
- CLI: buy/sell/prices/balance/calc-size/trade (simulated)
- GUI: Streamlit app to view prices, portfolio and simulate trades
- Mock fallback (file-backed JSON): runs anywhere without Binance API access

## Quick start (mock mode)
```bash
git clone https://github.com/yourusername/binance-portfolio-demo.git
cd binance-portfolio-demo
python3 -m venv venv
source venv/bin/activate      # or venv\\Scripts\\activate on Windows
pip install -r requirements.txt
# Run CLI examples
python trading_bot.py prices
python trading_bot.py balance
python trading_bot.py buy BTCUSDT 0.001
python trading_bot.py sell BTCUSDT 0.001
# Run GUI
streamlit run gui_app.py
