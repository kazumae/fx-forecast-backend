"""
Forex Data Persistence Service for US-014

Handles automatic saving of received pricing data to database
with deduplication, archival, and search capabilities.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from sqlalchemy import and_, desc, func, text
import logging

from src.models.forex import ForexRate, ForexRateArchive


logger = logging.getLogger(__name__)


class ForexPersistenceService:
    """Service for persisting forex data with US-014 requirements"""
    
    def __init__(self, db: Session = None):
        """Initialize with database session"""
        self.db = db
    
    async def save_forex_rate(
        self, 
        symbol: str, 
        bid: float, 
        ask: float, 
        timestamp: datetime
    ) -> Optional[ForexRate]:
        """
        Save forex rate data with automatic deduplication
        Returns None if duplicate data (already exists)
        """
        try:
            # Convert to appropriate types
            bid_decimal = Decimal(str(bid))
            ask_decimal = Decimal(str(ask))
            
            # Create new forex rate record
            forex_rate = ForexRate(
                symbol=symbol,
                bid=bid_decimal,
                ask=ask_decimal,
                timestamp=timestamp
            )
            
            # Add to session
            self.db.add(forex_rate)
            self.db.commit()
            self.db.refresh(forex_rate)
            
            logger.debug(f"Saved forex rate: {symbol} {bid}/{ask} at {timestamp}")
            return forex_rate
            
        except IntegrityError as e:
            # Duplicate entry - rollback and return None
            self.db.rollback()
            logger.debug(f"Duplicate forex rate ignored: {symbol} at {timestamp}")
            return None
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error saving forex rate: {str(e)}")
            raise
    
    async def bulk_save_forex_rates(
        self, 
        forex_data: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """
        Bulk save multiple forex rates
        Returns statistics: {'saved': count, 'duplicates': count, 'errors': count}
        """
        stats = {'saved': 0, 'duplicates': 0, 'errors': 0}
        
        for data in forex_data:
            try:
                result = await self.save_forex_rate(
                    symbol=data['symbol'],
                    bid=data['bid'],
                    ask=data['ask'],
                    timestamp=data['timestamp']
                )
                
                if result:
                    stats['saved'] += 1
                else:
                    stats['duplicates'] += 1
                    
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"Error in bulk save: {str(e)}")
        
        logger.info(f"Bulk save completed: {stats}")
        return stats
    
    async def get_historical_data(
        self,
        symbol: str,
        start_time: datetime,
        end_time: datetime,
        limit: int = 1000
    ) -> List[ForexRate]:
        """
        Retrieve historical forex data for given symbol and time range
        """
        try:
            query = self.db.query(ForexRate).filter(
                and_(
                    ForexRate.symbol == symbol,
                    ForexRate.timestamp >= start_time,
                    ForexRate.timestamp <= end_time
                )
            ).order_by(desc(ForexRate.timestamp)).limit(limit)
            
            return query.all()
            
        except Exception as e:
            logger.error(f"Error retrieving historical data: {str(e)}")
            raise
    
    async def get_latest_rate(self, symbol: str) -> Optional[ForexRate]:
        """Get the most recent rate for a symbol"""
        try:
            return self.db.query(ForexRate).filter(
                ForexRate.symbol == symbol
            ).order_by(desc(ForexRate.timestamp)).first()
            
        except Exception as e:
            logger.error(f"Error getting latest rate: {str(e)}")
            raise
    
    async def search_rates_by_criteria(
        self,
        symbol: Optional[str] = None,
        min_spread: Optional[float] = None,
        max_spread: Optional[float] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[ForexRate]:
        """
        Advanced search for forex rates with multiple criteria
        """
        try:
            query = self.db.query(ForexRate)
            
            # Apply filters
            if symbol:
                query = query.filter(ForexRate.symbol == symbol)
            
            if start_time:
                query = query.filter(ForexRate.timestamp >= start_time)
            
            if end_time:
                query = query.filter(ForexRate.timestamp <= end_time)
            
            # Spread filtering requires calculated field
            if min_spread is not None or max_spread is not None:
                if min_spread is not None:
                    query = query.filter((ForexRate.ask - ForexRate.bid) >= min_spread)
                if max_spread is not None:
                    query = query.filter((ForexRate.ask - ForexRate.bid) <= max_spread)
            
            return query.order_by(desc(ForexRate.timestamp)).limit(limit).all()
            
        except Exception as e:
            logger.error(f"Error in search_rates_by_criteria: {str(e)}")
            raise
    
    async def get_data_statistics(self, symbol: Optional[str] = None) -> Dict[str, Any]:
        """
        Get statistics about stored forex data
        """
        try:
            query = self.db.query(ForexRate)
            
            if symbol:
                query = query.filter(ForexRate.symbol == symbol)
            
            # Basic counts
            total_records = query.count()
            
            if total_records == 0:
                return {
                    'total_records': 0,
                    'symbols': [],
                    'date_range': None,
                    'latest_update': None
                }
            
            # Get symbols
            symbols_query = self.db.query(ForexRate.symbol).distinct()
            if symbol:
                symbols = [symbol]
            else:
                symbols = [row[0] for row in symbols_query.all()]
            
            # Date range
            min_date = query.with_entities(func.min(ForexRate.timestamp)).scalar()
            max_date = query.with_entities(func.max(ForexRate.timestamp)).scalar()
            
            # Latest update
            latest_update = self.db.query(ForexRate.created_at).order_by(
                desc(ForexRate.created_at)
            ).first()
            
            return {
                'total_records': total_records,
                'symbols': symbols,
                'date_range': {
                    'start': min_date.isoformat() if min_date else None,
                    'end': max_date.isoformat() if max_date else None
                },
                'latest_update': latest_update[0].isoformat() if latest_update else None,
                'symbols_count': len(symbols)
            }
            
        except Exception as e:
            logger.error(f"Error getting data statistics: {str(e)}")
            raise
    
    async def archive_old_data(
        self, 
        days_old: int = 90,
        batch_size: int = 1000
    ) -> Dict[str, int]:
        """
        Archive data older than specified days
        Returns statistics about archived records
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            # Find records to archive
            old_records_query = self.db.query(ForexRate).filter(
                ForexRate.timestamp < cutoff_date
            )
            
            total_to_archive = old_records_query.count()
            archived_count = 0
            
            if total_to_archive == 0:
                return {'archived': 0, 'total_found': 0}
            
            logger.info(f"Starting archival of {total_to_archive} records older than {cutoff_date}")
            
            # Process in batches
            offset = 0
            while offset < total_to_archive:
                batch = old_records_query.offset(offset).limit(batch_size).all()
                
                if not batch:
                    break
                
                # Create archive records
                archive_records = []
                for record in batch:
                    archive_record = ForexRateArchive(
                        id=record.id,
                        symbol=record.symbol,
                        bid=record.bid,
                        ask=record.ask,
                        timestamp=record.timestamp,
                        created_at=record.created_at
                    )
                    archive_records.append(archive_record)
                
                # Add to archive table
                self.db.bulk_save_objects(archive_records)
                
                # Delete from main table
                for record in batch:
                    self.db.delete(record)
                
                self.db.commit()
                archived_count += len(batch)
                offset += batch_size
                
                logger.info(f"Archived batch: {archived_count}/{total_to_archive}")
            
            logger.info(f"Archival completed: {archived_count} records archived")
            
            return {
                'archived': archived_count,
                'total_found': total_to_archive,
                'cutoff_date': cutoff_date.isoformat()
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during archival: {str(e)}")
            raise
    
    async def cleanup_old_archives(self, days_old: int = 365) -> int:
        """
        Delete archived data older than specified days
        Returns count of deleted records
        """
        try:
            cutoff_date = datetime.utcnow() - timedelta(days=days_old)
            
            deleted_count = self.db.query(ForexRateArchive).filter(
                ForexRateArchive.archived_at < cutoff_date
            ).delete()
            
            self.db.commit()
            
            logger.info(f"Cleaned up {deleted_count} archived records older than {cutoff_date}")
            return deleted_count
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error during archive cleanup: {str(e)}")
            raise
    
    async def validate_data_integrity(self) -> Dict[str, Any]:
        """
        Validate data integrity and return report
        """
        try:
            issues = []
            
            # Check for negative spreads
            negative_spreads = self.db.query(ForexRate).filter(
                ForexRate.ask < ForexRate.bid
            ).count()
            
            if negative_spreads > 0:
                issues.append(f"Found {negative_spreads} records with negative spreads")
            
            # Check for future timestamps
            future_timestamps = self.db.query(ForexRate).filter(
                ForexRate.timestamp > datetime.utcnow()
            ).count()
            
            if future_timestamps > 0:
                issues.append(f"Found {future_timestamps} records with future timestamps")
            
            # Check for zero prices
            zero_prices = self.db.query(ForexRate).filter(
                (ForexRate.bid <= 0) | (ForexRate.ask <= 0)
            ).count()
            
            if zero_prices > 0:
                issues.append(f"Found {zero_prices} records with zero or negative prices")
            
            # Check for extremely large spreads (> 1000 pips)
            large_spreads = self.db.query(ForexRate).filter(
                (ForexRate.ask - ForexRate.bid) > 0.1000  # Assuming 4-digit precision
            ).count()
            
            if large_spreads > 0:
                issues.append(f"Found {large_spreads} records with unusually large spreads")
            
            return {
                'total_issues': len(issues),
                'issues': issues,
                'validated_at': datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Error during data validation: {str(e)}")
            raise