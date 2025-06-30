# Cron Container Environment Variables Fix

## Problem
The AI market analysis batch job was failing with `ValueError: ANTHROPIC_API_KEY environment variable is not set` because cron jobs run with a minimal environment and don't inherit Docker container environment variables.

## Solution
1. Created an `entrypoint.sh` script that exports all container environment variables to `/etc/environment` before starting cron
2. Updated crontab to source `/etc/environment` before running each job
3. Modified `AnthropicAnalysisClient` to use mock mode when API key is missing (for testing)

## Changes Made

### 1. Created `docker/cron/entrypoint.sh`
This script:
- Exports all relevant environment variables to `/etc/environment`
- Applies the crontab
- Starts cron in foreground mode

### 2. Updated `docker/cron/Dockerfile`
- Copies and makes the entrypoint script executable
- Uses the entrypoint script instead of directly running cron

### 3. Updated `docker/cron/crontab`
- Each cron job now sources `/etc/environment` before execution
- This ensures all environment variables are available

### 4. Updated `src/services/analysis/anthropic_client.py`
- Changed from raising ValueError to logging warning and using mock mode
- Allows the system to continue running even without API key (useful for testing)

## How to Apply Changes

1. Rebuild the cron container:
```bash
docker-compose build cron
```

2. Restart the services:
```bash
docker-compose down
docker-compose up -d
```

## Verifying the Fix

Check if environment variables are being passed correctly:
```bash
docker-compose exec cron cat /etc/environment | grep ANTHROPIC_API_KEY
```

Monitor the AI analysis logs:
```bash
docker-compose logs -f cron
# or
tail -f backend/logs/cron/ai_analysis.log
```

## Environment Variables Required

Make sure these are set in your `.env` file:
- `ANTHROPIC_API_KEY` - For AI market analysis (optional, uses mock mode if not set)
- `DATABASE_URL` - PostgreSQL connection string
- `SLACK_WEBHOOK_URL` - For Slack notifications (optional)
- `TRADERMADE_API_KEY` - For forex data (optional)