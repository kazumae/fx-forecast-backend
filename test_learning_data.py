"""Test script for learning data service"""
import asyncio
import os
import sys
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Set the working directory to backend
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.learning_data_service import LearningDataService
from app.models.forecast import ForecastRequest


async def test_learning_data_service():
    """Test the learning data service functionality"""
    
    print("=== Learning Data Service Test ===\n")
    
    db: Session = SessionLocal()
    
    try:
        # Initialize service
        learning_service = LearningDataService(db)
        
        # Test 1: Get pattern success summary
        print("Test 1: Pattern Success Summary")
        print("-" * 40)
        summary = learning_service.get_pattern_success_summary()
        print(summary)
        print()
        
        # Test 2: Extract metadata from a recent forecast
        print("Test 2: Extract Metadata from Recent Forecast")
        print("-" * 40)
        
        # Get a recent forecast
        recent_forecast = db.query(ForecastRequest).order_by(
            ForecastRequest.created_at.desc()
        ).first()
        
        if recent_forecast:
            print(f"Forecast ID: {recent_forecast.id}")
            print(f"Currency Pair: {recent_forecast.currency_pair}")
            print(f"Timeframes: {recent_forecast.timeframes}")
            
            # Extract metadata
            metadata = await learning_service.extract_pattern_metadata(recent_forecast)
            print(f"\nExtracted Metadata:")
            for key, value in metadata.items():
                if key not in ["forecast_id", "created_at"]:
                    print(f"  {key}: {value}")
        else:
            print("No forecasts found in database")
        print()
        
        # Test 3: Compile learning data
        print("Test 3: Compile Learning Data (Last 7 Days)")
        print("-" * 40)
        
        compiled_data = await learning_service.compile_learning_data(days_back=7)
        
        print(f"Compilation Period: {compiled_data.get('period')}")
        print(f"Total Patterns Analyzed: {len(compiled_data.get('successful_patterns', [])) + len(compiled_data.get('failed_patterns', []))}")
        
        # Show pattern success rates
        print("\nPattern Success Rates:")
        for pattern, stats in compiled_data.get("pattern_success_rates", {}).items():
            if stats.get("total", 0) > 0:
                success_rate = stats.get("success_rate", 0) * 100
                print(f"  {pattern}: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
        
        # Show best practices
        if compiled_data.get("best_practices"):
            print(f"\nTop Best Practices:")
            for i, practice in enumerate(compiled_data["best_practices"][:3], 1):
                print(f"  {i}. {practice}")
        
        # Show common mistakes
        if compiled_data.get("common_mistakes"):
            print(f"\nTop Common Mistakes:")
            for i, mistake in enumerate(compiled_data["common_mistakes"][:3], 1):
                print(f"  {i}. {mistake}")
        
        # Test 4: Save learning data
        print("\n\nTest 4: Save Learning Data to File")
        print("-" * 40)
        
        filepath = await learning_service.save_learning_data(
            compiled_data, 
            filename="test_learning_data.txt"
        )
        
        print(f"Data saved to: {filepath}")
        
        # Check if file exists
        if os.path.exists(filepath):
            file_size = os.path.getsize(filepath)
            print(f"File size: {file_size} bytes")
            
            # Read first few lines
            with open(filepath, 'r', encoding='utf-8') as f:
                lines = f.readlines()[:10]
                print(f"\nFirst 10 lines of saved file:")
                for line in lines:
                    print(f"  {line.rstrip()}")
        
        # Test 5: Load recent learning data
        print("\n\nTest 5: Load Recent Learning Data")
        print("-" * 40)
        
        recent_data = learning_service.load_recent_learning_data(days=7)
        print(f"Found {len(recent_data)} recent learning data files")
        
        if recent_data:
            for i, data in enumerate(recent_data, 1):
                print(f"\nFile {i}:")
                print(f"  Compilation Date: {data.get('compilation_date')}")
                print(f"  Period: {data.get('period')}")
                print(f"  Patterns Analyzed: {len(data.get('pattern_success_rates', {}))}")
        
        print("\n=== Test Complete ===")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(test_learning_data_service())