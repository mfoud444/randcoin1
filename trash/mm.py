from binance.client import Client
import time

import math
from typing import Dict, Optional, Tuple
# Reuse the get_fastest_movers() function here
from concurrent.futures import ThreadPoolExecutor, as_completed


TRADE_AMOUNT_USDT = 5.6  # Amount to trade in USDT
PROFIT_TARGET = 0.01  # 5% profit target
TRADING_FEE = 0.001  # 0.1% per trade
MONITOR_TIME=10
# Set up your Binance API keys
API_KEY = 'YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT'
API_SECRET = 'Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq'

client = Client(API_KEY, API_SECRET)

def monitor_sell_order(symbol, order_id):
    """Monitor the status of the sell order and reinitiate trading if filled."""
    try:
        while True:
            # Fetch the order status
            order_status = client.get_order(symbol=symbol, orderId=order_id)
            # print(f"Monitoring sell order {order_id}: Status {order_status['status']}")
            
            # Check if the order is filled
            if order_status['status'] == 'FILLED':
                print(f"Sell order {order_id} for {symbol} is filled.")
                print(f"Monitoring sell order {order_id}: Status {order_status['status']}")
                
                break

            # Wait before checking again
            time.sleep(5)
    except Exception as e:
        print(f"Error monitoring sell order: {e}")


def get_lot_size_constraints(symbol):
    """Retrieve LOT_SIZE constraints for the symbol."""
    try:
        symbol_info = client.get_symbol_info(symbol)
        for filter_ in symbol_info['filters']:
            if filter_['filterType'] == 'LOT_SIZE':
                return float(filter_['minQty']), float(filter_['maxQty']), float(filter_['stepSize'])
    except Exception as e:
        print(f"Error fetching LOT_SIZE for {symbol}: {e}")
    return None, None, None

def adjust_quantity(quantity, step_size):
    """Adjust the quantity to comply with the LOT_SIZE step size."""
    return round(quantity // step_size * step_size, int(-1 * round(math.log10(step_size))))

def get_price_filter_constraints(symbol):
    """Retrieve PRICE_FILTER constraints for the symbol."""
    try:
        symbol_info = client.get_symbol_info(symbol)
        for filter_ in symbol_info['filters']:
            if filter_['filterType'] == 'PRICE_FILTER':
                return float(filter_['minPrice']), float(filter_['maxPrice']), float(filter_['tickSize'])
    except Exception as e:
        print(f"Error fetching PRICE_FILTER for {symbol}: {e}")
    return None, None, None

def adjust_price(price, tick_size):
    """Adjust the price to comply with the PRICE_FILTER tick size."""
    return round(price // tick_size * tick_size, int(-1 * round(math.log10(tick_size))))

def trade_fastest_currency(symbol):
    print(f"Trading the fastest currency: {symbol}")
    try:
        ticker = client.get_ticker(symbol=symbol)
        current_price = float(ticker['lastPrice'])
        minQty, maxQty, stepSize = get_lot_size_constraints(symbol)
        if minQty is None:
            print(f"Could not retrieve LOT_SIZE for {symbol}. Skipping trade.")
            return
        raw_quantity = TRADE_AMOUNT_USDT / current_price
        adjusted_quantity = adjust_quantity(raw_quantity, stepSize)
        if adjusted_quantity < minQty or adjusted_quantity > maxQty:
            print(f"Adjusted quantity {adjusted_quantity} is out of LOT_SIZE range for {symbol}. Skipping trade.")
            return
        print(f"Placing market buy order for {adjusted_quantity} {symbol}...")
        buy_order = client.order_market_buy(symbol=symbol, quantity=adjusted_quantity)
        print(f"Buy order placed: {buy_order}")
        executed_buy_price = sum(float(fill['price']) * float(fill['qty']) for fill in buy_order['fills']) / sum(float(fill['qty']) for fill in buy_order['fills'])
        print(f"Executed buy price: {executed_buy_price:.6f} USDT")

        # Step 3: Calculate target sell price
        target_price = executed_buy_price * (1 + PROFIT_TARGET + 2 * TRADING_FEE)

        # Get PRICE_FILTER constraints
        minPrice, maxPrice, tickSize = get_price_filter_constraints(symbol)
        if minPrice is None:
            print(f"Could not retrieve PRICE_FILTER for {symbol}. Skipping trade.")
            return

        # Adjust the target price to comply with PRICE_FILTER
        adjusted_target_price = adjust_price(target_price, tickSize)
        print(f"Target sell price (including fees, adjusted): {adjusted_target_price:.6f} USDT")

        # Ensure the adjusted price is within PRICE_FILTER limits
        if adjusted_target_price < minPrice or adjusted_target_price > maxPrice:
            print(f"Adjusted target price {adjusted_target_price} is out of PRICE_FILTER range for {symbol}. Skipping trade.")
            return

        # Step 4: Place a limit sell order
        print(f"Placing limit sell order for {adjusted_quantity} {symbol} at {adjusted_target_price}...")
        sell_order = client.order_limit_sell(symbol=symbol, quantity=adjusted_quantity, price=f"{adjusted_target_price:.6f}")
        print(f"Sell order placed: {sell_order}")

        # Monitor the sell order
        monitor_sell_order(symbol, sell_order['orderId'])

    except Exception as e:
        print(f"Error during trading: {e}")


def detect_positive_changes(
                            previous_prices, 
                            current_prices):
    for symbol, current_price in current_prices.items():
        if symbol in previous_prices:
            previous_price = previous_prices[symbol]
            if previous_price > 0:
                change = ((current_price - previous_price) / previous_price) * 100
                print(f"Significant change detected for {symbol}: {change} exceeds threshold {current_price} - {previous_price}")
                if change > 0.5:
                    print(f"Significant change detected for {symbol}: {change} exceeds threshold {current_price} - {previous_price} = {current_price-previous_price} ")
                    return symbol, current_price, change
    return None, None, None

def fetch_prices() -> Dict[str, float]:
    try:
        prices = client.futures_symbol_ticker()
        return {item['symbol']: float(item['price']) for item in prices}
    except Exception as e:
        print(f"Error fetching prices: {e}")
        return {}


def run():
    previous_prices = fetch_prices()

    while True:
        try:
            time.sleep(2)
            current_prices = fetch_prices()

            if not current_prices:
                continue

            symbol, price, change = detect_positive_changes(previous_prices, current_prices)
            if change:  # If a symbol is found with positive change
                trade_fastest_currency(symbol)
                # return [{'symbol': symbol, 'change': change}]
            previous_prices = current_prices
        except Exception as e:
            
            print(f"An error occurred in the trading loop: {e}")
            break
            

def fetch_mover_data(symbol):
    """Fetch the price change data for a single symbol."""
    try:
        candles = client.get_klines(symbol=symbol, interval=Client.KLINE_INTERVAL_1MINUTE, limit=10)
        start_price = float(candles[0][1])
        ticker = client.get_ticker(symbol=symbol)
        last_price = float(ticker['lastPrice'])
        percent_change = ((last_price - start_price) / start_price) * 100
        print(f"symbloy:{symbol}percent change:{percent_change}")
        if percent_change >= 1:
            return {'symbol': symbol, 'change': percent_change}
    except Exception as e:
        print(f"Error fetching data for {symbol}: {e}")
    return None

def get_fastest_movers():
    tickers = client.get_ticker()
    usdt_symbols = [ticker['symbol'] for ticker in tickers if ticker['symbol'].endswith('USDT')]

    movers = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        # Create futures for each symbol
        futures = {executor.submit(fetch_mover_data, symbol): symbol for symbol in usdt_symbols}

        for future in as_completed(futures):
            result = future.result()
            if result:
                movers.append(result)

    movers.sort(key=lambda x: x['change'], reverse=True)
    print(movers)
    return movers

def main():
    run()
    # trade_fastest_currency()
    # while True:
    #     try:
    #         # Execute the trading function
    #         trade_fastest_currency()
    #     except Exception as e:
    #         print(f"An error occurred in the trading loop: {e}")
# Execute the trading function
if __name__ == "__main__":
    main()

