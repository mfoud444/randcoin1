from binance.client import *
import time
from tqdm import tqdm
# Constants
API_KEY = 'YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT'
API_SECRET = 'Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq'

POLL_INTERVAL = 2  # seconds
THRESHOLD = 0.01  # 1% price increase
NET_TARGET_PROFIT = 0.01  # 1% net profit after fees
BUY_AMOUNT_USDT = 7  # Amount to spend on each buy

# Initialize Binance client
client = Client(api_key=API_KEY, api_secret=API_SECRET)


def fetch_prices():
    """Fetches the latest prices for all Binance Futures coins."""
    try:
        prices = client.futures_symbol_ticker()
        return {item['symbol']: float(item['price']) for item in prices}
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return {}


def detect_positive_changes(previous_prices, current_prices):
    """Detects coins with positive price changes exceeding the threshold."""
    for symbol, current_price in current_prices.items():
        if symbol in previous_prices:
            previous_price = previous_prices[symbol]
            if previous_price > 0:  # Avoid division by zero
                change = (current_price - previous_price) / previous_price
                if change > THRESHOLD:
                    return symbol, current_price, change
    return None, None, None

def get_trading_fees(symbol):
    """Fetches the maker and taker fees for the given symbol."""
    try:
        fees = client.get_trade_fee(symbol=symbol)
        if fees and len(fees) > 0:
            return float(fees[0]['makerCommission']), float(fees[0]['takerCommission'])
    except Exception as e:
        print(f"Error fetching trading fees for {symbol}: {e}")
    return 0.0, 0.0


def calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee):
    """
    Calculates the adjusted target price to achieve the net target profit after fees.
    Fees are applied on both buy and sell orders.
    """
    total_fee_percentage = maker_fee + taker_fee  # Assume worst case (taker fees both times)
    adjusted_profit_multiplier = (1 + NET_TARGET_PROFIT + total_fee_percentage)
    return buy_price * adjusted_profit_multiplier


def place_order(symbol, side, usdt_amount):
    """Places a market order with dynamic quantity based on USDT amount."""
    try:
        # Fetch current price
        price = float(client.futures_symbol_ticker(symbol=symbol)['price'])

        # Get symbol-specific LOT_SIZE info
        exchange_info = client.futures_exchange_info()
        lot_size_filter = next(
            f for f in next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)['filters']
            if f['filterType'] == 'LOT_SIZE'
        )
        min_qty = float(lot_size_filter['minQty'])
        step_size = float(lot_size_filter['stepSize'])

        # Calculate quantity respecting LOT_SIZE
        quantity = usdt_amount / price
        quantity = max(min_qty, (quantity // step_size) * step_size)

        # Place order
        order = client.create_order(
            symbol=symbol,
            side=side,
            type='MARKET',
            quantity=quantity
        )
        print(f"{side} order placed: {order}")
        return order
    except Exception as e:
        print(f"Error placing {side} order: {e}")
        return None


def monitor_for_target(symbol, buy_price, target_price):
    """Monitors the price to sell when the adjusted target profit is reached."""
    print(f"Monitoring {symbol} for target profit...")
    print(f"Buy Price: {buy_price:.6f}")
    print(f"Adjusted Target Price: {target_price:.6f}")

    # Initialize tqdm progress bar
    progress_bar = tqdm(total=100, desc="Progress to target", unit="%")

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            progress = ((current_price - buy_price) / (target_price - buy_price)) * 100
            progress = max(0, min(progress, 100))  # Clamp progress between 0% and 100%

            # Update tqdm bar
            progress_bar.n = int(progress)
            progress_bar.last_print_t = time.time()  # Avoid tqdm rate warnings
            progress_bar.refresh()

            if current_price >= target_price:
                progress_bar.close()
                print(f"Target reached! Current Price: {current_price:.6f}")
                return current_price
        except Exception as e:
            print(f"Error fetching current price: {e}")
            progress_bar.close()
            break


def main():
    print("Starting Binance Futures Price Monitor...")
    previous_prices = fetch_prices()
    print("Successful fetch of previous prices.")

    while True:
        time.sleep(POLL_INTERVAL)
        current_prices = fetch_prices()
        if not current_prices:
            continue

        # Detect the first coin with a rapid positive change
        symbol, price, change = detect_positive_changes(previous_prices, current_prices)
        if symbol:
            print(f"Rapid change detected: {symbol}, Price: {price:.6f}, Change: {change:.2%}")

            # Fetch trading fees
            maker_fee, taker_fee = get_trading_fees(symbol)

            # Place a buy order for $5 USDT worth
            buy_order = place_order(symbol, 'BUY', BUY_AMOUNT_USDT)
            if buy_order:
                buy_price = price  # Use the detected price as the buy price

                # Calculate the adjusted target price
                target_price = calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee)

                # Monitor price for the adjusted target
                sell_price = monitor_for_target(symbol, buy_price, target_price)

                # Place a sell order
                sell_order = place_order(symbol, 'SELL', BUY_AMOUNT_USDT)
                if sell_order:
                    print(f"Sold {symbol} at {sell_price:.6f}, Target profit achieved!")
                    break  # Exit after successful trade

        previous_prices = current_prices


if __name__ == "__main__":
    main()
