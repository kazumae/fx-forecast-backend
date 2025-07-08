#!/usr/bin/env python3
"""
Script to compile and save learning data from forecasts, reviews, and comments
This can be run periodically (e.g., daily via cron) to accumulate learning data
"""

import sys
import os
import asyncio
from datetime import datetime

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm import Session
from app.db.session import SessionLocal
from app.services.learning_data_service import LearningDataService


async def compile_and_save_learning_data(days_back: int = 30):
    """Compile learning data from the last N days and save to file"""
    
    db: Session = SessionLocal()
    
    try:
        print(f"Starting learning data compilation for the last {days_back} days...")
        
        # Initialize service
        learning_service = LearningDataService(db)
        
        # Compile data
        print("Compiling data from forecasts, reviews, and comments...")
        compiled_data = await learning_service.compile_learning_data(days_back=days_back)
        
        # Save to file
        print("Saving compiled data...")
        filepath = await learning_service.save_learning_data(compiled_data)
        
        print(f"Learning data saved to: {filepath}")
        
        # Print summary statistics
        total_patterns = sum(
            stats.get("total", 0) 
            for stats in compiled_data.get("pattern_success_rates", {}).values()
        )
        
        print(f"\nSummary:")
        print(f"- Total patterns analyzed: {total_patterns}")
        print(f"- Successful patterns: {len(compiled_data.get('successful_patterns', []))}")
        print(f"- Failed patterns: {len(compiled_data.get('failed_patterns', []))}")
        print(f"- Comment insights: {len(compiled_data.get('comment_insights', []))}")
        print(f"- Trade reviews: {len(compiled_data.get('trade_execution_insights', []))}")
        
        # Print pattern success rates
        print("\nPattern Success Rates:")
        for pattern, stats in compiled_data.get("pattern_success_rates", {}).items():
            if stats.get("total", 0) > 0:
                success_rate = stats.get("success_rate", 0) * 100
                print(f"  {pattern}: {success_rate:.1f}% ({stats['success']}/{stats['total']})")
        
        return filepath
        
    except Exception as e:
        print(f"Error compiling learning data: {e}")
        raise
    finally:
        db.close()


async def generate_daily_report():
    """Generate a daily learning report"""
    
    db: Session = SessionLocal()
    
    try:
        learning_service = LearningDataService(db)
        
        # Get pattern success summary
        summary = learning_service.get_pattern_success_summary()
        
        # Save daily report
        timestamp = datetime.now().strftime("%Y%m%d")
        report_path = learning_service.data_dir / f"daily_report_{timestamp}.txt"
        
        with open(report_path, 'w', encoding='utf-8') as f:
            f.write(f"FX予測システム 日次学習レポート\n")
            f.write(f"生成日時: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 80 + "\n\n")
            f.write(summary)
            f.write("\n\n" + "=" * 80 + "\n")
            f.write("このレポートは過去30日間の蓄積データから生成されています。\n")
        
        print(f"Daily report saved to: {report_path}")
        
    finally:
        db.close()


async def main():
    """Main function"""
    
    # Parse command line arguments
    if len(sys.argv) > 1:
        if sys.argv[1] == "--daily-report":
            await generate_daily_report()
        elif sys.argv[1] == "--days":
            days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
            await compile_and_save_learning_data(days_back=days)
        else:
            print("Usage:")
            print("  python compile_learning_data.py           # Compile last 30 days")
            print("  python compile_learning_data.py --days N  # Compile last N days")
            print("  python compile_learning_data.py --daily-report  # Generate daily report")
    else:
        # Default: compile last 30 days
        await compile_and_save_learning_data(days_back=30)


if __name__ == "__main__":
    asyncio.run(main())