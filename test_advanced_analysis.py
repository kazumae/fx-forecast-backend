"""Test script for advanced analysis features"""
import asyncio
from app.services.advanced_analysis_service import (
    AdvancedAnalysisService, 
    TrendDirection, 
    MarketCondition
)


async def test_advanced_analysis():
    """Test the advanced analysis service"""
    
    print("=== Advanced Analysis Service Test ===\n")
    
    # Initialize service
    service = AdvancedAnalysisService()
    
    # Test Case 1: Bullish market with pullback opportunity
    print("Test Case 1: Bullish Market with Pullback")
    print("-" * 40)
    
    timeframe_data_bullish = {
        "4時間": {
            "current_price": 150.50,
            "ema20": 150.20,
            "ema75": 149.80,
            "ema200": 149.50,
            "atr": 40,
            "recent_ranges": [35, 40, 45, 38, 42],
            "support_levels": [149.00, 148.50],
            "resistance_levels": [151.00, 152.00]
        },
        "1時間": {
            "current_price": 150.50,
            "ema20": 150.30,
            "ema75": 150.10,
            "ema200": 149.90,
            "atr": 25,
            "recent_ranges": [20, 25, 30, 22, 28],
            "support_levels": [150.00, 149.50],
            "resistance_levels": [151.00, 151.50]
        },
        "15分": {
            "current_price": 150.50,
            "ema20": 150.55,
            "ema75": 150.60,
            "ema200": 150.40,
            "atr": 15,
            "recent_ranges": [12, 15, 18, 14, 16],
            "support_levels": [150.30, 150.00],
            "resistance_levels": [150.80, 151.00]
        },
        "5分": {
            "current_price": 150.50,
            "ema20": 150.60,
            "ema75": 150.65,
            "ema200": 150.55,
            "atr": 10,
            "recent_ranges": [8, 10, 12, 9, 11],
            "support_levels": [150.40, 150.30],
            "resistance_levels": [150.70, 150.80]
        }
    }
    
    # Perform analysis
    volatility = service.analyze_volatility(timeframe_data_bullish["15分"], "15分")
    mtf_analysis = service.perform_multi_timeframe_analysis(timeframe_data_bullish)
    
    print(f"Volatility Analysis:")
    print(f"  Current: {volatility.current_volatility} pips")
    print(f"  Average: {volatility.average_volatility} pips")
    print(f"  Trend: {volatility.volatility_trend}")
    print(f"  Recommended Stop: {volatility.recommended_stop_distance} pips")
    print(f"  Recommended Target: {volatility.recommended_target_distance} pips")
    print()
    
    print(f"Multi-Timeframe Analysis:")
    print(f"  Primary Trend: {mtf_analysis.primary_trend.value}")
    print(f"  Entry TF Trend: {mtf_analysis.entry_timeframe_trend.value}")
    print(f"  Execution TF Trend: {mtf_analysis.execution_timeframe_trend.value}")
    print(f"  Trend Alignment: {'Yes' if mtf_analysis.trend_alignment else 'No'}")
    print(f"  Pullback Detected: {'Yes' if mtf_analysis.pullback_detected else 'No'}")
    if mtf_analysis.pullback_detected:
        print(f"  Pullback Quality: {mtf_analysis.pullback_quality:.0%}")
    if mtf_analysis.entry_zone:
        print(f"  Entry Zone: {mtf_analysis.entry_zone[0]:.2f} - {mtf_analysis.entry_zone[1]:.2f}")
    print(f"  Risk/Reward Ratio: 1:{mtf_analysis.risk_reward_ratio}")
    print()
    
    # Generate enhanced prompt
    enhanced_prompt = service.generate_enhanced_analysis_prompt(volatility, mtf_analysis)
    print("Enhanced Prompt Generated:")
    print(enhanced_prompt[:500] + "...")  # Show first 500 chars
    print("\n")
    
    # Test Case 2: Bearish market with retracement
    print("Test Case 2: Bearish Market with Retracement")
    print("-" * 40)
    
    timeframe_data_bearish = {
        "4時間": {
            "current_price": 148.50,
            "ema20": 148.80,
            "ema75": 149.20,
            "ema200": 149.50,
            "atr": 45,
            "recent_ranges": [40, 45, 50, 43, 48],
            "support_levels": [148.00, 147.50],
            "resistance_levels": [149.00, 149.50]
        },
        "1時間": {
            "current_price": 148.50,
            "ema20": 148.60,
            "ema75": 148.80,
            "ema200": 149.00,
            "atr": 30,
            "recent_ranges": [25, 30, 35, 28, 32],
            "support_levels": [148.00, 147.50],
            "resistance_levels": [149.00, 149.20]
        },
        "15分": {
            "current_price": 148.50,
            "ema20": 148.45,
            "ema75": 148.40,
            "ema200": 148.60,
            "atr": 20,
            "recent_ranges": [18, 20, 22, 19, 21],
            "support_levels": [148.30, 148.00],
            "resistance_levels": [148.70, 149.00]
        }
    }
    
    # Perform analysis
    volatility2 = service.analyze_volatility(timeframe_data_bearish["1時間"], "1時間")
    mtf_analysis2 = service.perform_multi_timeframe_analysis(timeframe_data_bearish)
    
    print(f"Volatility Analysis:")
    print(f"  Current: {volatility2.current_volatility} pips")
    print(f"  Recommended Stop: {volatility2.recommended_stop_distance} pips")
    print(f"  Recommended Target: {volatility2.recommended_target_distance} pips")
    print()
    
    print(f"Multi-Timeframe Analysis:")
    print(f"  Primary Trend: {mtf_analysis2.primary_trend.value}")
    print(f"  Pullback Detected: {'Yes' if mtf_analysis2.pullback_detected else 'No'}")
    if mtf_analysis2.entry_zone:
        print(f"  Entry Zone: {mtf_analysis2.entry_zone[0]:.2f} - {mtf_analysis2.entry_zone[1]:.2f}")
    print()
    
    # Test Case 3: Ranging market
    print("Test Case 3: Ranging Market")
    print("-" * 40)
    
    timeframe_data_ranging = {
        "4時間": {
            "current_price": 150.00,
            "ema20": 150.05,
            "ema75": 149.95,
            "ema200": 150.00,
            "atr": 20,
            "recent_ranges": [18, 20, 22, 19, 21],
            "support_levels": [149.50, 149.00],
            "resistance_levels": [150.50, 151.00]
        },
        "1時間": {
            "current_price": 150.00,
            "ema20": 149.95,
            "ema75": 150.05,
            "ema200": 150.00,
            "atr": 15,
            "recent_ranges": [12, 15, 18, 14, 16],
            "support_levels": [149.80, 149.50],
            "resistance_levels": [150.20, 150.50]
        }
    }
    
    mtf_analysis3 = service.perform_multi_timeframe_analysis(timeframe_data_ranging)
    
    print(f"Multi-Timeframe Analysis:")
    print(f"  Primary Trend: {mtf_analysis3.primary_trend.value}")
    print(f"  Trend Alignment: {'Yes' if mtf_analysis3.trend_alignment else 'No'}")
    print(f"  Entry Zone: {'Not defined' if not mtf_analysis3.entry_zone else f'{mtf_analysis3.entry_zone[0]:.2f} - {mtf_analysis3.entry_zone[1]:.2f}'}")
    print()
    
    print("=== Test Complete ===")


if __name__ == "__main__":
    asyncio.run(test_advanced_analysis())