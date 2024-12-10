from binance.client import *
import time
# from tqdm import tqdm
# Constants
API_KEY = 'YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT'
API_SECRET = 'Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq'
from .logger import Logger
logger = Logger()
POLL_INTERVAL = 2  # seconds
THRESHOLD = 0.005  # 1% price increase
NET_TARGET_PROFIT = 0.005  # 1% net profit after fees
BUY_AMOUNT_USDT = 7  # Amount to spend on each buy

# Initialize Binance client
client = Client(api_key=API_KEY, api_secret=API_SECRET)


def fetch_prices():
    """Fetches the latest prices for all Binance Futures coins."""
    try:
        prices = client.futures_symbol_ticker()
        return {item['symbol']: float(item['price']) for item in prices}
    except Exception as e:
        logger.error(f"🚫 Error fetching prices: {e}")
        return {}


def detect_positive_changes(previous_prices, current_prices):
    """Detects coins with positive price changes exceeding the threshold."""
    for symbol, current_price in current_prices.items():
        if symbol in previous_prices:
            previous_price = previous_prices[symbol]
            if previous_price > 0:
                change = (current_price - previous_price) / previous_price
                if change > THRESHOLD:
                    logger.info(f"📈 Significant change detected for {symbol}: {change:.2%} exceeds threshold {THRESHOLD:.2%}")
                    return symbol, current_price, change
    return None, None, None


def get_trading_fees(symbol):
    try:
        fees = client.get_trade_fee(symbol=symbol)
        if fees and len(fees) > 0:
            return float(fees[0]['makerCommission']), float(fees[0]['takerCommission'])
    except Exception as e:
        logger.error(f"💰 Error fetching trading fees for {symbol}: {e}")
    return 0.0, 0.0


def calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee):
    """
    Calculates the adjusted target price to achieve the net target profit after fees.
    Fees are applied on both buy and sell orders.
    """
    total_fee_percentage = maker_fee + taker_fee  # Assume worst case (taker fees both times)
    adjusted_profit_multiplier = (1 + NET_TARGET_PROFIT + total_fee_percentage)
    return buy_price * adjusted_profit_multiplier


def calculate_quantity(symbol, usdt_amount):
    """Calculate the quantity for an order based on USDT amount and symbol price."""
    try:
        # Fetch current price of the symbol
        price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
        
        # Get symbol-specific LOT_SIZE info
        exchange_info = client.futures_exchange_info()
        lot_size_filter = next(
            f for f in next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)['filters']
            if f['filterType'] == 'LOT_SIZE'
        )
        
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])
        
        # Calculate quantity based on the price and USDT amount
        quantity = usdt_amount / price
        quantity = max(min_qty, (quantity // step_size) * step_size)
        
        return quantity
    except Exception as e:
        print(f"Error calculating quantity: {e}")
        return None


def place_order(symbol, side, quantity):
    try:
        logger.info(f"📊 Placing {side} order - Quantity: {quantity}")
        order = client.create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity
        )
        logger.info(f"✅ {side} order placed: {order}")
        return order
    except Exception as e:
        logger.error(f"❌ Error placing {side} order: {e}")
        return None


def monitor_for_target(symbol, buy_price, target_price):
    logger.info(f"👀 Monitoring {symbol} for target profit...")
    logger.info(f"💵 Buy Price: {buy_price:.6f}")
    logger.info(f"🎯 Adjusted Target Price: {target_price:.6f}")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            if (target_price > buy_price and current_price >= target_price) or (target_price < buy_price and current_price <= target_price):
                logger.info(f"🎉 Target reached! Current Price: {current_price:.6f}")
                return current_price
        except Exception as e:
            logger.error(f"❌ Error fetching current price: {e}")
            break


def calculate_sell_quantity(symbol, buy_order):
    """Calculate the quantity to sell based on the executed quantity after the buy order, adjusted for LOT_SIZE."""
    try:
        # Extract the executed quantity from the buy order
        executed_qty = float(buy_order['executedQty'])
        
        # Extract the commission from the buy order (in terms of coin)
        commission_qty = float(buy_order['fills'][0]['commission'])
        
        # The actual quantity of coins after commission deduction
        actual_qty = executed_qty - commission_qty
        
        # Fetch symbol-specific LOT_SIZE info
        exchange_info = client.futures_exchange_info()
        lot_size_filter = next(
            f for f in next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)['filters']
            if f['filterType'] == 'LOT_SIZE'
        )
        
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])
        
        # Adjust the quantity to meet the LOT_SIZE filter
        adjusted_qty = max(min_qty, (actual_qty // step_size) * step_size)

        return adjusted_qty
    except Exception as e:
        print(f"Error calculating sell quantity: {e}")
        return None


def main():
    logger.info("🤖 Starting Bot Rand Monitor...")
    previous_prices = fetch_prices()
    logger.info("✅ Successfully fetched previous prices.")

    while True:
        time.sleep(POLL_INTERVAL)
        current_prices = fetch_prices()
        if not current_prices:
            continue

        symbol, price, change = detect_positive_changes(previous_prices, current_prices)
        if symbol:
            logger.info(f"🚀 Rapid change detected: {symbol}, Price: {price:.6f}, Change: {change:.2%}")

            quantity = calculate_quantity(symbol, BUY_AMOUNT_USDT)
            if quantity is None:
                logger.error(f"❌ Error calculating quantity for {symbol}. Skipping...")
                continue

            buy_order = place_order(symbol, 'BUY', quantity)
            sell_quantity = calculate_sell_quantity(symbol, buy_order)
            if buy_order:
                buy_price = price
                maker_fee, taker_fee = get_trading_fees(symbol)
                target_price = calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee)
                sell_price = monitor_for_target(symbol, buy_price, target_price)
                sell_order = place_order(symbol, 'SELL', sell_quantity)
                if sell_order:
                    logger.info(f"💰 Sold {symbol} at {sell_price:.6f}, Target profit achieved!")
                    previous_prices = fetch_prices()
        previous_prices = fetch_prices()




