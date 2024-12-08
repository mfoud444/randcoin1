#!/bin/bash

if [ "$1" = "api" ]; then
    exec python -m binance_trade_bot.api_server
else
    exec python -m binance_trade_bot
fi