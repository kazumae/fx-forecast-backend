"""
TraderMade WebSocket Streaming Client with Database Storage
"""
import asyncio
import logging
import signal
import sys
from typing import Optional, Set
import os

from src.stream.websocket_manager import WebSocketManager
from src.stream.data_processor_db import DataProcessorDB
from src.stream.config import StreamConfig
from src.stream.graceful_shutdown import GracefulShutdownHandler
from src.stream.resource_manager import ResourceManager
import logging


class StreamClientDB:
    """Main streaming client with database storage"""
    
    def __init__(self):
        """Initialize stream client"""
        # Setup logging
        logging.basicConfig(level=logging.INFO)
        self.logger = logging.getLogger(__name__)
        
        # Initialize components
        self.config = StreamConfig.from_env()
        self.ws_manager = WebSocketManager(self.config)
        self.data_processor = DataProcessorDB()
        self.shutdown_handler = GracefulShutdownHandler()
        self.resource_manager = ResourceManager()
        
        # Target symbols from environment
        symbols_str = os.getenv("TARGET_SYMBOLS", "XAUUSD")
        self.target_symbols: Set[str] = set(s.strip() for s in symbols_str.split(","))
        
        # Track running state
        self.is_running = False
        
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            self.stop()
            
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
        
    async def start(self):
        """Start the streaming client"""
        self.logger.info("Starting TraderMade stream client with DB storage...")
        self.logger.info(f"Target symbols: {', '.join(self.target_symbols)}")
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        # Mark as running
        self.is_running = True
        
        try:
            # Set authenticated callback to subscribe to symbols
            def on_authenticated():
                self.logger.info("Authentication successful, subscribing to symbols")
                for symbol in self.target_symbols:
                    self.ws_manager.subscribe_to_symbol(symbol)
                    self.logger.info(f"Subscribed to {symbol}")
            
            self.ws_manager.on_authenticated = on_authenticated
            
            # Set price data callback to use data processor
            def on_price_data(price_info: dict):
                self.data_processor.process_price_data(price_info)
            
            self.ws_manager.on_price_data = on_price_data
            
            # Connect to WebSocket
            self.logger.info("Initiating WebSocket connection...")
            self.ws_manager.connect()
            
            # Keep the main thread alive
            while self.is_running and self.ws_manager._should_run:
                await asyncio.sleep(1)
                
        except Exception as e:
            self.logger.error(f"Fatal error: {e}")
        finally:
            await self.cleanup()
            
    def stop(self):
        """Stop the streaming client"""
        self.logger.info("Stopping stream client...")
        self.is_running = False
        
        # Initiate shutdown
        self.shutdown_handler.initiate_shutdown()
        
    async def cleanup(self):
        """Clean up resources"""
        self.logger.info("Cleaning up resources...")
        
        # Close WebSocket
        if self.ws_manager:
            self.ws_manager.close()
            
        # Close data processor
        if self.data_processor:
            self.data_processor.close()
        
        self.logger.info("Cleanup complete")
        

async def main():
    """Main entry point"""
    client = StreamClientDB()
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logging.info("Interrupted by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        sys.exit(1)
        

if __name__ == "__main__":
    # Run the async main function
    asyncio.run(main())