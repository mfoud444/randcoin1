FROM --platform=$BUILDPLATFORM python:3.8 as builder

WORKDIR /install

RUN apt-get update && apt-get install -y rustc

COPY requirements.txt /requirements.txt
# Update pip before installing dependencies
RUN pip install --upgrade pip

RUN pip install --prefix=/install -r /requirements.txt

FROM python:3.8-slim

WORKDIR /app

COPY --from=builder /install /usr/local
COPY . .

CMD ["python", "-m", "binance_trade_bot"]
