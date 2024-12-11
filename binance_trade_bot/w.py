import time
import math
import urllib
import hmac
import hashlib
import requests
from typing import Dict, Optional, Tuple
from binance.client import Client
from binance.exceptions import BinanceAPIException

class Logger:
    @staticmethod
    def info(message: str) -> None:
        print(f"ℹ️ {message}")

    @staticmethod
    def error(message: str) -> None:
        print(f"❌ {message}")

class BinanceTradeConfiguration:
    def __init__(self, 
                 api_key: str, 
                 api_secret: str, 
                 poll_interval: int = 2,
                 threshold: float = 0.005,
                 net_target_profit: float = 0.005,
                 buy_amount_usdt: float = 5):
        self.API_KEY = api_key
        self.API_SECRET = api_secret
        self.POLL_INTERVAL = poll_interval
        self.THRESHOLD = threshold
        self.NET_TARGET_PROFIT = net_target_profit
        self.BUY_AMOUNT_USDT = buy_amount_usdt
        self.logger = Logger()

class BinanceClient:
    def __init__(self, config: BinanceTradeConfiguration):
        self.config = config
        self.client = Client(api_key=config.API_KEY, api_secret=config.API_SECRET)
        self.logger = config.logger

    def fetch_prices(self) -> Dict[str, float]:
        try:
            prices = self.client.futures_symbol_ticker()
            return {item['symbol']: float(item['price']) for item in prices}
        except Exception as e:
            self.logger.error(f"Error fetching prices: {e}")
            return {}

    def get_trading_fees(self, symbol: str) -> Tuple[float, float]:
        try:
            fees = self.client.get_trade_fee(symbol=symbol)
            if fees and len(fees) > 0:
                return float(fees[0]['makerCommission']), float(fees[0]['takerCommission'])
        except Exception as e:
            self.logger.error(f"Error fetching trading fees for {symbol}: {e}")
        return 0.0, 0.0

class TradeAnalyzer:
    def __init__(self, config: BinanceTradeConfiguration):
        self.config = config
        self.logger = config.logger

    def detect_positive_changes(self, 
                                previous_prices: Dict[str, float], 
                                current_prices: Dict[str, float]) -> Tuple[Optional[str], Optional[float], Optional[float]]:
        for symbol, current_price in current_prices.items():
            if symbol in previous_prices:
                previous_price = previous_prices[symbol]
                if previous_price > 0:
                    change = (current_price - previous_price) / previous_price
                    if change > self.config.THRESHOLD:
                        self.logger.info(f"Significant change detected for {symbol}: {change:.2%} exceeds threshold {self.config.THRESHOLD:.2%}")
                        return symbol, current_price, change
        return None, None, None

    def calculate_adjusted_target_profit(self, buy_price: float, maker_fee: float, taker_fee: float) -> float:
        total_fee_percentage = maker_fee + taker_fee 
        adjusted_profit_multiplier = (1 + self.config.NET_TARGET_PROFIT + total_fee_percentage)
        return buy_price * adjusted_profit_multiplier

class TradeExecutor:
    def __init__(self, binance_client: BinanceClient, config: BinanceTradeConfiguration):
        self.client = binance_client.client
        self.config = config
        self.logger = config.logger
        self.base_url = "https://api.binance.com"
        self.trade_analyzer = TradeAnalyzer(config)

    def _calculate_quantity_from_usdt(self, symbol: str, usdt_amount: float) -> Optional[float]:
            try:
                # Get symbol information to check minimum quantity and precision
                symbol_info = self.client.get_symbol_info(symbol)
                
                # Get current market price
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])

                # Calculate raw quantity
                raw_quantity = usdt_amount / current_price

                # Find the filters
                lot_size_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'LOT_SIZE'), None)
                min_notional_filter = next((f for f in symbol_info['filters'] if f['filterType'] == 'MIN_NOTIONAL'), None)

                if not lot_size_filter or not min_notional_filter:
                    self.logger.error(f"Could not find lot size or min notional filter for {symbol}")
                    return None

                min_qty = float(lot_size_filter['minQty'])
                max_qty = float(lot_size_filter['maxQty'])
                step_size = float(lot_size_filter['stepSize'])
                min_notional = float(min_notional_filter['minNotional'])

                # Round down quantity to step size
                quantity = math.floor(raw_quantity / step_size) * step_size

                # Ensure quantity meets minimum quantity requirement
                quantity = max(quantity, min_qty)

                # Ensure quantity is within max limit
                quantity = min(quantity, max_qty)

                # Additional check for minimum notional value
                while quantity * current_price < min_notional and quantity > min_qty:
                    quantity -= step_size

                # Final precision check
                quantity = round(quantity, 8)

                self.logger.info(f"Calculated Quantity: {quantity}")
                self.logger.info(f"Current Price: {current_price}")
                self.logger.info(f"Total Value: {quantity * current_price}")
                self.logger.info(f"Min Notional: {min_notional}")

                return quantity

            except Exception as e:
                self.logger.error(f"Error calculating quantity for {symbol}: {e}")
                return None

        def buy_usdt_amount(self, symbol: str, usdt_amount: float, target_profit_percentage: float = 0.005, stop_loss_percentage: float = 0.02):
            try:
                # Fetch current market price
                ticker = self.client.get_symbol_ticker(symbol=symbol)
                current_price = float(ticker['price'])

                # Get symbol information to check price precision
                symbol_info = self.client.get_symbol_info(symbol)
                
                # Find price filter to determine rounding precision
                price_filter = next(
                    (f for f in symbol_info['filters'] if f['filterType'] == 'PRICE_FILTER'), 
                    None
                )
                
                # Determine price rounding function
                if price_filter:
                    tick_size = float(price_filter['tickSize'])
                    def round_price(price):
                        return math.floor(price / tick_size) * tick_size
                else:
                    # Fallback to default rounding
                    def round_price(price):
                        return round(price, 8)

                # Calculate quantity to buy based on USDT amount and current price
                quantity = self._calculate_quantity_from_usdt(symbol, usdt_amount)

                if quantity is None or quantity <= 0:
                    self.logger.error(f"Could not calculate valid quantity for {symbol}")
                    return None

                # Place the market buy order
                self.logger.info(f"Placing BUY order for {symbol} - USDT Amount: {usdt_amount}")
                buy_order = self.client.create_order(
                    symbol=symbol,
                    side="BUY",
                    type="MARKET",
                    quantity=quantity
                )
                self.logger.info(f"Buy order placed successfully: {buy_order}")

                # Calculate buy price from the order
                buy_price = float(buy_order['fills'][0]['price'])
                actual_qty = float(buy_order['executedQty'])

                # Get trading fees
                fees = self.client.get_trade_fee(symbol=symbol)
                maker_fee = float(fees[0]['makerCommission'])
                taker_fee = float(fees[0]['takerCommission'])

                # Calculate target price considering fees
                total_fee_percentage = maker_fee + taker_fee
                total_target_percentage = target_profit_percentage + total_fee_percentage
                target_price = round_price(buy_price * (1 + total_target_percentage))

                # Calculate stop-loss price
                stop_price = round_price(buy_price * (1 - stop_loss_percentage))
                stop_limit_price = round_price(stop_price * 0.99)  # Slightly lower to ensure execution

                # Place an OCO sell order with actual executed quantity
                self.logger.info(f"Placing OCO SELL order for {symbol}")
                self.logger.info(f"  Buy Price: {buy_price}")
                self.logger.info(f"  Actual Quantity: {actual_qty}")
                self.logger.info(f"  Target Price: {target_price}")
                self.logger.info(f"  Stop Price: {stop_price}")
                self.logger.info(f"  Stop Limit Price: {stop_limit_price}")

                oco_order = self.client.create_oco_order(
                    symbol=symbol,
                    side="SELL",
                    quantity=actual_qty,
                    price=target_price,
                    stopPrice=stop_price,
                    stopLimitPrice=stop_limit_price,
                    stopLimitTimeInForce="GTC"
                )
                self.logger.info(f"OCO sell order placed successfully: {oco_order}")

                return {
                    "buy_order": buy_order, 
                    "oco_order": oco_order,
                    "buy_price": buy_price,
                    "target_price": target_price,
                    "stop_price": stop_price
                }

            except Exception as e:
                self.logger.error(f"Error placing orders for {symbol}: {e}")
                return None

class TradingBot:
    def __init__(self, config: BinanceTradeConfiguration):
        self.config = config
        self.logger = config.logger
        self.binance_client = BinanceClient(config)
        self.trade_analyzer = TradeAnalyzer(config)
        self.trade_executor = TradeExecutor(self.binance_client, config)

    def monitor_for_target(self, symbol: str, buy_price: float, target_price: float) -> Optional[float]:
        while True:
            time.sleep(self.config.POLL_INTERVAL)
            try:
                current_price = float(self.binance_client.client.futures_symbol_ticker(symbol=symbol)['price'])
                if (target_price > buy_price and current_price >= target_price) or \
                   (target_price < buy_price and current_price <= target_price):
                    self.logger.info(f"Target reached! Current Price: {current_price:.6f}")
                    return current_price
            except Exception as e:
                self.logger.error(f"Error fetching current price: {e}")
                break

    def monitor_order_success(self, order: Dict, timeout: int = 300) -> bool:
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                order_status = self.trade_executor.client.get_order(
                    symbol=order['symbol'], 
                    orderId=order['orderId']
                )
                
                if order_status['status'] in ['FILLED', 'PARTIALLY_FILLED']:
                    self.logger.info(f"Order {order['orderId']} successfully executed")
                    return True
                elif order_status['status'] in ['CANCELED', 'REJECTED']:
                    self.logger.error(f"Order {order['orderId']} was {order_status['status']}")
                    return False
                
                time.sleep(self.config.POLL_INTERVAL)
            except Exception as e:
                self.logger.error(f"Error checking order status: {e}")
                break
        
        self.logger.error(f"Order {order['orderId']} did not complete within {timeout} seconds")
        return False

    def run(self):
        previous_prices = self.binance_client.fetch_prices()

        while True:
            time.sleep(self.config.POLL_INTERVAL)
            current_prices = self.binance_client.fetch_prices()
            if not current_prices:
                continue

            symbol, price, change = self.trade_analyzer.detect_positive_changes(previous_prices, current_prices)
            if symbol:
                self.logger.info(f"Rapid change detected: {symbol}, Price: {price:.6f}, Change: {change:.2%}")

                # Place the OCO order (both buy and sell in one method)
                oco_orders = self.trade_executor.buy_usdt_amount(
                    symbol, 
                    self.config.BUY_AMOUNT_USDT
                )

                if oco_orders:
                    # Monitor buy order success
                    if self.monitor_order_success(oco_orders['buy_order']):
                        self.logger.info(f"Buy order for {symbol} executed successfully")
                        
                        # Wait and monitor sell order (take-profit or stop-loss)
                        sell_order_success = self.monitor_order_success(oco_orders['oco_order'])
                        
                        if sell_order_success:
                            self.logger.info(f"Completed trade for {symbol} successfully!")
                        else:
                            self.logger.warning(f"Trade for {symbol} did not complete as expected")
                
                previous_prices = current_prices  # Update previous prices for the next iteration

# Example usage
def main():
    config = BinanceTradeConfiguration(
     api_key='YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT', 
        api_secret='Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq',
        poll_interval=2,
        threshold=0.005,
        net_target_profit=0.005,
        buy_amount_usdt=7
    )
    trading_bot = TradingBot(config)
    trading_bot.run()

if __name__ == "__main__":
    main()