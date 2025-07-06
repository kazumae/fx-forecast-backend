"""Test script for pattern analysis functionality"""
import asyncio
import requests
from datetime import datetime

# Base URL for the API
BASE_URL = "http://localhost:8767/api/v1"

def test_pattern_analysis():
    """Test pattern analysis for XAUUSD"""
    print("=== Testing Pattern Analysis ===\n")
    
    # 1. Get pattern analysis for XAUUSD
    print("1. Getting pattern analysis for XAUUSD (last 30 days)...")
    response = requests.get(f"{BASE_URL}/patterns/analysis/XAUUSD?days_back=30")
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Total patterns analyzed: {data['total_patterns_analyzed']}")
        print(f"✓ Confidence score: {data['confidence_score']:.0%}")
        
        # Show pattern statistics
        if data.get('pattern_stats'):
            print("\nPattern Statistics:")
            for pattern in data['pattern_stats'][:5]:
                print(f"  - {pattern['pattern_type']}: "
                      f"Success rate {pattern['success_rate']:.1%} "
                      f"({pattern['success_count']}/{pattern['total_occurrences']} trades)")
        
        # Show recommendations
        if data.get('recommendations'):
            print("\nRecommendations:")
            for rec in data['recommendations']:
                print(f"  - {rec}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")
    
    print("\n" + "="*50 + "\n")

def test_similar_patterns():
    """Test finding similar patterns"""
    print("2. Finding similar historical patterns...")
    
    # Define current market conditions
    current_conditions = {
        "currency_pair": "XAUUSD",
        "timeframe": "5m",
        "pattern_type": "point_1"
    }
    
    response = requests.post(
        f"{BASE_URL}/patterns/similar?limit=3",
        json=current_conditions
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Found {data['total_found']} similar patterns")
        
        for i, match in enumerate(data['matches'], 1):
            print(f"\nMatch #{i}:")
            print(f"  - Similarity: {match['similarity_score']:.1%}")
            print(f"  - Pattern: {match['pattern_type']}")
            print(f"  - Outcome: {match['outcome']}")
            print(f"  - Date: {match['occurred_at']}")
            
            if match.get('key_similarities'):
                print(f"  - Similarities: {', '.join(match['key_similarities'])}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")
    
    print("\n" + "="*50 + "\n")

def test_pattern_context():
    """Test getting pattern context for AI"""
    print("3. Getting pattern context for AI predictions...")
    
    response = requests.get(
        f"{BASE_URL}/patterns/context/XAUUSD?timeframes=1m,5m,15m,1h"
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Currency pair: {data['currency_pair']}")
        print(f"✓ Timeframes: {', '.join(data['timeframes'])}")
        print(f"✓ Context length: {data['context_length']} characters")
        
        # Show a preview of the context
        context_preview = data['context'][:500] + "..." if len(data['context']) > 500 else data['context']
        print(f"\nContext preview:\n{context_preview}")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")
    
    print("\n" + "="*50 + "\n")

def test_pattern_statistics():
    """Test getting overall pattern statistics"""
    print("4. Getting overall pattern statistics...")
    
    response = requests.get(f"{BASE_URL}/patterns/statistics")
    
    if response.status_code == 200:
        data = response.json()
        print("✓ Statistics retrieved successfully")
        
        for pair, stats in data.items():
            print(f"\n{pair}:")
            if "error" in stats:
                print(f"  - {stats['error']}")
            else:
                print(f"  - Total patterns: {stats.get('total_patterns', 0)}")
                print(f"  - Confidence: {stats.get('confidence_score', 0):.0%}")
                
                if stats.get('top_patterns'):
                    print("  - Top patterns:")
                    for pattern in stats['top_patterns']:
                        print(f"    • {pattern['type']}: {pattern['success_rate']:.1%} "
                              f"({pattern['occurrences']} occurrences)")
    else:
        print(f"✗ Error: {response.status_code} - {response.text}")

def main():
    """Run all tests"""
    print(f"\n{'='*60}")
    print(f"Pattern Analysis API Test - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")
    
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL.replace('/api/v1', '')}/health")
        if response.status_code != 200:
            print("✗ API is not running. Please start the backend first.")
            return
    except requests.exceptions.ConnectionError:
        print("✗ Cannot connect to API. Please start the backend first.")
        print("  Run: docker-compose up")
        return
    
    # Run tests
    test_pattern_analysis()
    test_similar_patterns()
    test_pattern_context()
    test_pattern_statistics()
    
    print(f"\n{'='*60}")
    print("All tests completed!")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    main()