import threading
# from .crypto_trading import main
from .wow import main
from .api_server import run_api_server

if __name__ == "__main__":
    try:
        # Create thread for running api server
        api_server_thread = threading.Thread(target=run_api_server)
        api_server_thread.start()
        
        # Run the main trading bot
        main()
    except KeyboardInterrupt:
        exit(0)
