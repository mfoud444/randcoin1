from binance.client import Client

# Initialize the Binance client
api_key = 'your_api_key'
api_secret = 'your_api_secret'
client = Client(api_key, api_secret)

# Fetch all trading pairs and extract unique coins
exchange_info = client.get_exchange_info()
symbols = exchange_info['symbols']

# Extract base and quote assets
coins = set()
for symbol in symbols:
    coins.add(symbol['baseAsset'])
    coins.add(symbol['quoteAsset'])

# Print all unique coins
print("All Coins:")
print(sorted(coins))
