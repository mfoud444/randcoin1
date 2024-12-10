import time
from binance.client import Client
from binance.exceptions import BinanceAPIException
from typing import Dict, Optional, Tuple
import requests
import requests
import hmac
import hashlib
from .logger import Logger
import urllib
# class Logger:
#     @staticmethod
#     def info(message: str) -> None:
#         print(f"ℹ️ {message}")

#     @staticmethod
#     def error(message: str) -> None:
#         print(f"❌ {message}")

class BinanceTradeConfiguration:
    def __init__(self, 
                 api_key: str, 
                 api_secret: str, 
                 poll_interval: int = 2,
                 threshold: float = 0.005,
                 net_target_profit: float = 0.003,
                 buy_amount_usdt: float = 7):
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
    def calculate_quantity(self, symbol: str, usdt_amount: float) -> Optional[float]:
        try:
            price = float(self.client.futures_symbol_ticker(symbol=symbol)['price'])
            
            exchange_info = self.client.futures_exchange_info()
            lot_size_filter = next(
                f for f in next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)['filters']
                if f['filterType'] == 'LOT_SIZE'
            )
            
            min_qty = float(lot_size_filter['minQty'])
            step_size = float(lot_size_filter['stepSize'])
            
            quantity = usdt_amount / price
            quantity = max(min_qty, (quantity // step_size) * step_size)
            
            return quantity
        except Exception as e:
            self.logger.error(f"Error calculating quantity: {e}")
            return None

    def calculate_sell_quantity(self, symbol, buy_order):
        try:
            executed_qty = float(buy_order['executedQty'])
            commission_qty = float(buy_order['fills'][0]['commission'])
            actual_qty = executed_qty - commission_qty
            exchange_info = self.client.futures_exchange_info()
            lot_size_filter = next(
                f for f in next(s for s in exchange_info['symbols'] if s['symbol'] == symbol)['filters']
                if f['filterType'] == 'LOT_SIZE'
            )
            
            min_qty = float(lot_size_filter['minQty'])
            step_size = float(lot_size_filter['stepSize'])
            adjusted_qty = max(min_qty, (actual_qty // step_size) * step_size)
            return adjusted_qty
        except Exception as e:
            print(f"Error calculating sell quantity: {e}")
            return None

    def place_order(self, symbol: str, side: str, quantity: float):
        try:
            self.logger.info(f"Placing {side} order - Quantity: {quantity}")
            order = self.client.create_order(
                symbol=symbol,
                side=side,
                type='MARKET',
                quantity=quantity
            )
            return order
        except Exception as e:
            self.logger.error(f"Error placing {side} order: {e}")
            return None
    def place_order_sell(self, symbol: str, side: str):
        try:
            # Fetch available free balance for the asset
            free = float(self.client.get_asset_balance(asset=symbol[:-4])['free'])

            # Fetch LOT_SIZE filter for the symbol
            info = self.client.get_symbol_info(symbol)
            lot_size_filter = next(f for f in info['filters'] if f['filterType'] == 'LOT_SIZE')
            min_qty = float(lot_size_filter['minQty'])
            max_qty = float(lot_size_filter['maxQty'])
            step_size = float(lot_size_filter['stepSize'])

            while free >= min_qty:
                # Adjust quantity to match step size
                quantity = min(max_qty, free)
                quantity = quantity - (quantity % step_size)  # Align with step size

                if quantity < min_qty:
                    self.logger.warning(f"Adjusted quantity {quantity} is below minQty for {symbol}. Ending sell attempts.")
                    break

                # Place the sell order
                self.logger.info(f"Placing {side} order for {symbol} - Quantity: {quantity}")
                order = self.client.order_market_sell(
                    symbol=symbol,
                    quantity=quantity
                )
                self.logger.info(f"Sell order successful: {order}")

                # Update the free balance after the sell
                free = float(self.client.get_asset_balance(asset=symbol[:-4])['free'])
            
            self.logger.info(f"Finished selling all available {symbol}. Remaining balance: {free}")
            return True

        except Exception as e:
            self.logger.error(f"Error placing {side} order for {symbol}: {e}")
            return None

    def _generate_signature(self, query_string: str, secret_key: str) -> str:

        return hmac.new(secret_key.encode('utf-8'), query_string.encode('utf-8'), hashlib.sha256).hexdigest()

    def validate_conversion_assets(self, from_asset: str, to_asset: str) -> bool:
        """
        Validate if the assets are supported for conversion
        Add more sophisticated validation if needed
        """
        # List of known convertible assets
        convertible_assets = ['USDT', 'BTC', 'ETH', 'BNB']
        return from_asset in convertible_assets and to_asset in convertible_assets

    def convert_crypto(self, from_asset: str, to_asset: str, from_amount: float) -> Dict:
        try:
            if from_amount <= 0:
                self.logger.error(f"Invalid conversion amount: {from_amount}")
                return {"error": "Invalid conversion amount"}

            session = requests.Session()
            timestamp = int(time.time() * 1000)
            
            quote_params = {
                "fromAsset": from_asset,
                "toAsset": to_asset,
                "fromAmount": f"{from_amount:.2f}",  # Ensure 2 decimal precision
                "timestamp": timestamp
            }

            query_string = "&".join([f"{key}={value}" for key, value in sorted(quote_params.items())])
            signature = self._generate_signature(query_string, self.config.API_SECRET)
            
            headers = {"X-MBX-APIKEY": self.config.API_KEY}
            quote_params["signature"] = signature

            quote_url = f"{self.base_url}/sapi/v1/convert/getQuote"
            
            self.logger.info(f"Requesting quote: {quote_params}")
            
            quote_response = session.post(quote_url, params=quote_params, headers=headers)
            
            # Log full response for debugging
            self.logger.info(f"Quote response status: {quote_response.status_code}")
            self.logger.info(f"Quote response text: {quote_response.text}")
            
            quote_response.raise_for_status()
            quote_data = quote_response.json()
            
            quote_id = quote_data.get("quoteId")
            if not quote_id:
                self.logger.error("No quote ID found in response")
                return {"error": "Quote ID not found", "response": quote_data}

            # Accept quote process
            accept_params = {
                "quoteId": quote_id,
                "timestamp": int(time.time() * 1000)
            }

            accept_query_string = "&".join([f"{key}={value}" for key, value in sorted(accept_params.items())])
            accept_signature = self._generate_signature(accept_query_string, self.config.API_SECRET)
            
            accept_params["signature"] = accept_signature

            accept_url = f"{self.base_url}/sapi/v1/convert/acceptQuote"
            
            accept_response = session.post(accept_url, params=accept_params, headers=headers)
            
            # Log full accept response for debugging
            self.logger.info(f"Accept response status: {accept_response.status_code}")
            self.logger.info(f"Accept response text: {accept_response.text}")
            
            accept_response.raise_for_status()
            conversion_data = accept_response.json()

            self.logger.info(f"Conversion completed: {conversion_data}")
            return conversion_data

        except requests.exceptions.HTTPError as http_err:
            self.logger.error(f"HTTP error during conversion: {http_err}")
            self.logger.error(f"Response text: {http_err.response.text}")
            return {"error": "HTTP Error", "details": str(http_err)}
        except requests.exceptions.RequestException as req_err:
            self.logger.error(f"Request error during conversion: {req_err}")
            return {"error": "Request Error", "details": str(req_err)}
        except Exception as e:
            self.logger.error(f"Unexpected error during conversion: {e}")
            return {"error": "Unexpected Error", "details": str(e)}


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

    def run(self):
        # sell_order = self.trade_executor.place_order_sell("MOVEUSDT", 'SELL')
        
        previous_prices = self.binance_client.fetch_prices()

        while True:
            time.sleep(self.config.POLL_INTERVAL)
            current_prices = self.binance_client.fetch_prices()
            if not current_prices:
                continue

            symbol, price, change = self.trade_analyzer.detect_positive_changes(previous_prices, current_prices)
            if symbol:
                self.logger.info(f"Rapid change detected: {symbol}, Price: {price:.6f}, Change: {change:.2%}")

                quantity = self.trade_executor.calculate_quantity(symbol, self.config.BUY_AMOUNT_USDT)
                
                if quantity is None:
                    self.logger.info(f"Error calculating quantity for {symbol}. Skipping...")
                    continue

                buy_order = self.trade_executor.place_order(symbol, 'BUY', quantity) #self.trade_executor.convert_crypto(from_asset="USDT", to_asset=symbol[:-4], from_amount=100)
                sell_quantity = self.trade_executor.calculate_sell_quantity(symbol, buy_order)
                if buy_order:
                    buy_price = price
                    maker_fee, taker_fee = self.binance_client.get_trading_fees(symbol)
                    target_price = self.trade_analyzer.calculate_adjusted_target_profit(buy_price, maker_fee, taker_fee)

                    trade_info = (
                        f"BUY Order Details:\n"
                        f"    Symbol: {buy_order['symbol']}\n"
                        f"    Price: {float(buy_order['fills'][0]['price']):.8f}\n"
                        f"    Quantity: {buy_order['executedQty']}\n"
                        f"    Total Value: {float(buy_order['cummulativeQuoteQty']):.8f} USDT\n"
                        f"    Commission: {buy_order['fills'][0]['commission']} {buy_order['fills'][0]['commissionAsset']}\n"
                        f"    Status: {buy_order['status']}\n"
                        f"Trade Monitor:\n"
                        f"    Symbol: {symbol}\n"
                        f"    Buy Price: {buy_price:.8f}\n"
                        f"    Target Price: {target_price:.8f}\n"
                        f"    Expected Profit: {((target_price - buy_price) / buy_price * 100):.2f}%"
                    )
                    self.logger.info(trade_info)

                    sell_price = self.monitor_for_target(symbol, buy_price, target_price)
                    sell_order = self.trade_executor.place_order_sell(symbol, 'SELL')#self.trade_executor.convert_crypto(from_asset=symbol[:-4], to_asset="USDT", from_amount=100)
                    if sell_order:
                        self.logger.info(f"Sold {symbol} at {sell_price:.6f}, Target profit achieved!")
                        previous_prices = self.binance_client.fetch_prices()
            
            previous_prices = self.binance_client.fetch_prices()

def main():
    # You would pass actual API credentials here
    config = BinanceTradeConfiguration(
        api_key='YpTu6946fpANB5b0vUHhgZOCmoDUt6czUH0PJpziNCUllbF19AzCwywtixw3QkGT', 
        api_secret='Qr8AhyXTKrO2t85lL2eIjiAOmOnRWoWKDFJsgogdUCdXGTkCsKJvec0e3X1noneq'
    )
    bot = TradingBot(config)
    bot.run()

if __name__ == "__main__":
    main()