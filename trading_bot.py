# trading_bot.py
"""
Unified trading bot module
- Provides a CLI for mock/testnet usage (prices, buy/sell, balance, calc-size, set-leverage)
- If python-binance is installed and API keys provided, can switch to real-client mode (testnet).
- Otherwise uses a MockClient backed by JSON files in data/
"""

import argparse
import json
from pathlib import Path
from datetime import datetime
import logging
import os
from decimal import Decimal, ROUND_DOWN
import trading_bot as tb


# Logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# Paths
PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)
PRICES_FILE = DATA_DIR / "mock_prices.json"
BALANCE_FILE = DATA_DIR / "mock_balance.json"

# Defaults (if files missing we'll create reasonable mock files)
DEFAULT_PRICES = [
    {"symbol": "BTCUSDT", "price": 68250.00},
    {"symbol": "ETHUSDT", "price": 3650.00},
    {"symbol": "BNBUSDT", "price": 590.00},
    {"symbol": "SOLUSDT", "price": 190.50}
]

DEFAULT_BALANCE = {"USDT": 10000.0, "BTC": 0.0, "ETH": 0.0, "BNB": 0.0, "SOL": 0.0}

# Create default files if missing
if not PRICES_FILE.exists():
    PRICES_FILE.write_text(json.dumps(DEFAULT_PRICES, indent=2))
if not BALANCE_FILE.exists():
    BALANCE_FILE.write_text(json.dumps(DEFAULT_BALANCE, indent=2))


# Try to import python-binance; if not available we will fallback to mock
try:
    from binance.client import Client
    from binance.enums import SIDE_BUY, SIDE_SELL
    from binance.exceptions import BinanceAPIException, BinanceOrderException
    BINANCE_AVAILABLE = True
except Exception:
    BINANCE_AVAILABLE = False
    # define constants so rest of code works
    SIDE_BUY = "BUY"
    SIDE_SELL = "SELL"


# ---------------------------
# Helper functions
# ---------------------------
def read_json(path: Path):
    with open(path, "r") as f:
        return json.load(f)


def write_json(path: Path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def round_dec(value, ndigits=6):
    # safer rounding for crypto qtys/prices
    q = Decimal(value).quantize(Decimal(10) ** -ndigits, rounding=ROUND_DOWN)
    return float(q)


# ---------------------------
# Mock client (file-backed)
# ---------------------------
class MockFuturesBot:
    def __init__(self):
        logging.info("Using MockFuturesBot (file-backed).")
        self.prices_file = PRICES_FILE
        self.balance_file = BALANCE_FILE

    def get_all_prices(self):
        return read_json(self.prices_file)

    def get_price(self, symbol):
        for p in self.get_all_prices():
            if p["symbol"].upper() == symbol.upper():
                return float(p["price"])
        return None

    def get_balance(self):
        b = read_json(self.balance_file)
        return b.get("USDT", 0.0)

    def show_balance(self):
        return read_json(self.balance_file)

    def save_balance(self, balance_dict):
        write_json(self.balance_file, balance_dict)

    def set_leverage(self, symbol, leverage):
        # mock does nothing but logs
        logging.info(f"(mock) set leverage {leverage}x for {symbol}")

    def place_market_order(self, symbol, side, quantity):
        # Modify local balance file accordingly (simulate market order)
        b = read_json(self.balance_file)
        symbol_base = symbol.replace("USDT", "")
        price = self.get_price(symbol)
        if price is None:
            raise ValueError("Symbol not found in mock prices")

        # Buy
        if side == SIDE_BUY:
            cost = quantity * price
            if b["USDT"] < cost:
                raise ValueError("Not enough USDT")
            b["USDT"] = round_dec(b["USDT"] - cost, 6)
            b[symbol_base] = round_dec(b.get(symbol_base, 0.0) + quantity, 8)
            write_json(self.balance_file, b)
            return {"status": "FILLED", "side": "BUY", "symbol": symbol, "price": price, "qty": quantity}

        # Sell
        elif side == SIDE_SELL:
            if b.get(symbol_base, 0.0) < quantity:
                raise ValueError(f"Not enough {symbol_base}")
            proceeds = quantity * price
            b[symbol_base] = round_dec(b.get(symbol_base, 0.0) - quantity, 8)
            b["USDT"] = round_dec(b["USDT"] + proceeds, 6)
            write_json(self.balance_file, b)
            return {"status": "FILLED", "side": "SELL", "symbol": symbol, "price": price, "qty": quantity}

    def futures_mark_price(self, symbol):
        # mimic binance client response shape
        price = self.get_price(symbol)
        return {"symbol": symbol, "markPrice": str(price)}


# ---------------------------
# Real Binance wrapper (thin)
# ---------------------------
class RealFuturesBot:
    def __init__(self, api_key, api_secret, testnet=True):
        if not BINANCE_AVAILABLE:
            raise RuntimeError("python-binance package not installed")
        logging.info("Initializing RealFuturesBot (python-binance).")
        self.client = Client(api_key, api_secret)
        if testnet:
            # by default python-binance uses mainnet; set testnet futures url if requested
            self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
        self.testnet = testnet

    def get_all_prices(self):
        # uses futures mark price endpoint to approximate
        infos = self.client.futures_mark_price()
        # limit to some standard symbols for portfolio demo
        symbols = ["BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT"]
        out = []
        for s in symbols:
            item = next((i for i in infos if i["symbol"] == s), None)
            if item:
                out.append({"symbol": s, "price": float(item["markPrice"])})
        return out

    def get_price(self, symbol):
        item = self.client.futures_mark_price(symbol=symbol)
        return float(item["markPrice"])

    def get_balance(self):
        account = self.client.futures_account_balance()
        usdt = next((i for i in account if i["asset"] == "USDT"), None)
        return float(usdt["balance"]) if usdt else 0.0

    def show_balance(self):
        account = self.client.futures_account_balance()
        # return whole structure for debugging
        return account

    def save_balance(self, *_):
        raise RuntimeError("Cannot save balance to file in real mode")

    def set_leverage(self, symbol, leverage):
        self.client.futures_change_leverage(symbol=symbol, leverage=leverage)

    def place_market_order(self, symbol, side, quantity):
        return self.client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=quantity)

    def futures_mark_price(self, symbol):
        return self.client.futures_mark_price(symbol=symbol)


# ---------------------------
# Factory
# ---------------------------
def build_bot(api_key=None, api_secret=None, use_real=False, testnet=True):
    # If user explicitly requests real mode and we have keys + python-binance -> RealFuturesBot
    if use_real and BINANCE_AVAILABLE and api_key and api_secret:
        return RealFuturesBot(api_key, api_secret, testnet=testnet)
    # Otherwise use mock
    return MockFuturesBot()


# ---------------------------
# Business logic utilities
# ---------------------------
def calculate_position_size(bot, symbol, risk_pct, stop_loss_pct, leverage):
    balance = bot.get_balance()
    if balance is None:
        raise ValueError("Failed to get account balance")
    risk_amount = balance * (risk_pct / 100.0)
    price_data = bot.futures_mark_price(symbol=symbol)
    current_price = float(price_data["markPrice"])
    stop_distance = current_price * stop_loss_pct
    qty = (risk_amount * leverage) / stop_distance
    # round qty to reasonable precision
    return round_dec(qty, 6), current_price


# ---------------------------
# CLI
# ---------------------------
def cli():
    parser = argparse.ArgumentParser(description="Unified Trading Bot (mock-able).")
    parser.add_argument("--api-key", type=str, default=os.getenv("BINANCE_API_KEY"))
    parser.add_argument("--api-secret", type=str, default=os.getenv("BINANCE_API_SECRET"))
    parser.add_argument("--use-real", action="store_true", help="Use real python-binance client (requires keys and python-binance).")
    parser.add_argument("--testnet", action="store_true", default=True, help="Default to testnet when using real client.")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("prices", help="List current market prices (mock or real depending on mode)")
    sub.add_parser("balance", help="Show portfolio balance (mock file or real futures balance)")
    buy_p = sub.add_parser("buy", help="Buy (mock) a symbol")
    buy_p.add_argument("symbol", type=str)
    buy_p.add_argument("amount", type=float)

    sell_p = sub.add_parser("sell", help="Sell (mock) a symbol")
    sell_p.add_argument("symbol", type=str)
    sell_p.add_argument("amount", type=float)

    setlev = sub.add_parser("set-leverage", help="Set leverage (mock logs action)")
    setlev.add_argument("symbol", type=str)
    setlev.add_argument("leverage", type=int)

    calc = sub.add_parser("calc-size", help="Calculate position size by risk parameters")
    calc.add_argument("symbol", type=str)
    calc.add_argument("--risk", type=float, default=1.0, help="Risk percent of balance")
    calc.add_argument("--stop", type=float, default=0.01, help="Stop loss percent (fraction, e.g., 0.01 = 1%)")
    calc.add_argument("--lev", type=int, default=1, help="Leverage")

    trade = sub.add_parser("trade", help="Full trade flow: calc -> place market -> set mock SL/TP (simulated)")
    trade.add_argument("symbol", type=str)
    trade.add_argument("--risk", type=float, default=1.0)
    trade.add_argument("--stop", type=float, default=0.01)
    trade.add_argument("--tp", type=float, default=0.02)
    trade.add_argument("--lev", type=int, default=1)
    trade.add_argument("--side", choices=[SIDE_BUY, SIDE_SELL], default=SIDE_BUY)

    args = parser.parse_args()

    bot = build_bot(api_key=args.api_key, api_secret=args.api_secret, use_real=args.use_real, testnet=args.testnet)

    if args.cmd == "prices":
        prices = bot.get_all_prices()
        print("📊 Market Prices:")
        for p in prices:
            print(f"{p['symbol']:10} {p['price']:>12}")
    elif args.cmd == "balance":
        bal = bot.show_balance()
        print("💼 Balance:")
        print(json.dumps(bal, indent=2))
    elif args.cmd == "buy":
        try:
            res = bot.place_market_order(args.symbol.upper(), SIDE_BUY, args.amount)
            print("✅ Buy executed:", res)
        except Exception as e:
            print("❌ Error:", e)
    elif args.cmd == "sell":
        try:
            res = bot.place_market_order(args.symbol.upper(), SIDE_SELL, args.amount)
            print("✅ Sell executed:", res)
        except Exception as e:
            print("❌ Error:", e)
    elif args.cmd == "set-leverage":
        bot.set_leverage(args.symbol.upper(), args.leverage)
        print(f"➡️  Set leverage (mock/real) for {args.symbol.upper()} to {args.leverage}x")
    elif args.cmd == "calc-size":
        qty, price = calculate_position_size(bot, args.symbol.upper(), args.risk, args.stop, args.lev)
        print(f"Calculated qty: {qty:.6f} @ price {price:.2f}")
    elif args.cmd == "trade":
        # steps: calc size -> place order -> compute sl/tp (mock only)
        qty, price = calculate_position_size(bot, args.symbol.upper(), args.risk, args.stop, args.lev)
        print(f"→ Calculated qty: {qty:.6f} @ price {price:.2f}")
        try:
            entry = bot.place_market_order(args.symbol.upper(), args.side, qty)
            print("→ Entry order result:", entry)
            sl_price = price * (1 - args.stop) if args.side == SIDE_BUY else price * (1 + args.stop)
            tp_price = price * (1 + args.tp) if args.side == SIDE_BUY else price * (1 - args.tp)
            # In mock mode we just print the SL/TP; real mode you'd call create orders with reduceOnly/closePosition
            print(f"→ (simulated) SL: {sl_price:.2f}, TP: {tp_price:.2f}")
        except Exception as e:
            print("❌ Trade error:", e)


if __name__ == "__main__":
    cli()
