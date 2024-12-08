from datetime import datetime
import random
import sys
import csv
from typing import Dict, Optional

from binance_trade_bot.auto_trader import AutoTrader
from binance_trade_bot.models import Coin, Pair


class Strategy(AutoTrader):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.previous_prices: Dict[str, float] = {}
        self.min_price_change_percentage = 0.5  # Minimum price change to trigger trade (0.5%)
        self.trade_history_file = "trade_history.csv"
        # Enhanced CSV headers with more detailed information
        with open(self.trade_history_file, 'a', newline='') as f:
            writer = csv.writer(f)
            if f.tell() == 0:  # Check if file is empty
                writer.writerow([
                    'Timestamp',
                    'Operation',
                    'Coin',
                    'Entry Price',
                    'Exit Price',
                    'Amount',
                    'Total Value',
                    'Profit/Loss Amount',
                    'Profit/Loss Percentage',
                    'Trading Fee',
                    'Net Profit/Loss'
                ])

    def initialize(self):
        super().initialize()
        self.initialize_current_coin()

    def scout(self):
        """
        Scalping strategy:
        - Monitor price changes in short intervals
        - Buy when price drops by threshold percentage
        - Sell when price increases by threshold percentage
        - Use smaller trade amounts for more frequent trades
        """
        current_coin = self.db.get_current_coin()
        
        # Display scouting activity
        print(
            f"{datetime.now()} - CONSOLE - INFO - Scalping strategy scouting. "
            f"Current coin: {current_coin + self.config.BRIDGE} ",
            end="\r",
        )

        if current_coin is None:
            self.bridge_scout()
            return

        current_coin_price = self.manager.get_ticker_price(current_coin + self.config.BRIDGE)
        
        if current_coin_price is None:
            self.logger.info(f"Skipping scouting... current coin {current_coin + self.config.BRIDGE} not found")
            return

        # Store previous price if not already tracked
        if current_coin.symbol not in self.previous_prices:
            self.previous_prices[current_coin.symbol] = current_coin_price
            return

        previous_price = self.previous_prices[current_coin.symbol]
        price_change = ((current_coin_price - previous_price) / previous_price) * 100

        # Update previous price
        self.previous_prices[current_coin.symbol] = current_coin_price

        # Add more detailed logging
        self.logger.info(f"Current price: {current_coin_price:.8f} {self.config.BRIDGE.symbol}")
        self.logger.info(f"Previous price: {previous_price:.8f} {self.config.BRIDGE.symbol}")
        self.logger.info(f"Price change: {price_change:.2f}%")
        
        # Check if price dropped enough to buy
        if not self.is_holding_coin() and price_change <= -self.min_price_change_percentage:
            amount = self.manager.get_currency_balance(self.config.BRIDGE.symbol)
            trading_fee = self.calculate_trading_fee(amount, current_coin_price)
            self.logger.info(f"Available balance: {amount:.8f} {self.config.BRIDGE.symbol}")
            self.logger.info(f"Trading fee: {trading_fee:.8f} {self.config.BRIDGE.symbol}")
            
            self.save_trade_history(
                operation='BUY',
                coin=current_coin.symbol,
                entry_price=current_coin_price,
                exit_price=0,
                amount=amount,
                trading_fee=trading_fee
            )
            self.buy_coin(current_coin)
            return

        # Check if price increased enough to sell
        if self.is_holding_coin() and price_change >= self.min_price_change_percentage:
            amount = self.manager.get_currency_balance(current_coin.symbol)
            total = amount * current_coin_price
            entry_price = self.get_entry_price(current_coin.symbol)
            trading_fee = self.calculate_trading_fee(amount, current_coin_price)
            
            profit_amount = self.calculate_profit(current_coin.symbol, amount, current_coin_price)
            profit_percentage = (profit_amount / (entry_price * amount)) * 100 if entry_price else 0
            net_profit = profit_amount - trading_fee
            
            self.logger.info(f"Holding amount: {amount:.8f} {current_coin.symbol}")
            self.logger.info(f"Total value: {total:.8f} {self.config.BRIDGE.symbol}")
            self.logger.info(f"Profit amount: {profit_amount:.8f} {self.config.BRIDGE.symbol}")
            self.logger.info(f"Profit percentage: {profit_percentage:.2f}%")
            self.logger.info(f"Trading fee: {trading_fee:.8f} {self.config.BRIDGE.symbol}")
            self.logger.info(f"Net profit: {net_profit:.8f} {self.config.BRIDGE.symbol}")
            
            self.save_trade_history(
                operation='SELL',
                coin=current_coin.symbol,
                entry_price=entry_price,
                exit_price=current_coin_price,
                amount=amount,
                trading_fee=trading_fee,
                profit_amount=profit_amount,
                profit_percentage=profit_percentage,
                net_profit=net_profit
            )
            self.sell_coin(current_coin)
            return

    def buy_coin(self, coin: Coin) -> Optional[float]:
        """Execute buy order for given coin"""
        return self.manager.buy_alt(coin, self.config.BRIDGE)

    def sell_coin(self, coin: Coin) -> Optional[float]:
        """Execute sell order for given coin"""
        return self.manager.sell_alt(coin, self.config.BRIDGE)

    def is_holding_coin(self) -> bool:
        """Check if we currently hold any coin balance"""
        current_coin = self.db.get_current_coin()
        if current_coin is None:
            return False
            
        coin_balance = self.manager.get_currency_balance(current_coin.symbol)
        return coin_balance > 0

    def bridge_scout(self):
        """
        Bridge scout implementation for scalping strategy
        """
        current_coin = self.db.get_current_coin()
        
        # If we have a current coin and enough balance, don't bridge scout
        if current_coin is not None and self.manager.get_currency_balance(current_coin.symbol) > self.manager.get_min_notional(
            current_coin.symbol, self.config.BRIDGE.symbol
        ):
            return None

        # Get coins for trading
        coins = self.db.get_coins()
        for coin in coins:
            # Check if coin price exists and we can buy minimum amount
            coin_price = self.manager.get_ticker_price(coin + self.config.BRIDGE)
            if coin_price is None:
                continue

            if self.manager.get_currency_balance(self.config.BRIDGE.symbol) > self.manager.get_min_notional(
                coin.symbol, self.config.BRIDGE.symbol
            ):
                self.logger.info(f"Bridge scouting: Buying {coin}")
                self.db.set_current_coin(coin)
                self.buy_coin(coin)
                return coin

        return None 
    
    def initialize_current_coin(self):
        """
        Decide what is the current coin, and set it up in the DB.
        """
        if self.db.get_current_coin() is None:
            current_coin_symbol = self.config.CURRENT_COIN_SYMBOL
            if not current_coin_symbol:
                current_coin_symbol = random.choice(self.config.SUPPORTED_COIN_LIST)

            self.logger.info(f"Setting initial coin to {current_coin_symbol}")

            if current_coin_symbol not in self.config.SUPPORTED_COIN_LIST:
                sys.exit("***\nERROR!\nSince there is no backup file, a proper coin name must be provided at init\n***")
            self.db.set_current_coin(current_coin_symbol)

            # if we don't have a configuration, we selected a coin at random... Buy it so we can start trading.
            if self.config.CURRENT_COIN_SYMBOL == "":
                current_coin = self.db.get_current_coin()
                self.logger.info(f"Purchasing {current_coin} to begin trading")
                self.manager.buy_alt(current_coin, self.config.BRIDGE)
                self.logger.info("Ready to start trading")

    def save_trade_history(self, operation: str, coin: str, entry_price: float, exit_price: float, 
                          amount: float, trading_fee: float, profit_amount: float = 0, 
                          profit_percentage: float = 0, net_profit: float = 0):
        """Save detailed trade operation to CSV file"""
        total_value = amount * (exit_price if operation == 'SELL' else entry_price)
        
        with open(self.trade_history_file, 'a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                datetime.now(),
                operation,
                coin,
                f"{entry_price:.8f}",
                f"{exit_price:.8f}" if operation == 'SELL' else "0",
                f"{amount:.8f}",
                f"{total_value:.8f}",
                f"{profit_amount:.8f}" if operation == 'SELL' else "0",
                f"{profit_percentage:.2f}" if operation == 'SELL' else "0",
                f"{trading_fee:.8f}",
                f"{net_profit:.8f}" if operation == 'SELL' else "0"
            ])

    def get_entry_price(self, coin: str) -> Optional[float]:
        """Get the entry price from the last BUY operation"""
        try:
            with open(self.trade_history_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                last_buy = None
                for row in reader:
                    if row[1] == 'BUY' and row[2] == coin:
                        last_buy = row
                
                if last_buy:
                    return float(last_buy[3])  # Entry price is in column 3
        except Exception as e:
            self.logger.error(f"Error getting entry price: {e}")
        return None

    def calculate_trading_fee(self, amount: float, price: float) -> float:
        """Calculate trading fee for the transaction"""
        total_value = amount * price
        fee_percentage = 0.001  # Assuming 0.1% trading fee, adjust as needed
        return total_value * fee_percentage

    def calculate_profit(self, coin: str, amount: float, current_price: float) -> float:
        """Calculate profit/loss for current trade"""
        # Read last BUY operation from CSV to get entry price
        try:
            with open(self.trade_history_file, 'r') as f:
                reader = csv.reader(f)
                next(reader)  # Skip header
                last_buy = None
                for row in reader:
                    if row[1] == 'BUY' and row[2] == coin:
                        last_buy = row
                
                if last_buy:
                    entry_price = float(last_buy[3])
                    return (current_price - entry_price) * amount
        except Exception as e:
            self.logger.error(f"Error calculating profit: {e}")
        return 0
