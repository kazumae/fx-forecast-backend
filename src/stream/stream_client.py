"""
TraderMade Real-time Streaming Client
"""
import logging
import logging.handlers
import os
import signal
import sys
import time
from datetime import datetime
from pathlib import Path

from .config import StreamConfig
from .websocket_manager import WebSocketManager
from .data_processor import DataProcessor
from .logging_utils import SensitiveDataFilter


class StreamClient:
    """Main streaming client application"""
    
    def __init__(self):
        """Initialize streaming client"""
        self.config = None
        self.websocket_manager = None
        self.data_processor = None
        self.logger = None
        self.running = True
        
    def setup_logging(self, config: StreamConfig):
        """Setup logging configuration"""
        # Create logs directory if it doesn't exist
        log_dir = Path(config.log_file_path)
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # Setup logger
        logger = logging.getLogger()
        logger.setLevel(getattr(logging, config.log_level.upper()))
        
        # Console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        
        # File handler with rotation
        log_file = log_dir / f'stream_client_{datetime.now().strftime("%Y%m%d")}.log'
        file_handler = logging.handlers.TimedRotatingFileHandler(
            log_file,
            when='midnight',
            interval=1,
            backupCount=30,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Add handlers
        logger.addHandler(console_handler)
        logger.addHandler(file_handler)
        
        # Add sensitive data filter
        sensitive_patterns = []
        if hasattr(config, 'api_key') and config.api_key:
            sensitive_patterns.append(config.api_key)
        
        sensitive_filter = SensitiveDataFilter(sensitive_patterns)
        for handler in logger.handlers:
            handler.addFilter(sensitive_filter)
        
        self.logger = logging.getLogger(__name__)
        self.logger.info("Logging setup complete with sensitive data filtering")
    
    def setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)
        self.logger.info("Signal handlers registered")
    
    def _handle_signal(self, signum, frame):
        """Handle shutdown signals"""
        signal_name = signal.Signals(signum).name
        self.logger.info(f"Received {signal_name}, initiating graceful shutdown")
        self.running = False
        
        if self.websocket_manager:
            self.websocket_manager.close()
    
    def run(self):
        """Run the streaming client"""
        try:
            # Load configuration
            self.config = StreamConfig.from_env()
            
            # Setup logging
            self.setup_logging(self.config)
            
            # Log startup information
            self.logger.info("=" * 50)
            self.logger.info("TraderMade Streaming Client Starting")
            self.logger.info(f"Target Symbol: {self.config.target_symbol}")
            self.logger.info(f"WebSocket URL: {self.config.websocket_url}")
            self.logger.info("=" * 50)
            
            # Setup signal handlers
            self.setup_signal_handlers()
            
            # Create WebSocket manager
            self.websocket_manager = WebSocketManager(self.config)
            
            # Create data processor
            self.data_processor = DataProcessor()
            
            # Set authenticated callback to subscribe to symbol
            def on_authenticated():
                self.logger.info(f"Authentication successful, subscribing to {self.config.target_symbol}")
                self.websocket_manager.subscribe_to_symbol(self.config.target_symbol)
            
            self.websocket_manager.on_authenticated = on_authenticated
            
            # Set price data callback to use data processor
            def on_price_data(price_info: dict):
                self.data_processor.process_price_data(price_info)
            
            self.websocket_manager.on_price_data = on_price_data
            
            # Connect to WebSocket
            self.logger.info("Initiating WebSocket connection...")
            self.websocket_manager.connect()
            
            # Keep the main thread alive
            while self.running and self.websocket_manager._should_run:
                time.sleep(1)
            
        except ValueError as e:
            print(f"Configuration error: {e}")
            sys.exit(1)
        except KeyboardInterrupt:
            self.logger.info("Keyboard interrupt received")
        except Exception as e:
            if self.logger:
                self.logger.critical(f"Unexpected error: {e}", exc_info=True)
            else:
                print(f"Critical error: {e}")
            sys.exit(1)
        finally:
            # Display price summary before exiting
            if self.data_processor:
                self.data_processor.display_summary()
            
            # Display error summary
            if self.websocket_manager and self.websocket_manager.error_handler:
                error_summary = self.websocket_manager.error_handler.get_error_summary()
                if error_summary["total_errors"] > 0:
                    self.logger.info(f"Error Summary: {error_summary}")
            
            if self.logger:
                self.logger.info("TraderMade Streaming Client stopped")


def main():
    """Main entry point"""
    client = StreamClient()
    client.run()


if __name__ == "__main__":
    main()