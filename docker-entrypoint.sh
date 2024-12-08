#!/bin/bash
set -e

if [ "$1" = "api" ]; then
    # Run with gunicorn for production
    exec gunicorn binance_trade_bot.api_server:app \
        --worker-class eventlet \
        --workers 1 \
        --threads 1 \
        --bind 0.0.0.0:5123 \
        --timeout 120 \
        --preload
else
    # Run the trading bot
    exec python -m binance_trade_bot
fi