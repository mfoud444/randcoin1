from datetime import datetime, timedelta
from typing import Dict, Optional
from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.models import Coin

class Strategy(AutoTrader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.price_history: Dict[str, Dict[datetime, float]] = {}
        self.momentum_threshold = 2.0
        self.timeframe_minutes = 15 
        
    def initialize(self):
        super().initialize()
        self.initialize_current_coin()
        # Initialize price history for all supported coins
        for coin in self.db.get_coins():
            self.price_history[coin.symbol] = {}

    def scout(self):
        """
        Scout for potential momentum trades
        """
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
                    self._buy_coin(coin)
                    return

        # Check if we should sell current coin
        if current_coin is not None:
            current_price = self.manager.get_ticker_price(current_coin + self.config.BRIDGE)
            if current_price is not None:
                if self._should_sell(current_coin.symbol, current_price):
                    self.logger.info(f"Selling {current_coin.symbol} based on momentum reversal")
                    self._sell_coin(current_coin)

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
        """Determine if we should sell based on momentum reversal"""
        if not self.price_history[symbol]:
            return False
            
        recent_high = max(self.price_history[symbol].values())
        price_drop = ((recent_high - current_price) / recent_high) * 100
        
        return price_drop >= (self.momentum_threshold / 2)  # Sell if we lose half of our momentum

    def _buy_coin(self, coin: Coin) -> Optional[float]:
        """Execute buy order for given coin"""
        if self.manager.buy_alt(coin, self.config.BRIDGE) is not None:
            self.db.set_current_coin(coin)
            return True
        return None

    def _sell_coin(self, coin: Coin) -> Optional[float]:
        """Execute sell order for given coin"""
        if self.manager.sell_alt(coin, self.config.BRIDGE) is not None:
            self.db.set_current_coin(None)
            return True
        return None