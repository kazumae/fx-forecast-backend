"""
Data Processor with Database Storage for TraderMade Stream
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, Optional, List
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
import redis
import json
import os

from src.models.forex import ForexRate
from src.core.config import settings


class DataProcessorDB:
    """Process and store price data to database"""
    
    def __init__(self):
        """Initialize data processor with database connection"""
        self.logger = logging.getLogger(__name__)
        
        # Database setup
        self.engine = create_engine(settings.DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        
        # Redis setup
        try:
            self.redis_client = redis.from_url(
                os.getenv("REDIS_URL", "redis://redis:6379"),
                decode_responses=True
            )
            self.redis_client.ping()
            self.redis_enabled = True
            self.logger.info("Redis connection established")
        except Exception as e:
            self.logger.warning(f"Redis connection failed: {e}. Running without cache.")
            self.redis_client = None
            self.redis_enabled = False
        
        # Buffer for batch processing
        self.data_buffer = []
        self.buffer_size = 10
        self.last_flush_time = datetime.utcnow()
        self.flush_interval = 1  # seconds
        
    def process_price_data(self, data: dict):
        """Process price data and store to database
        
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
            
            # Calculate mid price
            mid_price = (bid + ask) / 2
            
            # Convert timestamp to datetime if it's a Unix timestamp
            if isinstance(timestamp, (int, float)):
                timestamp = datetime.utcfromtimestamp(timestamp)
            elif not isinstance(timestamp, datetime):
                # If it's a string, try to parse it
                try:
                    timestamp = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                except:
                    self.logger.warning(f"Could not parse timestamp: {timestamp}")
                    timestamp = datetime.utcnow()
            
            # Prepare data for storage
            price_data = {
                "currency_pair": symbol,
                "bid": bid,
                "ask": ask,
                "rate": mid_price,
                "timestamp": timestamp,
                "created_at": datetime.utcnow()
            }
            
            # Add to buffer
            self.data_buffer.append(price_data)
            
            # Update Redis cache (latest tick)
            if self.redis_enabled:
                self._update_redis_cache(price_data)
            
            # Check if we should flush
            if self._should_flush():
                self._flush_to_database()
                
        except Exception as e:
            self.logger.error(f"Error processing price data: {e}")
            
    def _update_redis_cache(self, price_data: dict):
        """Update Redis cache with latest tick data"""
        try:
            symbol = price_data["currency_pair"]
            
            # Store latest tick as hash
            key = f"tick:{symbol}:latest"
            self.redis_client.hset(key, mapping={
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "rate": price_data["rate"],
                "timestamp": price_data["timestamp"].isoformat() if isinstance(price_data["timestamp"], datetime) else str(price_data["timestamp"]),
                "updated_at": datetime.utcnow().isoformat()
            })
            
            # Set TTL of 24 hours
            self.redis_client.expire(key, 86400)
            
            # Store in history list (keep last 100 ticks)
            history_key = f"tick:{symbol}:history"
            tick_json = json.dumps({
                "bid": price_data["bid"],
                "ask": price_data["ask"],
                "rate": price_data["rate"],
                "timestamp": price_data["timestamp"].isoformat() if isinstance(price_data["timestamp"], datetime) else str(price_data["timestamp"])
            })
            
            self.redis_client.lpush(history_key, tick_json)
            self.redis_client.ltrim(history_key, 0, 99)  # Keep only last 100
            self.redis_client.expire(history_key, 86400)
            
        except Exception as e:
            self.logger.error(f"Error updating Redis cache: {e}")
            
    def _should_flush(self) -> bool:
        """Check if buffer should be flushed"""
        # Flush if buffer is full
        if len(self.data_buffer) >= self.buffer_size:
            return True
            
        # Flush if time interval has passed
        if (datetime.utcnow() - self.last_flush_time).total_seconds() >= self.flush_interval:
            return True
            
        return False
        
    def _flush_to_database(self):
        """Flush buffer to database"""
        if not self.data_buffer:
            return
            
        db: Session = self.SessionLocal()
        try:
            for data in self.data_buffer:
                # Create ForexRate object
                forex_rate = ForexRate(
                    currency_pair=data["currency_pair"],
                    bid=data["bid"],
                    ask=data["ask"],
                    rate=data["rate"],
                    timestamp=data["timestamp"],
                    created_at=data["created_at"]
                )
                
                # Use merge for upsert behavior
                db.merge(forex_rate)
            
            # Commit all changes
            db.commit()
            
            self.logger.debug(f"Flushed {len(self.data_buffer)} records to database")
            
            # Clear buffer
            self.data_buffer.clear()
            self.last_flush_time = datetime.utcnow()
            
        except SQLAlchemyError as e:
            self.logger.error(f"Database error: {e}")
            db.rollback()
        except Exception as e:
            self.logger.error(f"Unexpected error: {e}")
            db.rollback()
        finally:
            db.close()
            
    def close(self):
        """Clean up resources"""
        # Flush any remaining data
        if self.data_buffer:
            self._flush_to_database()
            
        # Close connections
        if self.redis_client:
            self.redis_client.close()