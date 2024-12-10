import csv
import os
from datetime import datetime, timedelta
from typing import Dict, Optional
from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.models import Coin, CurrentCoin

class Strategy(AutoTrader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_history: Dict[str, Dict[datetime, float]] = {}
        self.momentum_threshold = 3.0  # 3% price increase threshold
        self.timeframe_minutes = 15    # Monitor price changes over 15 minutes
        
        # Initialize CSV logging
        self._initialize_csv_log()
        
    def _initialize_csv_log(self):
        """Initialize the CSV log file with headers"""
        log_dir = 'trade_logs'
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, 'trade_operations.csv')
        
        # Check if file exists, if not create and write headers
        file_exists = os.path.isfile(log_file)
        
        with open(log_file, 'a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            if not file_exists:
                csv_writer.writerow([
                    'Timestamp', 
                    'Operation', 
                    'Coin', 
                    'Price', 
                    'Momentum', 
                    'Price Change %', 
                    'Trading Pair'
                ])
    
    def _log_trade_operation(self, operation: str, coin: Coin, current_price: float):
        """Log trade operation details to CSV"""
        log_dir = 'trade_logs'
        log_file = os.path.join(log_dir, 'trade_operations.csv')
        
        # Calculate momentum and price change
        price_history = self.price_history.get(coin.symbol, {})
        momentum = False
        price_change_pct = 0.0
        
        if price_history:
            oldest_price = min(price_history.values())
            price_change_pct = ((current_price - oldest_price) / oldest_price) * 100
            momentum = price_change_pct >= self.momentum_threshold
        
        with open(log_file, 'a', newline='') as csvfile:
            csv_writer = csv.writer(csvfile)
            csv_writer.writerow([
                datetime.now().isoformat(),
                operation,
                coin.symbol,
                current_price,
                momentum,
                price_change_pct,
                f"{coin.symbol}{self.config.BRIDGE}"
            ])
        
        self.logger.info(f"Trade operation logged: {operation} {coin.symbol}")

    def initialize(self):
        print("started-000000")
        super().initialize()
        # Initialize price history for all supported coins
        for coin in self.db.get_coins():
            self.price_history[coin.symbol] = {}
        
        # Get current coin from the database
        current_coin = self.db.get_current_coin()
        if current_coin is None:
            self.logger.info("No current coin found, setting initial coin...")
            # If no coin is set, look for a suitable initial coin
            for coin in self.db.get_coins():
                current_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)
                if current_price is not None:
                    self.logger.info(f"Setting initial coin to {coin.symbol}")
                    self.db.set_current_coin(coin)
                    break

    def scout(self):
        """
        Scout for potential momentum trades
        """
        try:
            current_coin = self.db.get_current_coin()
            
            print(
                f"{datetime.now()} - CONSOLE - INFO - Momentum strategy scouting. "
                f"Current coin: {current_coin + self.config.BRIDGE if current_coin else 'None'} ",
                end="\r",
            )

            # Update price history for all coins
            for coin in self.db.get_coins():
                current_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)
                if current_price is None:
                    continue
                    
                # Store current price with timestamp
                self.price_history[coin.symbol][datetime.now()] = current_price
                
                # Clean up old price history
                self._cleanup_old_prices(coin.symbol)
                
                # Check for momentum
                if self._check_momentum(coin.symbol, current_price):
                    if current_coin is None or coin.symbol != current_coin.symbol:
                        self.logger.info(f"Momentum detected for {coin.symbol}, attempting to buy")
                        if self._buy_coin(coin):
                            return

            # Check if we should sell current coin
            if current_coin is not None:
                current_price = self.manager.get_ticker_price(current_coin + self.config.BRIDGE)
                if current_price is not None and self._should_sell(current_coin.symbol, current_price):
                    self.logger.info(f"Selling {current_coin.symbol} based on momentum reversal")
                    if self._sell_coin(current_coin):
                        return
        except Exception as e:
            self.logger.error(f"Error while scouting: {str(e)}")

    def _cleanup_old_prices(self, symbol: str):
        """Remove price entries older than the monitoring timeframe"""
        cutoff_time = datetime.now() - timedelta(minutes=self.timeframe_minutes)
        self.price_history[symbol] = {
            timestamp: price 
            for timestamp, price in self.price_history[symbol].items()
            if timestamp > cutoff_time
        }

    def _check_momentum(self, symbol: str, current_price: float) -> bool:
        """Check if coin has momentum based on price history"""
        if not self.price_history[symbol]:
            return False
            
        oldest_price = min(self.price_history[symbol].values())
        price_change = ((current_price - oldest_price) / oldest_price) * 100
        
        return price_change >= self.momentum_threshold

    def _should_sell(self, symbol: str, current_price: float) -> bool:
        """Determine if we should sell based on scout_margin"""
        if not self.price_history[symbol]:
            return False
            
        buy_price = min(self.price_history[symbol].values())
        price_change = ((current_price - buy_price) / buy_price) * 100
        
        return price_change >= self.config.SCOUT_MARGIN

    def _buy_coin(self, coin: Coin) -> Optional[float]:
        """Execute buy order for given coin"""
        current_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)
        if self.manager.buy_alt(coin, self.config.BRIDGE) is not None:
            self.db.set_current_coin(coin)
            self.logger.info(f"Bought {coin.symbol}")
            
            # Log the buy operation
            self._log_trade_operation('BUY', coin, current_price)
            
            return True
        return None

    def _sell_coin(self, coin: Coin) -> Optional[float]:
        """Execute sell order for given coin"""
        current_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)
        if self.manager.sell_alt(coin, self.config.BRIDGE) is not None:
            # Clear the current coin by setting it to None through the database
            with self.db.db_session() as session:
                session.query(CurrentCoin).delete()
                session.commit()
            
            self.logger.info(f"Sold {coin.symbol}")
            self._log_trade_operation('SELL', coin, current_price)
            return True
        return None