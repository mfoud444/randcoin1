import csv
import time
import logging
from datetime import datetime
from typing import Dict, Optional, List, Any

import pandas as pd
import numpy as np
import talib
import ccxt

class AdvancedCryptoScalper:
    def __init__(self, 
                 exchange_id: str = 'binance', 
                 api_key: str = None, 
                 api_secret: str = None,
                 threshold: float = 0.05, 
                 monitor_time: int = 600,
                 poll_interval: int = 2,
                 min_volume: float = 100000,  # Minimum daily trading volume
                 major_pairs: List[str] = ['USDT', 'BTC']
    ):
        # Setup logging
        self.setup_logging()
        
        # Initialize exchange
        self.exchange = self.get_exchange(exchange_id, api_key, api_secret, )
        
        # Configuration parameters
        self.threshold = threshold
        self.monitor_time = monitor_time
        self.poll_interval = poll_interval
        self.min_volume = min_volume
        self.major_pairs = major_pairs
        
        # Data storage
        self.csv_filename = f"crypto_scalping_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        self.trades_log = []
    
    def setup_logging(self):
        """Configure comprehensive logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s: %(message)s',
            filename=f'scalping_log_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log',
            filemode='w'
        )
        self.logger = logging.getLogger(__name__)
    
    def get_exchange(self, exchange_id: str, api_key: str = None, api_secret: str = None):
        """Initialize exchange with error handling"""
        try:
            exchange_class = getattr(ccxt, exchange_id)
            exchange = exchange_class({
                'apiKey': api_key,
                'secret': api_secret,
                'enableRateLimit': True,
            
            })
            return exchange
        except Exception as e:
            self.logger.error(f"Exchange initialization error: {e}")
            raise
    
    def filter_tradable_symbols(self):
        """
        Advanced symbol filtering:
        1. Check trading volume
        2. Ensure major trading pairs
        3. Verify exchange support
        """
        try:
            markets = self.exchange.load_markets()
            filtered_symbols = []
            
            for symbol, market in markets.items():
                # Volume filter
                try:
                    ticker = self.exchange.fetch_ticker(symbol)
                    daily_volume = ticker['quoteVolume']
                    
                    # Check volume and pair criteria
                    if (daily_volume >= self.min_volume and 
                        any(pair in symbol for pair in self.major_pairs)):
                        filtered_symbols.append(symbol)
                
                except Exception as e:
                    self.logger.warning(f"Could not process symbol {symbol}: {e}")
            
            return filtered_symbols
        
        except Exception as e:
            self.logger.error(f"Symbol filtering error: {e}")
            return []
    
    def calculate_technical_indicators(self, ohlcv_data):
        """
        Calculate advanced technical indicators
        - RSI
        - Moving Averages
        - Bollinger Bands
        """
        close_prices = np.array([candle[4] for candle in ohlcv_data])
        
        # RSI
        rsi = talib.RSI(close_prices, timeperiod=14)
        
        # Moving Averages
        sma_50 = talib.SMA(close_prices, timeperiod=50)
        sma_200 = talib.SMA(close_prices, timeperiod=200)
        
        # Bollinger Bands
        upperband, middleband, lowerband = talib.BBANDS(close_prices, timeperiod=20, nbdevup=2, nbdevdn=2, matype=0)
        
        return {
            'rsi': rsi[-1],
            'sma_50': sma_50[-1],
            'sma_200': sma_200[-1],
            'bollinger_upper': upperband[-1],
            'bollinger_lower': lowerband[-1]
        }
    
    def advanced_trading_strategy(self, symbol, ohlcv_data, technical_indicators):
        """
        Advanced trading decision making
        Combines price changes with technical indicators
        """
        close_price = ohlcv_data[-1][4]  # Last close price
        
        # Trading strategy logic
        buy_signals = []
        sell_signals = []
        
        # RSI Strategy
        if technical_indicators['rsi'] < 30:
            buy_signals.append('RSI oversold')
        elif technical_indicators['rsi'] > 70:
            sell_signals.append('RSI overbought')
        
        # Moving Average Strategy
        if technical_indicators['sma_50'] > technical_indicators['sma_200']:
            buy_signals.append('Bullish MA Crossover')
        else:
            sell_signals.append('Bearish MA Crossover')
        
        # Bollinger Band Strategy
        if close_price <= technical_indicators['bollinger_lower']:
            buy_signals.append('Price near lower Bollinger Band')
        elif close_price >= technical_indicators['bollinger_upper']:
            sell_signals.append('Price near upper Bollinger Band')
        
        return {
            'buy_signals': buy_signals,
            'sell_signals': sell_signals
        }
    
    def start_monitoring(self):
        """
        Enhanced monitoring with advanced filtering and analysis
        """
        # Filter tradable symbols
        tradable_symbols = self.filter_tradable_symbols()
        self.logger.info(f"Monitoring {len(tradable_symbols)} symbols")
        
        start_time = time.time()
        while time.time() - start_time < self.monitor_time:
            for symbol in tradable_symbols:
                try:
                    # Fetch OHLCV data
                    ohlcv_data = self.exchange.fetch_ohlcv(symbol, '1m', limit=100)
                    
                    # Calculate technical indicators
                    technical_indicators = self.calculate_technical_indicators(ohlcv_data)
                    
                    # Apply trading strategy
                    trade_signals = self.advanced_trading_strategy(symbol, ohlcv_data, technical_indicators)
                    
                    # Log and potentially execute trades
                    if trade_signals['buy_signals'] or trade_signals['sell_signals']:
                        self.log_trade_opportunity(symbol, trade_signals, ohlcv_data[-1][4])
                
                except Exception as e:
                    self.logger.error(f"Error processing {symbol}: {e}")
            
            time.sleep(self.poll_interval)
    
    def log_trade_opportunity(self, symbol, signals, current_price):
        """
        Comprehensive trade opportunity logging
        """
        trade_log_entry = {
            'symbol': symbol,
            'timestamp': datetime.now().isoformat(),
            'current_price': current_price,
            'buy_signals': signals['buy_signals'],
            'sell_signals': signals['sell_signals']
        }
        
        self.trades_log.append(trade_log_entry)
        self.logger.info(f"Trade Opportunity - {symbol}: {trade_log_entry}")
        
        # Optional: Save to CSV for further analysis
        pd.DataFrame(self.trades_log).to_csv(self.csv_filename, index=False)

def main():
    # Replace with your actual credentials
    scalper = AdvancedCryptoScalper(
        exchange_id='binance',  # Can be changed to other exchanges
        api_key='your_api_key',
        api_secret='your_api_secret',
        threshold=0.05,
        monitor_time=1200,  # 20 minutes
        min_volume=100000,  # Minimum daily trading volume
        major_pairs=['USDT', 'BTC']
    )
    
    try:
        scalper.start_monitoring()
    except Exception as e:
        scalper.logger.critical(f"Monitoring failed: {e}")

if __name__ == "__main__":
    main()
    
    
    
    
    
import os
import ccxt
import pandas as pd
import numpy as np
import asyncio
import concurrent.futures
from binance.client import Client
from typing import List, Dict, Optional
import warnings
import nest_asyncio
nest_asyncio.apply()
warnings.filterwarnings('ignore')

class BinanceTradeAnalyzer:
    def __init__(
        self, 
        api_key: Optional[str] = None, 
        api_secret: Optional[str] = None, 
        specific_coins: Optional[List[str]] = None
    ):
        self.client = Client(api_key, api_secret, tld='us') if api_key and api_secret else Client()
        self.specific_coins = specific_coins
        
        self.INTERVALS = 4
        self.INTERVAL_MINUTES = 20
        self.TRADING_FEE = 0.001  # 0.1% per trade
        self.PROFIT_TARGET = 0.01  # 5% net profit target

    def get_tradable_coins(self) -> List[str]:
        """
        Fetch USDT trading pairs, with option to use all or specific coins
        """
        if self.specific_coins:
            return [coin.upper() + 'USDT' for coin in self.specific_coins if coin.upper() + 'USDT' in self.get_all_usdt_pairs()]
        
        return self.get_all_usdt_pairs()

    def get_all_usdt_pairs(self) -> List[str]:
        """
        Retrieve all USDT trading pairs
        """
        exchange_info = self.client.get_exchange_info()
        return [
            symbol['symbol'] 
            for symbol in exchange_info['symbols'] 
            if symbol['symbol'].endswith('USDT') and symbol['status'] == 'TRADING'
        ]

    async def fetch_price_data(self, symbol: str) -> pd.DataFrame:
        """
        Fetch price data for a specific symbol across multiple intervals
        """
        try:
            klines = self.client.get_klines(
                symbol=symbol, 
                interval=f'{self.INTERVAL_MINUTES}m', 
                limit=self.INTERVALS
            )
            
            df = pd.DataFrame(klines, columns=[
                'Open Time', 'Open', 'High', 'Low', 'Close', 
                'Volume', 'Close Time', 'Quote Asset Volume', 
                'Number of Trades', 'Taker Buy Base Asset Volume', 
                'Taker Buy Quote Asset Volume', 'Ignore'
            ])
            
            df['Close'] = df['Close'].astype(float)
            df['Percentage_Change'] = df['Close'].pct_change() * 100
            df['Symbol'] = symbol
            
            return df
        except Exception as e:
            print(f"Error fetching data for {symbol}: {e}")
            return pd.DataFrame()

    def analyze_price_changes(self, dataframes: List[pd.DataFrame]) -> pd.DataFrame:
        """
        Compute price change statistics and assign points
        """
        analysis_results = []
        
        for df in dataframes:
            if df.empty:
                continue
            
            positive_changes = (df['Percentage_Change'] > 0).sum()
            negative_changes = (df['Percentage_Change'] < 0).sum()
            
            coin_analysis = {
                'Symbol': df['Symbol'].iloc[0],
                'Positive_Changes': positive_changes,
                'Negative_Changes': negative_changes,
                'Net_Change': df['Percentage_Change'].sum(),
                'Volatility': df['Percentage_Change'].std(),
                'Points': positive_changes - negative_changes
            }
            
            analysis_results.append(coin_analysis)
        
        return pd.DataFrame(analysis_results)

    async def process_coins(self) -> pd.DataFrame:
        """
        Process all coins concurrently and analyze results
        """
        tradable_coins = self.get_tradable_coins()
        
        async def process_symbol(symbol):
            return await self.fetch_price_data(symbol)
        
        async with asyncio.Semaphore(10):  # Limit concurrent requests
            price_dataframes = await asyncio.gather(*[process_symbol(symbol) for symbol in tradable_coins])
        
        return self.analyze_price_changes(price_dataframes)

    def simulate_investment(self, analysis_df: pd.DataFrame, initial_capital: float = 100) -> pd.DataFrame:
        """
        Simulate investment strategy with reinvestment and fee calculation
        """
        results = []
        
        for _, row in analysis_df.iterrows():
            capital = initial_capital
            for interval in range(self.INTERVALS):
                profit_percentage = row['Points'] * 0.5  # Example profit calculation
                
                # Apply trading fee
                net_profit = capital * (profit_percentage - self.TRADING_FEE)
                capital += net_profit
                
                results.append({
                    'Symbol': row['Symbol'],
                    'Interval': interval + 1,
                    'Capital': capital,
                    'Profit_Percentage': profit_percentage
                })
        
        return pd.DataFrame(results)

    async def run_analysis(self) -> Dict[str, pd.DataFrame]:
        """
        Main method to run complete trading analysis
        """
        analysis_df = await self.process_coins()
        
        # Filter coins with more positive than negative changes
        filtered_df = analysis_df[analysis_df['Points'] > 0]
        
        investment_simulation = self.simulate_investment(filtered_df)
        
        return {
            'price_analysis': analysis_df,
            'filtered_coins': filtered_df,
            'investment_simulation': investment_simulation
        }

async def main():
    # Example usage with optional specific coins
    analyzer = BinanceTradeAnalyzer(
        api_key=os.getenv('BINANCE_API_KEY'), 
        api_secret=os.getenv('BINANCE_API_SECRET'),
        specific_coins=['BTC', 'ETH', 'BNB']  # Optional: specify coins
    )
    
    results = await analyzer.run_analysis()
    
    print("Price Analysis:")
    print(results['price_analysis'])
    print("\nFiltered Coins:")
    print(results['filtered_coins'])
    print("\nInvestment Simulation:")
    print(results['investment_simulation'])

if __name__ == '__main__':
    asyncio.run(main())