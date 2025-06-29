"""
Unit tests for Forex Persistence Service (US-014)
"""
import pytest
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import Mock, patch
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.services.data_persistence.forex_persistence_service import ForexPersistenceService
from src.models.forex import ForexRate, ForexRateArchive


class TestForexPersistenceService:
    """Test cases for forex persistence service"""
    
    @pytest.fixture
    def mock_db_session(self):
        """Mock database session"""
        return Mock(spec=Session)
    
    @pytest.fixture
    def service(self, mock_db_session):
        """Create service instance with mock database"""
        return ForexPersistenceService(mock_db_session)
    
    @pytest.fixture
    def sample_forex_rate(self):
        """Sample forex rate for testing"""
        return ForexRate(
            id=1,
            symbol="XAUUSD",
            bid=Decimal("2034.50"),
            ask=Decimal("2034.80"),
            timestamp=datetime(2024, 6, 29, 10, 30, 0),
            created_at=datetime(2024, 6, 29, 10, 30, 1)
        )
    
    @pytest.mark.asyncio
    async def test_save_forex_rate_success(self, service, mock_db_session):
        """Test successful forex rate saving"""
        # Mock successful database operations
        mock_db_session.commit.return_value = None
        mock_db_session.refresh.return_value = None
        
        # Test data
        symbol = "XAUUSD"
        bid = 2034.50
        ask = 2034.80
        timestamp = datetime(2024, 6, 29, 10, 30, 0)
        
        # Call service method
        result = await service.save_forex_rate(symbol, bid, ask, timestamp)
        
        # Assertions
        assert result is not None
        assert isinstance(result, ForexRate)
        assert result.symbol == symbol
        assert result.bid == Decimal("2034.50")
        assert result.ask == Decimal("2034.80")
        assert result.timestamp == timestamp
        
        # Verify database calls
        mock_db_session.add.assert_called_once()
        mock_db_session.commit.assert_called_once()
        mock_db_session.refresh.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_save_forex_rate_duplicate(self, service, mock_db_session):
        """Test handling of duplicate forex rate"""
        # Mock IntegrityError for duplicate
        mock_db_session.commit.side_effect = IntegrityError("", "", "")
        mock_db_session.rollback.return_value = None
        
        # Test data
        symbol = "XAUUSD"
        bid = 2034.50
        ask = 2034.80
        timestamp = datetime(2024, 6, 29, 10, 30, 0)
        
        # Call service method
        result = await service.save_forex_rate(symbol, bid, ask, timestamp)
        
        # Should return None for duplicate
        assert result is None
        
        # Verify rollback was called
        mock_db_session.rollback.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_bulk_save_forex_rates(self, service, mock_db_session):
        """Test bulk saving of forex rates"""
        # Mock database responses - IntegrityError only on the second call (duplicate)
        commit_calls = [0]
        
        def mock_commit():
            commit_calls[0] += 1
            if commit_calls[0] == 2:  # Second commit call raises IntegrityError
                raise IntegrityError("", "", "")
        
        mock_db_session.commit.side_effect = mock_commit
        mock_db_session.rollback.return_value = None
        mock_db_session.refresh.return_value = None
        
        # Test data
        forex_data = [
            {
                "symbol": "XAUUSD",
                "bid": 2034.50,
                "ask": 2034.80,
                "timestamp": datetime(2024, 6, 29, 10, 30, 0)
            },
            {
                "symbol": "XAUUSD",
                "bid": 2034.50,
                "ask": 2034.80,
                "timestamp": datetime(2024, 6, 29, 10, 30, 0)  # Duplicate
            },
            {
                "symbol": "EURUSD",
                "bid": 1.0735,
                "ask": 1.0737,
                "timestamp": datetime(2024, 6, 29, 10, 30, 1)
            }
        ]
        
        # Call service method
        stats = await service.bulk_save_forex_rates(forex_data)
        
        # Verify statistics
        assert stats['saved'] == 2  # First and third records
        assert stats['duplicates'] == 1  # Second record
        assert stats['errors'] == 0
    
    @pytest.mark.asyncio
    async def test_get_historical_data(self, service, mock_db_session, sample_forex_rate):
        """Test historical data retrieval"""
        # Mock query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_forex_rate]
        mock_db_session.query.return_value = mock_query
        
        # Test parameters
        symbol = "XAUUSD"
        start_time = datetime(2024, 6, 29, 10, 0, 0)
        end_time = datetime(2024, 6, 29, 11, 0, 0)
        limit = 1000
        
        # Call service method
        result = await service.get_historical_data(symbol, start_time, end_time, limit)
        
        # Assertions
        assert len(result) == 1
        assert result[0] == sample_forex_rate
        
        # Verify query was built correctly
        mock_db_session.query.assert_called_once_with(ForexRate)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
        mock_query.limit.assert_called_once_with(limit)
    
    @pytest.mark.asyncio
    async def test_get_latest_rate(self, service, mock_db_session, sample_forex_rate):
        """Test getting latest rate for symbol"""
        # Mock query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.first.return_value = sample_forex_rate
        mock_db_session.query.return_value = mock_query
        
        # Test parameters
        symbol = "XAUUSD"
        
        # Call service method
        result = await service.get_latest_rate(symbol)
        
        # Assertions
        assert result == sample_forex_rate
        
        # Verify query
        mock_db_session.query.assert_called_once_with(ForexRate)
        mock_query.filter.assert_called_once()
        mock_query.order_by.assert_called_once()
        mock_query.first.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_rates_by_criteria(self, service, mock_db_session, sample_forex_rate):
        """Test advanced search functionality"""
        # Mock query result
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.order_by.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [sample_forex_rate]
        mock_db_session.query.return_value = mock_query
        
        # Test parameters
        symbol = "XAUUSD"
        min_spread = 0.1
        max_spread = 1.0
        start_time = datetime(2024, 6, 29, 10, 0, 0)
        end_time = datetime(2024, 6, 29, 11, 0, 0)
        limit = 100
        
        # Call service method
        result = await service.search_rates_by_criteria(
            symbol=symbol,
            min_spread=min_spread,
            max_spread=max_spread,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        # Assertions
        assert len(result) == 1
        assert result[0] == sample_forex_rate
        
        # Verify query building
        mock_db_session.query.assert_called_once_with(ForexRate)
        # Should have multiple filter calls for different criteria
        assert mock_query.filter.call_count >= 4  # symbol, start_time, end_time, spreads
    
    @pytest.mark.asyncio
    async def test_get_data_statistics(self, service, mock_db_session):
        """Test data statistics generation"""
        # Mock query results
        mock_query = Mock()
        mock_query.count.return_value = 1000
        mock_query.with_entities.return_value = mock_query
        mock_query.scalar.return_value = datetime(2024, 6, 29, 10, 0, 0)
        mock_db_session.query.return_value = mock_query
        
        # Mock symbols query
        mock_symbols_query = Mock()
        mock_symbols_query.distinct.return_value = mock_symbols_query
        mock_symbols_query.all.return_value = [("XAUUSD",), ("EURUSD",)]
        
        
        # Set up individual query mocks that will be returned for each call to query()
        mock_count_query = Mock()
        mock_count_query.count.return_value = 1000
        
        mock_symbol_col_query = Mock()
        mock_symbol_col_query.distinct.return_value = mock_symbols_query
        
        mock_min_query = Mock()
        mock_min_query.with_entities.return_value = mock_min_query
        mock_min_query.scalar.return_value = datetime(2024, 6, 29, 10, 0, 0)
        
        mock_max_query = Mock()
        mock_max_query.with_entities.return_value = mock_max_query
        mock_max_query.scalar.return_value = datetime(2024, 6, 29, 11, 0, 0)
        
        # Set up the query for latest created_at
        mock_latest_created_query = Mock()
        mock_latest_created_query.order_by.return_value = mock_latest_created_query
        mock_latest_created_query.first.return_value = (datetime(2024, 6, 29, 10, 30, 0),)
        
        mock_db_session.query.side_effect = [
            mock_count_query,       # query(ForexRate) for count
            mock_symbol_col_query,  # query(ForexRate.symbol) for distinct
            mock_min_query,         # query(ForexRate) for min date
            mock_max_query,         # query(ForexRate) for max date
            mock_latest_created_query # query(ForexRate.created_at) for latest update
        ]
        
        # Call service method
        result = await service.get_data_statistics()
        
        # Assertions
        assert result['total_records'] == 1000
        assert result['symbols'] == ["XAUUSD", "EURUSD"]
        assert result['symbols_count'] == 2
        assert 'date_range' in result
        assert 'latest_update' in result
    
    @pytest.mark.asyncio
    async def test_archive_old_data(self, service, mock_db_session):
        """Test data archival functionality"""
        # Mock old records
        old_record = ForexRate(
            id=1,
            symbol="XAUUSD",
            bid=Decimal("2000.00"),
            ask=Decimal("2000.30"),
            timestamp=datetime.now() - timedelta(days=100),
            created_at=datetime.now() - timedelta(days=100)
        )
        
        # Mock query results
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.count.return_value = 1
        mock_query.offset.return_value = mock_query
        mock_query.limit.return_value = mock_query
        mock_query.all.return_value = [old_record]
        mock_db_session.query.return_value = mock_query
        
        # Mock database operations
        mock_db_session.bulk_save_objects.return_value = None
        mock_db_session.delete.return_value = None
        mock_db_session.commit.return_value = None
        
        # Call service method
        result = await service.archive_old_data(days_old=90, batch_size=1000)
        
        # Assertions
        assert result['archived'] == 1
        assert result['total_found'] == 1
        assert 'cutoff_date' in result
        
        # Verify database operations
        mock_db_session.bulk_save_objects.assert_called_once()
        mock_db_session.delete.assert_called_once_with(old_record)
        mock_db_session.commit.assert_called()
    
    @pytest.mark.asyncio
    async def test_cleanup_old_archives(self, service, mock_db_session):
        """Test archive cleanup functionality"""
        # Mock query for deletion
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        mock_query.delete.return_value = 5  # 5 records deleted
        mock_db_session.query.return_value = mock_query
        
        # Mock commit
        mock_db_session.commit.return_value = None
        
        # Call service method
        result = await service.cleanup_old_archives(days_old=365)
        
        # Assertions
        assert result == 5
        
        # Verify database operations
        mock_db_session.query.assert_called_once_with(ForexRateArchive)
        mock_query.delete.assert_called_once()
        mock_db_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_validate_data_integrity(self, service, mock_db_session):
        """Test data integrity validation"""
        # Mock query results for different integrity checks
        mock_query = Mock()
        mock_query.filter.return_value = mock_query
        
        # Set up count responses for different integrity checks
        count_responses = [2, 1, 0, 3]  # negative spreads, future timestamps, zero prices, large spreads
        mock_query.count.side_effect = count_responses
        
        mock_db_session.query.return_value = mock_query
        
        # Call service method
        result = await service.validate_data_integrity()
        
        # Assertions
        assert result['total_issues'] == 3  # Only non-zero counts create issues
        assert len(result['issues']) == 3
        assert 'validated_at' in result
        
        # Check specific issue messages
        issues = result['issues']
        assert any("negative spreads" in issue for issue in issues)
        assert any("future timestamps" in issue for issue in issues)
        assert any("large spreads" in issue for issue in issues)
        # Zero prices should not appear since count was 0
        assert not any("zero or negative prices" in issue for issue in issues)
    
    @pytest.mark.asyncio
    async def test_error_handling(self, service, mock_db_session):
        """Test error handling in service methods"""
        # Mock database error
        mock_db_session.query.side_effect = Exception("Database connection error")
        
        # Test that errors are properly raised
        with pytest.raises(Exception) as exc_info:
            await service.get_latest_rate("XAUUSD")
        
        assert "Database connection error" in str(exc_info.value)
    
    def test_forex_rate_model_properties(self, sample_forex_rate):
        """Test ForexRate model properties and methods"""
        # Test spread calculation
        expected_spread = sample_forex_rate.ask - sample_forex_rate.bid
        assert sample_forex_rate.spread == expected_spread
        
        # Test mid price calculation
        expected_mid = (sample_forex_rate.bid + sample_forex_rate.ask) / 2
        assert sample_forex_rate.mid_price == expected_mid
        
        # Test to_dict conversion
        rate_dict = sample_forex_rate.to_dict()
        assert rate_dict['symbol'] == "XAUUSD"
        assert rate_dict['bid'] == 2034.50
        assert rate_dict['ask'] == 2034.80
        assert 'spread' in rate_dict
        assert 'mid_price' in rate_dict
        assert 'timestamp' in rate_dict
        assert 'created_at' in rate_dict
    
    def test_forex_rate_model_repr(self, sample_forex_rate):
        """Test ForexRate model string representation"""
        repr_str = repr(sample_forex_rate)
        assert "ForexRate" in repr_str
        assert "XAUUSD" in repr_str
        assert "2034.50" in repr_str
        assert "2034.80" in repr_str