from binance.client import *
import time
# from tqdm import tqdm
# Constants
API_KEY = 'YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT'
API_SECRET = 'Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq'

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
        print(f"Error fetching prices: {e}")
        return {}


def detect_positive_changes(previous_prices, current_prices):
    """
    Detects coins with positive price changes exceeding the threshold.
    Logs details about the price changes for all symbols.
    """
    # print("Detecting positive changes...")
    for symbol, current_price in current_prices.items():
        if symbol in previous_prices:
            previous_price = previous_prices[symbol]
            if previous_price > 0:  # Avoid division by zero
                change = (current_price - previous_price) / previous_price
                # if change > 0:
                #     print(f"Symbol: {symbol}, Previous Price: {previous_price:.6f}, "
                #           f"Current Price: {current_price:.6f}, Change: {change:.2%}")

                if change > THRESHOLD:
                    print(f"Significant change detected for {symbol}: {change:.2%} exceeds threshold {THRESHOLD:.2%}")
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
    """Places a market order with the given quantity."""
    try:
        # Place order with the calculated quantity
        print("quantity", quantity, "side", side)
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
    # progress_bar = tqdm(total=100, desc="Progress to target", unit="%")
    # progress_bar.n = 0  # Start at 0%
    # progress_bar.last_print_t = time.time()  # Initialize time for refresh

    while True:
        time.sleep(POLL_INTERVAL)
        try:
            # Fetch the current price of the symbol
            current_price = float(client.futures_symbol_ticker(symbol=symbol)['price'])
            
            # Calculate the progress towards the target price
            # if target_price > buy_price:
            #     progress = ((current_price - buy_price) / (target_price - buy_price)) * 100
            # else:
            #     progress = ((buy_price - current_price) / (buy_price - target_price)) * 100

            # Ensure the progress is clamped between 0% and 100%
            # progress = max(0, min(progress, 100))

            # Update tqdm progress bar
            # progress_bar.n = int(progress)
            # progress_bar.last_print_t = time.time()  # Avoid tqdm rate warnings
            # progress_bar.refresh()

            # Check if the target price has been reached
            if (target_price > buy_price and current_price >= target_price) or (target_price < buy_price and current_price <= target_price):
                # progress_bar.close()
                print(f"Target reached! Current Price: {current_price:.6f}")
                return current_price

        except Exception as e:
            print(f"Error fetching current price: {e}")
            # progress_bar.close()
            break  # Stop the loop in case of error
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
    print("Starting Binance Futures Price Monitor...")
    previous_prices = fetch_prices()
    print("Successfully fetched previous prices.")

    while True:
        time.sleep(POLL_INTERVAL)
        current_prices = fetch_prices()
        if not current_prices:
            continue

        # Detect the first coin with a rapid positive change
        symbol, price, change = detect_positive_changes(previous_prices, current_prices)
        if symbol:
            print(f"Rapid change detected: {symbol}, Price: {price:.6f}, Change: {change:.2%}")

            # Calculate the quantity to buy based on the USDT amount
            quantity = calculate_quantity(symbol, BUY_AMOUNT_USDT)
            
            if quantity is None:
                print(f"Error calculating quantity for {symbol}. Skipping...")
                continue  # Skip this iteration if quantity calculation fails

            # Place a buy order for the calculated quantity
            buy_order = place_order(symbol, 'BUY', quantity)
            sell_quantity = calculate_sell_quantity(symbol, buy_order)
            if buy_order:
                buy_price = price  # Use the detected price as the buy price

                # Calculate the adjusted target price (considering fees)
                maker_fee, taker_fee = get_trading_fees(symbol)  # Assuming you have this function to fetch fees
                target_price = calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee)

                # Monitor price for the adjusted target
                sell_price = monitor_for_target(symbol, buy_price, target_price)

                # Place a sell order with the same quantity
                sell_order = place_order(symbol, 'SELL', sell_quantity)
                if sell_order:
                    print(f"Sold {symbol} at {sell_price:.6f}, Target profit achieved!")
                    previous_prices = fetch_prices()
                    # break  
        previous_prices = fetch_prices()




