from binance.client import Client
import pandas as pd

# Initialize Binance Client
api_key = "your_api_key"
api_secret = "your_api_secret"
client = Client(api_key, api_secret)

def get_all_tickers_movement_with_percentage(interval="1h"):
    """
    Fetch the movement direction and percentage change of all coins over a specific time interval.

    Args:
        interval (str): The interval for candlesticks (e.g., "1m", "5m", "1h", "1d").
        
    Returns:
        pd.DataFrame: DataFrame with coin symbols, directions, and percentage changes.
    """
    tickers = client.get_all_tickers()
    movement_data = []

    for ticker in tickers:
        symbol = ticker['symbol']
        if symbol.endswith('USDT'):  # Filter only USDT pairs
            try:
                # Fetch candlestick data
                candles = client.get_klines(symbol=symbol, interval=interval, limit=2)
                open_price = float(candles[0][1])
                close_price = float(candles[-1][4])

                # Calculate percentage change
                percentage_change = ((close_price - open_price) / open_price) * 100

                # Determine movement direction
                if percentage_change > 0:
                    direction = "Up"
                elif percentage_change < 0:
                    direction = "Down"
                else:
                    direction = "Sideways"

                movement_data.append({
                    "Symbol": symbol,
                    "Direction": direction,
                    "Open Price": open_price,
                    "Close Price": close_price,
                    "Percentage Change (%)": round(percentage_change, 2)
                })
            except Exception as e:
                print(f"Error fetching data for {symbol}: {e}")

    # Convert to DataFrame
    df = pd.DataFrame(movement_data)
    return df

if __name__ == "__main__":
    interval = "30m"  # Change interval as needed
    data = get_all_tickers_movement_with_percentage(interval)
    print(data)
    # Save results to a CSV file
    # movements.to_csv("coin_movements_with_percentage.csv", index=False)
    # data = pd.read_csv("coin_movements_with_percentage.csv")

    positive_changes = data[data['Percentage Change (%)'] > 0]
    sorted_positive_changes = positive_changes.sort_values(by='Percentage Change (%)', ascending=False)

    # Display the sorted list
    print("Coins ordered by biggest positive percentage change:")
    for index, row in sorted_positive_changes.iterrows():
        print(f"Symbol: {row['Symbol']}, Percentage Change: {row['Percentage Change (%)']}%")


