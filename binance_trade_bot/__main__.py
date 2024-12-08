import threading
from .crypto_trading import main
from .api_server import run_api_server

if __name__ == "__main__":
    try:
        # Create threads for both processes
        trading_thread = threading.Thread(target=main, daemon=True)
        api_thread = threading.Thread(target=run_api_server, daemon=True)
        
        # Start both threads
        trading_thread.start()
        api_thread.start()
        
        # Wait for threads to complete (which they won't unless there's an error)
        trading_thread.join()
        api_thread.join()
    except KeyboardInterrupt:
        pass
