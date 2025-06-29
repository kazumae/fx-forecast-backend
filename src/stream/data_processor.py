"""
Data Processor for TraderMade Stream Display
"""
import logging
from datetime import datetime
from typing import Optional


class DataProcessor:
    """Process and display price data to console"""
    
    def __init__(self):
        """Initialize data processor"""
        self.logger = logging.getLogger(__name__)
        self.last_price = {}  # Store last price for each symbol
        
    def process_price_data(self, data: dict):
        """Process price data and display to console
        
        Args:
            data: Price data dictionary with symbol, bid, ask, timestamp
        """
        symbol = data.get("symbol")
        bid = data.get("bid")
        ask = data.get("ask")
        timestamp = data.get("timestamp")
        
        # Validate data
        if not all([symbol, bid is not None, ask is not None, timestamp]):
            self.logger.warning("Incomplete price data received")
            return
            
        try:
            # Ensure bid and ask are floats
            bid = float(bid)
            ask = float(ask)
            
            # Calculate spread
            spread = ask - bid
            
            # Format timestamp
            dt = datetime.fromtimestamp(timestamp)
            formatted_time = dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]  # Remove last 3 digits from microseconds
            
            # Determine decimal places based on symbol
            if symbol in ["XAUUSD", "XAGUSD"]:  # Precious metals
                decimal_places = 2
            elif "JPY" in symbol:  # JPY pairs typically have 2 decimal places
                decimal_places = 2
            elif symbol == "BTCUSD":  # Crypto can have more variation
                decimal_places = 4
            else:  # Most forex pairs have 4 decimal places
                decimal_places = 4
            
            # Format output
            output = (
                f"[{formatted_time}] {symbol} - "
                f"Bid: {bid:.{decimal_places}f}, "
                f"Ask: {ask:.{decimal_places}f}, "
                f"Spread: {spread:.{decimal_places}f}"
            )
            
            # Check for price movement
            if symbol in self.last_price:
                last_bid = self.last_price[symbol]["bid"]
                if bid > last_bid:
                    output += " ↑"
                elif bid < last_bid:
                    output += " ↓"
                else:
                    output += " →"
            
            # Store current price
            self.last_price[symbol] = {"bid": bid, "ask": ask}
            
            # Display to console
            print(output)
            
            # Log for debugging
            self.logger.debug(f"Displayed: {output}")
            
        except Exception as e:
            self.logger.error(f"Error processing price data: {e}", exc_info=True)
    
    def display_summary(self):
        """Display summary of current prices"""
        if not self.last_price:
            print("\nNo price data received yet.")
            return
            
        print("\n" + "=" * 70)
        print("Current Price Summary")
        print("=" * 70)
        
        for symbol, prices in self.last_price.items():
            spread = prices["ask"] - prices["bid"]
            print(f"{symbol:10} Bid: {prices['bid']:12.4f}  Ask: {prices['ask']:12.4f}  Spread: {spread:8.4f}")
        
        print("=" * 70)