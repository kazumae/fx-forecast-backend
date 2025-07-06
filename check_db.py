#!/usr/bin/env python
"""Check database contents"""
import sqlite3
import json

conn = sqlite3.connect('/app/data/fx_forecast.db')
cursor = conn.cursor()

# Get tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", [t[0] for t in tables])

# Check if forecast_requests table exists
cursor.execute("SELECT COUNT(*) FROM forecast_requests")
forecast_count = cursor.fetchone()[0]
print(f"\nTotal forecasts: {forecast_count}")

if forecast_count > 0:
    # Get latest forecast
    cursor.execute("SELECT id, currency_pair, timeframes FROM forecast_requests ORDER BY created_at DESC LIMIT 1")
    latest = cursor.fetchone()
    print(f"Latest forecast: ID={latest[0]}, Pair={latest[1]}, Timeframes={latest[2]}")
    
    # Check comments for this forecast
    cursor.execute("SELECT COUNT(*) FROM forecast_comments WHERE forecast_id = ?", (latest[0],))
    comment_count = cursor.fetchone()[0]
    print(f"Comments for latest forecast: {comment_count}")

conn.close()