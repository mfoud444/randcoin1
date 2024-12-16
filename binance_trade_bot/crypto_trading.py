#!python3
import time

from .binance_api_manager import BinanceAPIManager
from .config import Config
from .database import Database
from .logger import Logger
from .scheduler import SafeScheduler
from .strategies import get_strategy


def main():
    logger = Logger()
    logger.info("Starting")

    config = Config()
    db = Database(logger, config)
    manager = BinanceAPIManager(config, db, logger)
    # check if we can access API feature that require valid config
    try:
        _ = manager.get_account()
    except Exception as e:  # pylint: disable=broad-except
        logger.error("Couldn't access Binance API - API keys may be wrong or lack sufficient permissions")
        logger.error(e)
        return
    # coins_data = []
    # for coin in supported_coins:
    #     balance = manager.get_currency_balance(coin.symbol)
    #     usd_price = manager.get_ticker_price(f"{coin.symbol}{config.BRIDGE_SYMBOL}")
    #     btc_price = manager.get_ticker_price(f"{coin.symbol}BTC")
        
    #     coin_data = {
    #         "symbol": coin.symbol,
    #         "enabled": coin.enabled,
    #         "balance": balance,
    #         "usd_price": usd_price,
    #         "btc_price": btc_price,
    #         "usd_value": balance * usd_price if usd_price else None,
    #         "btc_value": balance * btc_price if btc_price else None
    #     }
    #     coins_data.append(coin_data)
            
    strategy = get_strategy(config.STRATEGY)
    if strategy is None:
        logger.error("Invalid strategy name")
        return
    trader = strategy(manager, db, logger, config)
    logger.info(f"Chosen strategy: {config.STRATEGY}")

    logger.info("Creating database schema if it doesn't already exist")
    db.create_database()
    # config.SUPPORTED_COIN_LIST = manager.get_all_coins()

    db.set_coins(config.SUPPORTED_COIN_LIST)
    db.migrate_old_state()

    trader.initialize()

    schedule = SafeScheduler(logger)
    schedule.every(config.SCOUT_SLEEP_TIME).seconds.do(trader.scout).tag("scouting")
    schedule.every(1).minutes.do(trader.update_values).tag("updating value history")
    schedule.every(1).minutes.do(db.prune_scout_history).tag("pruning scout history")
    schedule.every(1).hours.do(db.prune_value_history).tag("pruning value history")
    try:
        while True:
            schedule.run_pending()
            time.sleep(1)
    finally:
        manager.stream_manager.close()
