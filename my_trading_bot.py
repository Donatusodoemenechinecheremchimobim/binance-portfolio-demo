"""
Trading Bot (CLI + Mock Binance Portfolio)
------------------------------------------
Simulates a Binance futures trading bot that works offline or with Binance Testnet API.

Features:
- Mock trading (no API keys needed)
- Position size calculation
- Buy/Sell simulation
- CLI interface for quick testing
- Colored logging (console) + file logs
- Built-in color log test utility
"""

import argparse
import json
import logging
import os
from datetime import datetime
from pathlib import Path

# --- Try to import colorlog for pretty logs ---
try:
    import colorlog
except ImportError:
    colorlog = None

# --- Optional: Binance client (if available) ---
try:
    from binance.client import Client
    from binance.enums import *
except ImportError:
    Client = None

# --- Constants ---
SIDE_BUY = "BUY"
SIDE_SELL = "SELL"
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "bot.log"


# ==========================
# Logging Configuration
# ==========================
def setup_logger():
    """Set up colorized logger for console and plain text logger for file."""
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Remove previous handlers (avoid duplication)
    for h in logger.handlers[:]:
        logger.removeHandler(h)

    # File handler (writes everything)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    file_handler.setFormatter(file_formatter)

    # Console handler (colored)
    console_handler = logging.StreamHandler()
    if colorlog:
        color_formatter = colorlog.ColoredFormatter(
            "%(log_color)s%(asctime)s [%(levelname)s]%(reset)s %(message_log_color)s%(message)s",
            datefmt="%H:%M:%S",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
            secondary_log_colors={
                "message": {
                    "INFO": "white",
                    "WARNING": "yellow",
                    "ERROR": "red",
                    "CRITICAL": "red",
                }
            },
        )
        console_handler.setFormatter(color_formatter)
    else:
        console_handler.setFormatter(file_formatter)

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    # Test the logger setup visually
    print("🔍 Logger initialized with handlers:", [type(h).__name__ for h in logger.handlers])
    return logger


# ✅ Initialize logger before any other code uses it
logger = setup_logger()


# ==========================
# Mock Bot Implementation
# ==========================
class MockFuturesBot:
    """Simulates Binance Futures trading for testing and portfolios."""

    def __init__(self):
        self.balance_file = DATA_DIR / "mock_balance.json"
        self.price_file = DATA_DIR / "mock_prices.json"

        if not self.balance_file.exists():
            with open(self.balance_file, "w") as f:
                json.dump({"USDT": 1000.0, "BTC": 0.0, "ETH": 0.0}, f, indent=2)

        if not self.price_file.exists():
            with open(self.price_file, "w") as f:
                json.dump(
                    [
                        {"symbol": "BTCUSDT", "price": 68000.0},
                        {"symbol": "ETHUSDT", "price": 3200.0},
                        {"symbol": "BNBUSDT", "price": 560.0},
                    ],
                    f,
                    indent=2,
                )

        logger.info("Initialized Mock Futures Bot.")

    def _load_balance(self):
        with open(self.balance_file) as f:
            return json.load(f)

    def _save_balance(self, bal):
        with open(self.balance_file, "w") as f:
            json.dump(bal, f, indent=2)

    def get_all_prices(self):
        with open(self.price_file) as f:
            prices = json.load(f)
        return prices

    def get_price(self, symbol: str):
        for p in self.get_all_prices():
            if p["symbol"] == symbol.upper():
                return p["price"]
        raise ValueError(f"Symbol {symbol} not found")

    def place_market_order(self, symbol: str, side: str, amount: float):
        bal = self._load_balance()
        price = self.get_price(symbol)
        base = symbol.replace("USDT", "")

        if side == SIDE_BUY:
            cost = price * amount
            if bal["USDT"] >= cost:
                bal["USDT"] -= cost
                bal[base] = bal.get(base, 0) + amount
                msg = f"Bought {amount} {base} for {cost:.2f} USDT"
                logger.info(msg)
            else:
                logger.error("Not enough USDT balance.")
                raise ValueError("Not enough USDT balance.")

        elif side == SIDE_SELL:
            if bal.get(base, 0) >= amount:
                bal["USDT"] += price * amount
                bal[base] -= amount
                msg = f"Sold {amount} {base} for {price * amount:.2f} USDT"
                logger.info(msg)
            else:
                logger.error(f"Not enough {base} balance.")
                raise ValueError(f"Not enough {base} balance.")
        else:
            logger.error("Invalid order side.")
            raise ValueError("Invalid side. Use BUY or SELL.")

        self._save_balance(bal)
        return {
            "symbol": symbol,
            "side": side,
            "amount": amount,
            "price": price,
            "timestamp": datetime.utcnow().isoformat(),
        }

    def show_balance(self):
        bal = self._load_balance()
        logger.info("Balance checked.")
        return bal


# ==========================
# Real Binance Bot
# ==========================
class RealFuturesBot:
    """Connects to Binance Testnet or Live."""

    def __init__(self, api_key, api_secret, testnet=True):
        if not Client:
            raise ImportError("Binance package not installed. Run: pip install python-binance")
        self.client = Client(api_key, api_secret, testnet=testnet)
        logger.info(f"Connected to Binance {'Testnet' if testnet else 'Live'}")

    def get_all_prices(self):
        prices = self.client.futures_symbol_ticker()
        return [{"symbol": p["symbol"], "price": float(p["price"])} for p in prices]

    def get_price(self, symbol):
        ticker = self.client.futures_symbol_ticker(symbol=symbol)
        return float(ticker["price"])

    def place_market_order(self, symbol, side, amount):
        order = self.client.futures_create_order(symbol=symbol, side=side, type="MARKET", quantity=amount)
        logger.info(f"Executed {side} order for {symbol}, qty={amount}")
        return order

    def show_balance(self):
        balances = self.client.futures_account_balance()
        logger.info("Fetched live futures account balance.")
        return balances


# ==========================
# Utility: Build Bot
# ==========================
def build_bot(api_key=None, api_secret=None, use_real=False):
    if use_real and api_key and api_secret:
        return RealFuturesBot(api_key, api_secret, testnet=True)
    else:
        return MockFuturesBot()


# ==========================
# Utility: Position Size Calculator
# ==========================
def calculate_position_size(bot, symbol: str, risk_pct: float, stop_loss_pct: float, leverage: int = 1):
    """Calculate position size given risk %, stop loss, and leverage."""
    balance = bot.show_balance()
    usdt_balance = balance.get("USDT", 0)
    price = bot.get_price(symbol)
    risk_amount = usdt_balance * (risk_pct / 100)
    position_size = (risk_amount * leverage) / (price * stop_loss_pct)
    logger.info(f"Calculated position size: {position_size:.6f} {symbol} @ {price:.2f} USDT")
    return position_size, price


# ==========================
# CLI Interface
# ==========================
def main():
    parser = argparse.ArgumentParser(description="Mock Binance Portfolio Trading Bot CLI")
    parser.add_argument("command", choices=["prices", "balance", "buy", "sell", "calc", "testlog"], help="Command to run")
    parser.add_argument("--symbol", help="Symbol (e.g., BTCUSDT)")
    parser.add_argument("--amount", type=float, help="Amount to trade")
    parser.add_argument("--risk", type=float, help="Risk percent for position sizing")
    parser.add_argument("--stop", type=float, help="Stop loss percent (e.g. 0.01 = 1%)")
    parser.add_argument("--leverage", type=int, default=1, help="Leverage")
    parser.add_argument("--api-key", help="Binance API Key")
    parser.add_argument("--api-secret", help="Binance API Secret")
    parser.add_argument("--use-real", action="store_true", help="Use Binance Testnet instead of mock")

    args = parser.parse_args()

    # 🧪 Built-in logger color test
    if args.command == "testlog":
        logger.debug("This is a DEBUG message (cyan).")
        logger.info("This is an INFO message (green).")
        logger.warning("This is a WARNING message (yellow).")
        logger.error("This is an ERROR message (red).")
        logger.critical("This is a CRITICAL message (bold red).")
        print("\n✅ Check if colors display correctly above. If not, try CMD instead of PowerShell.\n")
        return

    bot = build_bot(args.api_key, args.api_secret, args.use_real)

    if args.command == "prices":
        print(json.dumps(bot.get_all_prices(), indent=2))

    elif args.command == "balance":
        print(json.dumps(bot.show_balance(), indent=2))

    elif args.command == "buy":
        if not args.symbol or not args.amount:
            logger.warning("Please provide --symbol and --amount")
            return
        order = bot.place_market_order(args.symbol, SIDE_BUY, args.amount)
        print(json.dumps(order, indent=2))

    elif args.command == "sell":
        if not args.symbol or not args.amount:
            logger.warning("Please provide --symbol and --amount")
            return
        order = bot.place_market_order(args.symbol, SIDE_SELL, args.amount)
        print(json.dumps(order, indent=2))

    elif args.command == "calc":
        if not args.symbol or not args.risk or not args.stop:
            logger.warning("Usage: python trading_bot.py calc --symbol BTCUSDT --risk 1 --stop 0.01 --leverage 5")
            return
        qty, price = calculate_position_size(bot, args.symbol, args.risk, args.stop, args.leverage)
        print(f"Position size: {qty:.6f} units at {price:.2f} USDT")


if __name__ == "__main__":
    main()
