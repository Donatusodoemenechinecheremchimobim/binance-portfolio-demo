import logging
import json
from binance.client import Client
from binance.enums import (
    ORDER_TYPE_MARKET,
    ORDER_TYPE_LIMIT,
    TIME_IN_FORCE_GTC,
    SIDE_BUY,
    SIDE_SELL
)

from binance.exceptions import BinanceAPIException, BinanceOrderException

# ============================================================
# CONFIGURATION SECTION
# ============================================================

API_KEY = "YOUR_TESTNET_API_KEY_HERE"
API_SECRET = "YOUR_TESTNET_SECRET_KEY_HERE"

# Example trading parameters
SYMBOL = "BTCUSDT"        # Futures symbol
RISK_PERCENT = 1.0        # Risk 1% of account balance per trade
STOP_LOSS_PCT = 0.01      # 1% stop loss below entry
TAKE_PROFIT_PCT = 0.02    # 2% take profit above entry
LEVERAGE = 10             # Leverage for position
TESTNET = True            # True = testnet, False = live


# ============================================================
# LOGGING SETUP
# ============================================================
logging.basicConfig(
    filename='trading_bot.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ============================================================
# BASIC BOT CLASS
# ============================================================
class FuturesBot:
    def __init__(self, api_key, api_secret, testnet=True):
        self.client = Client(api_key, api_secret)
        if testnet:
            self.client.FUTURES_URL = "https://testnet.binancefuture.com/fapi"
        logging.info(f"Initialized FuturesBot (Testnet Mode: {testnet})")

    # --------------------------------------------------------
    # ACCOUNT INFO
    # --------------------------------------------------------
    def get_balance(self):
        try:
            account = self.client.futures_account_balance()
            usdt_balance = next(item for item in account if item['asset'] == 'USDT')
            balance = float(usdt_balance['balance'])
            logging.info(f"Account balance: {balance} USDT")
            return balance
        except Exception as e:
            logging.exception("Error fetching account balance")
            return None

    # --------------------------------------------------------
    # SET LEVERAGE
    # --------------------------------------------------------
    def set_leverage(self, symbol, leverage):
        try:
            self.client.futures_change_leverage(symbol=symbol, leverage=leverage)
            logging.info(f"Leverage set to {leverage}x for {symbol}")
        except Exception:
            logging.exception("Error setting leverage")

    # --------------------------------------------------------
    # PLACE MARKET ORDER
    # --------------------------------------------------------
    def place_market_order(self, symbol, side, quantity):
        try:
            order = self.client.futures_create_order(
                symbol=symbol,
                side=side,
                type=ORDER_TYPE_MARKET,
                quantity=quantity
            )
            logging.info(f"Market order placed: {order}")
            return order
        except (BinanceAPIException, BinanceOrderException):
            logging.exception("Error placing market order")
            return None

    # --------------------------------------------------------
    # PLACE STOP-LOSS & TAKE-PROFIT
    # --------------------------------------------------------
    def set_risk_management(self, symbol, entry_side, stop_loss_price, take_profit_price):
        try:
            exit_side = SIDE_SELL if entry_side == SIDE_BUY else SIDE_BUY

            # Stop-Loss Order
            sl_order = self.client.futures_create_order(
                symbol=symbol,
                side=exit_side,
                type='STOP_MARKET',
                stopPrice=round(stop_loss_price, 2),
                closePosition=True,
                reduceOnly=True
            )

            # Take-Profit Order
            tp_order = self.client.futures_create_order(
                symbol=symbol,
                side=exit_side,
                type='STOP_MARKET',
                stopPrice=round(take_profit_price, 2),
                closePosition=True,
                reduceOnly=True
            )

            logging.info(f"Placed SL/TP Orders: SL={sl_order}, TP={tp_order}")
            return {"stop_loss": sl_order, "take_profit": tp_order}

        except (BinanceAPIException, BinanceOrderException):
            logging.exception("Error placing SL/TP orders")
            return None


# ============================================================
# HELPER FUNCTIONS
# ============================================================
def calculate_position_size(bot, symbol, risk_pct, stop_loss_pct, leverage):
    balance = bot.get_balance()
    if balance is None:
        raise ValueError("Failed to get account balance")

    risk_amount = balance * (risk_pct / 100)
    price_data = bot.client.futures_mark_price(symbol=symbol)
    current_price = float(price_data['markPrice'])

    # Risk per contract (approximation)
    stop_distance = current_price * stop_loss_pct
    qty = (risk_amount * leverage) / stop_distance

    return round(qty, 3), current_price


# ============================================================
# MAIN EXECUTION
# ============================================================
if __name__ == "__main__":
    bot = FuturesBot(API_KEY, API_SECRET, testnet=TESTNET)

    # 1️⃣ Set leverage
    bot.set_leverage(SYMBOL, LEVERAGE)

    # 2️⃣ Calculate quantity based on risk and price
    quantity, entry_price = calculate_position_size(bot, SYMBOL, RISK_PERCENT, STOP_LOSS_PCT, LEVERAGE)
    print(f"Calculated quantity: {quantity}, entry price: {entry_price}")

    # 3️⃣ Place Market Order (LONG EXAMPLE)
    entry_side = SIDE_BUY
    entry_order = bot.place_market_order(SYMBOL, entry_side, quantity)
    print(json.dumps(entry_order, indent=4))

    if entry_order:
        # 4️⃣ Compute Stop-Loss & Take-Profit levels
        stop_loss_price = entry_price * (1 - STOP_LOSS_PCT)
        take_profit_price = entry_price * (1 + TAKE_PROFIT_PCT)

        # 5️⃣ Place SL/TP
        risk_orders = bot.set_risk_management(SYMBOL, entry_side, stop_loss_price, take_profit_price)
        print(json.dumps(risk_orders, indent=4))

    print("\n✅ Trade setup complete. Check your Binance Testnet dashboard.")
