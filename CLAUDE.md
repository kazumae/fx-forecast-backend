# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview
FastAPI and PostgreSQL-based foreign exchange (FX) prediction backend API. Provides RESTful APIs for currency rate management, predictions, and batch processing with Slack integration.

## Essential Commands

### Development
```bash
# Start application
docker-compose up --build

# Run in background
docker-compose up -d

# View logs
docker-compose logs -f

# Access API documentation
# http://localhost:8900/docs
```

### Database Management
```bash
# Create new migration
docker-compose exec app alembic revision --autogenerate -m "description"

# Apply migrations
docker-compose exec app alembic upgrade head

# Rollback migration
docker-compose exec app alembic downgrade -1

# Direct database access
docker-compose exec db psql -U fx_user -d fx_forecast
```

### Batch Jobs
```bash
# Fetch forex rates
docker-compose exec app python run_batch.py fetch_forex_rates

# Cleanup old data
docker-compose exec app python run_batch.py cleanup_old_data --days 90

# Generate daily report
docker-compose exec app python run_batch.py generate_daily_report

# Send Slack notification
docker-compose exec app python run_batch.py slack_notification --notification-type daily_summary
```

### Testing
```bash
# Run all tests
bash scripts/test.sh

# Run unit tests only
bash scripts/test_unit.sh

# Run integration tests (requires Docker)
bash scripts/test_integration.sh

# Run E2E tests (requires all services)
bash tests/e2e/test_api_endpoints.sh

# Run specific test
python tests/unit/core/test_tradermade_config.py
docker-compose exec tradermade-stream python tests/integration/test_slack_notifications.py
```

## Architecture

### Directory Structure
- `backend/src/api/v1/` - API endpoint definitions
- `backend/src/batch/` - Batch processing jobs
- `backend/src/core/` - Core configuration and utilities
- `backend/src/models/` - SQLAlchemy database models
- `backend/src/schemas/` - Pydantic schemas for request/response validation
- `backend/src/services/` - Business logic layer
- `backend/src/stream/` - TraderMade WebSocket streaming
- `backend/alembic/` - Database migration scripts
- `backend/tests/` - Organized test suite (unit, integration, e2e, manual)
- `backend/scripts/` - Development and test runner scripts

### Key Design Patterns
1. **Layered Architecture**: Clear separation between API endpoints, services, and data models
2. **Dependency Injection**: FastAPI's dependency system for database sessions and auth
3. **Schema Validation**: Pydantic models for all API inputs/outputs
4. **Repository Pattern**: Service layer abstracts database operations

### Database Schema
- PostgreSQL with SQLAlchemy ORM
- Main entities: Users, ForexRates, Forecasts, Reports
- Migrations managed with Alembic
- Database runs on port 6543 (non-standard to avoid conflicts)

### API Design
- RESTful endpoints under `/api/v1/`
- Auto-generated OpenAPI documentation at `/docs`
- CORS enabled for frontend integration
- JWT authentication configured

## Development Notes

### Environment Setup
- Copy `.env.example` to `.env` before starting
- Python 3.11 required
- All dependencies in `requirements.txt`
- Hot reload enabled in development

### Common Gotchas
- Database port is 6543, not 5432
- API runs on port 8900
- Batch jobs require manual execution (no scheduler running by default)
- Test framework not set up - pytest recommended

### External Integrations
- TraderMade API for forex data (requires API key in .env)
- Slack webhooks for notifications (optional)