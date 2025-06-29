"""
WebSocket Manager for TraderMade Streaming
"""
import json
import logging
import ssl
import time
import threading
from typing import Optional, Callable
from datetime import datetime
from enum import Enum

import websocket

from .config import StreamConfig
from .error_handler import ErrorHandler, ErrorType
from .slack_error_notifier import SlackErrorNotifier


class ConnectionState(Enum):
    """WebSocket connection states"""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    AUTHENTICATED = "authenticated"
    RECONNECTING = "reconnecting"
    ERROR = "error"


class WebSocketManager:
    """Manages WebSocket connection to TraderMade API"""
    
    def __init__(self, config: StreamConfig):
        """Initialize WebSocket manager
        
        Args:
            config: Stream configuration
        """
        self.config = config
        self.ws: Optional[websocket.WebSocketApp] = None
        self.logger = logging.getLogger(__name__)
        
        # State management
        self._state = ConnectionState.DISCONNECTED
        self._state_lock = threading.Lock()
        
        # Callbacks
        self.on_authenticated: Optional[Callable] = None
        self.on_price_data: Optional[Callable] = None
        
        # Subscription tracking
        self.subscribed_symbols = set()
        self._symbols_lock = threading.Lock()
        
        # Connection management
        self._ws_thread: Optional[threading.Thread] = None
        self._should_run = True
        self._reconnect_count = 0
        self._reconnect_thread: Optional[threading.Thread] = None
        
        # Error handling with Slack notifications
        slack_notifier = None
        if hasattr(config, 'slack_error_notification_enabled') and config.slack_error_notification_enabled:
            slack_cooldown = getattr(config, 'slack_error_notification_cooldown', 300)
            slack_notifier = SlackErrorNotifier(notification_cooldown=slack_cooldown)
        else:
            # Check environment variable
            import os
            if os.getenv('SLACK_ERROR_NOTIFICATION_ENABLED', '').lower() == 'true':
                slack_cooldown = int(os.getenv('SLACK_ERROR_NOTIFICATION_COOLDOWN', '300'))
                slack_notifier = SlackErrorNotifier(notification_cooldown=slack_cooldown)
        
        self.error_handler = ErrorHandler(slack_notifier=slack_notifier)
    
    @property
    def state(self) -> ConnectionState:
        """Get current connection state"""
        with self._state_lock:
            return self._state
    
    @state.setter
    def state(self, new_state: ConnectionState):
        """Set connection state"""
        with self._state_lock:
            old_state = self._state
            self._state = new_state
            if old_state != new_state:
                self.logger.info(f"State changed: {old_state.value} -> {new_state.value}")
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected"""
        return self.state in [ConnectionState.CONNECTED, ConnectionState.AUTHENTICATED]
    
    @property
    def is_authenticated(self) -> bool:
        """Check if WebSocket is authenticated"""
        return self.state == ConnectionState.AUTHENTICATED
        
    def connect(self):
        """Establish WebSocket connection"""
        if self.state != ConnectionState.DISCONNECTED:
            self.logger.warning(f"Cannot connect in state: {self.state.value}")
            return
        
        self.state = ConnectionState.CONNECTING
        self._should_run = True
        
        # Start WebSocket in a separate thread
        self._ws_thread = threading.Thread(target=self._run_websocket, name="WebSocket-Thread")
        self._ws_thread.daemon = True
        self._ws_thread.start()
        
        # Wait a bit for connection to establish
        time.sleep(2)
        
        # If not connected after initial wait, start reconnection thread
        if not self.is_connected and self._should_run:
            self._start_reconnection()
    
    def _run_websocket(self):
        """Run WebSocket connection in thread"""
        try:
            self.logger.info(f"Connecting to {self.config.websocket_url}")
            
            self.ws = websocket.WebSocketApp(
                self.config.websocket_url,
                on_open=self._on_open,
                on_message=self._on_message,
                on_error=self._on_error,
                on_close=self._on_close,
                on_ping=self._on_ping,
                on_pong=self._on_pong
            )
            
            # SSL configuration for secure connection
            sslopt = {
                "cert_reqs": ssl.CERT_REQUIRED,
                "ssl_version": ssl.PROTOCOL_TLS,
                "check_hostname": True
            }
            
            # Run with timeout
            self.ws.run_forever(
                sslopt=sslopt,
                ping_interval=self.config.heartbeat_interval,
                ping_timeout=10
            )
            
        except Exception as e:
            error_info = self.error_handler.handle_error(e, "WebSocket connection")
            if error_info["action"] == "terminate":
                self.state = ConnectionState.ERROR
                self._should_run = False
            else:
                self.state = ConnectionState.DISCONNECTED
        finally:
            self.logger.debug("WebSocket thread ended")
    
    def _start_reconnection(self):
        """Start reconnection thread"""
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            return
        
        self._reconnect_thread = threading.Thread(
            target=self._reconnect_loop, 
            name="Reconnect-Thread"
        )
        self._reconnect_thread.daemon = True
        self._reconnect_thread.start()
    
    def _reconnect_loop(self):
        """Reconnection loop with exponential backoff"""
        while self._should_run and not self.is_connected:
            interval = self._calculate_backoff()
            self.logger.info(f"Reconnecting in {interval} seconds... (attempt {self._reconnect_count + 1})")
            
            # Wait for interval, but check periodically if we should stop
            for _ in range(int(interval)):
                if not self._should_run or self.is_connected:
                    return
                time.sleep(1)
            
            if not self._should_run or self.is_connected:
                return
            
            self.state = ConnectionState.RECONNECTING
            self._reconnect_count += 1
            
            # Try to reconnect
            self._run_websocket()
            
            # Check if connected
            if self.is_connected:
                self.logger.info("Reconnection successful")
                self._reconnect_count = 0
                self.error_handler.reset_error_counts()  # Reset error counts on successful connection
                self._restore_subscriptions()
                break
    
    def _calculate_backoff(self) -> float:
        """Calculate exponential backoff interval"""
        base_interval = self.config.reconnect_interval
        max_interval = self.config.max_reconnect_interval
        
        # 2^n * base_interval (capped at max_interval)
        interval = min(base_interval * (2 ** self._reconnect_count), max_interval)
        return interval
    
    def _restore_subscriptions(self):
        """Restore previous subscriptions after reconnection"""
        with self._symbols_lock:
            symbols = list(self.subscribed_symbols)
        
        for symbol in symbols:
            try:
                self.subscribe_to_symbol(symbol)
                self.logger.info(f"Restored subscription for {symbol}")
            except Exception as e:
                self.logger.error(f"Failed to restore subscription for {symbol}: {e}")
    
    def _on_open(self, ws):
        """Handle connection open event"""
        self.state = ConnectionState.CONNECTED
        self.logger.info("WebSocket connection established")
        
        # Send authentication message
        self._authenticate()
    
    def _authenticate(self):
        """Send authentication message"""
        auth_message = {
            "userKey": self.config.api_key
        }
        
        try:
            message = json.dumps(auth_message)
            self.ws.send(message)
            self.logger.info("Authentication message sent")
            self.logger.debug(f"Sending authentication message to TraderMade")
        except Exception as e:
            self.error_handler.handle_error(e, "Authentication send")
            self.close()
    
    def _on_message(self, ws, message):
        """Handle incoming messages"""
        try:
            # Skip empty messages
            if not message or not message.strip():
                return
            
            # Log raw message for debugging
            self.logger.debug(f"Raw message received: {repr(message)}")
            
            # Handle plain text "Connected" message from TraderMade
            if message.strip() == "Connected":
                self.state = ConnectionState.AUTHENTICATED
                self.logger.info("Authentication successful - Connected to TraderMade")
                if self.on_authenticated:
                    self.on_authenticated()
                return
            
            # Try to parse as JSON
            try:
                data = json.loads(message)
                
                # Check for authentication response
                if data.get("event") == "login":
                    if data.get("success"):
                        self.state = ConnectionState.AUTHENTICATED
                        self.logger.info("Authentication successful")
                        
                        # Trigger authenticated callback
                        if self.on_authenticated:
                            self.on_authenticated()
                    else:
                        auth_error = Exception(f"Authentication failed: {data.get('message', 'Unknown error')}")
                        self.error_handler.handle_error(auth_error, "Authentication response", ErrorType.AUTH_ERROR)
                        self.state = ConnectionState.ERROR
                        self._should_run = False
                        self.close()
                        return
                
                # Handle subscription confirmation
                elif data.get("event") == "subscribed":
                    symbol = data.get("symbol")
                    if symbol:
                        with self._symbols_lock:
                            self.subscribed_symbols.add(symbol)
                        self.logger.info(f"Subscription confirmed for {symbol}")
                
                # Handle price data (expected format for TraderMade)
                elif "symbol" in data and ("bid" in data or "ask" in data):
                    self._process_price_data(data)
                
                # Log other messages
                else:
                    self.logger.info(f"Received data: {data}")
                    # Check if it's a subscription-related message
                    if "subscription" in str(data).lower() or symbol in self.subscribed_symbols:
                        self.logger.info("Possible subscription response detected")
                
            except json.JSONDecodeError as e:
                # Log non-JSON messages that aren't "Connected"
                self.error_handler.handle_error(e, f"JSON decode error: {repr(message)}", ErrorType.DATA_ERROR)
                
        except Exception as e:
            self.error_handler.handle_error(e, "Message processing")
    
    def _on_error(self, ws, error):
        """Handle WebSocket errors"""
        error_info = self.error_handler.handle_error(error, "WebSocket event")
        
        # Take action based on error handler recommendation
        if error_info["action"] == "terminate":
            self._should_run = False
            self.state = ConnectionState.ERROR
        elif error_info["action"] == "reconnect" and self._should_run:
            self.state = ConnectionState.DISCONNECTED
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Handle connection close event"""
        self.state = ConnectionState.DISCONNECTED
        
        self.logger.info(
            f"WebSocket connection closed - "
            f"Status: {close_status_code}, Message: {close_msg}"
        )
        
        # Start reconnection if not manually stopped
        if self._should_run:
            self._start_reconnection()
    
    def _on_ping(self, ws, message):
        """Handle ping message"""
        self.logger.debug("Ping received")
    
    def _on_pong(self, ws, message):
        """Handle pong message"""
        self.logger.debug("Pong received")
    
    def send(self, message: dict):
        """Send message through WebSocket
        
        Args:
            message: Message dictionary to send
        """
        if not self.is_connected:
            self.logger.error("Cannot send message - not connected")
            return
        
        if not self.is_authenticated:
            self.logger.error("Cannot send message - not authenticated")
            return
        
        try:
            self.ws.send(json.dumps(message))
            self.logger.debug(f"Sent message: {message}")
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")
    
    def close(self):
        """Close WebSocket connection"""
        self.logger.info("Closing WebSocket connection")
        self._should_run = False
        
        # Close WebSocket if exists
        if self.ws:
            try:
                self.ws.close()
            except Exception as e:
                self.logger.debug(f"Error closing WebSocket: {e}")
        
        # Wait for threads to finish
        if self._ws_thread and self._ws_thread.is_alive():
            self._ws_thread.join(timeout=5)
        
        if self._reconnect_thread and self._reconnect_thread.is_alive():
            self._reconnect_thread.join(timeout=5)
        
        self.state = ConnectionState.DISCONNECTED
        self.logger.info("WebSocket manager closed")
    
    def is_alive(self) -> bool:
        """Check if connection is alive"""
        return self.is_connected and self.is_authenticated
    
    def subscribe_to_symbol(self, symbol: str):
        """Subscribe to a specific symbol
        
        Args:
            symbol: The symbol to subscribe to (e.g., "XAUUSD")
        """
        if not self.is_authenticated:
            self.logger.error("Cannot subscribe - not authenticated")
            return
        
        # Track subscription
        with self._symbols_lock:
            self.subscribed_symbols.add(symbol)
        
        subscribe_message = {
            "userKey": self.config.api_key,
            "symbol": symbol
        }
        
        try:
            self.ws.send(json.dumps(subscribe_message))
            self.logger.info(f"Subscription request sent for {symbol}")
        except Exception as e:
            self.error_handler.handle_error(e, f"Subscribe to {symbol}")
            with self._symbols_lock:
                self.subscribed_symbols.discard(symbol)
    
    def _process_price_data(self, data: dict):
        """Process incoming price data
        
        Args:
            data: Price data dictionary
        """
        try:
            symbol = data.get("symbol")
            bid = data.get("bid")
            ask = data.get("ask")
            timestamp = data.get("ts", data.get("timestamp"))
            
            # Convert timestamp if it's a string or in milliseconds
            if timestamp:
                try:
                    timestamp = float(timestamp)
                    if timestamp > 1e10:
                        timestamp = timestamp / 1000
                except (ValueError, TypeError):
                    timestamp = None
            
            # Create formatted timestamp
            if timestamp:
                dt = datetime.fromtimestamp(timestamp)
                formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                formatted_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Log price data
            self.logger.info(
                f"Price data - {symbol}: "
                f"Bid: {bid}, Ask: {ask}, Time: {formatted_time}"
            )
            
            # Call price data callback if set
            if self.on_price_data:
                price_info = {
                    "symbol": symbol,
                    "bid": bid,
                    "ask": ask,
                    "timestamp": timestamp or time.time(),
                    "formatted_time": formatted_time
                }
                self.on_price_data(price_info)
                
        except Exception as e:
            self.error_handler.handle_error(e, "Price data processing", ErrorType.DATA_ERROR)