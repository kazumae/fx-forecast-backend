# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a FastAPI backend for FX (forex) forecasting that uses Anthropic's AI to analyze trading charts. The system accepts chart images, performs AI-powered analysis, stores results in a database, and sends notifications via Slack.

## Essential Commands

### Development
```bash
# Build and run with Docker Compose
docker-compose up --build

# Run without rebuilding
docker-compose up

# Access running container
docker-compose exec api bash

# View logs
docker-compose logs -f api
```

### Database Operations
```bash
# Create a new migration after model changes
docker-compose exec api alembic revision --autogenerate -m "Description of changes"

# Apply migrations
docker-compose exec api alembic upgrade head

# Rollback one migration
docker-compose exec api alembic downgrade -1

# View migration history
docker-compose exec api alembic history
```

### Testing
```bash
# The API documentation provides interactive testing at:
http://localhost:8767/docs

# For manual testing, use the test_*.html files in the root directory
```

## Architecture Overview

### Service Architecture
- **FastAPI Application**: Main web framework handling HTTP requests
- **SQLite Database**: Persistent storage for forecasts and analysis results
- **Anthropic Service**: Integration with Claude AI for chart analysis
- **Slack Service**: Webhook integration for real-time notifications
- **Image Storage**: File-based storage organized by date (data/images/YYYY/MM/)

### Key Design Patterns
1. **Dependency Injection**: Database sessions and services are injected via FastAPI's dependency system
2. **Schema Validation**: Pydantic models ensure data integrity at API boundaries
3. **Service Layer**: Business logic is isolated in service modules, not in endpoints
4. **Repository Pattern**: Database operations are abstracted through SQLAlchemy models

### Critical Service Flows

#### Chart Analysis Flow
1. Client uploads 1-4 chart images via `/api/v1/analysis/analyze`
2. Images are saved to disk with timestamp-based filenames
3. Anthropic service processes images using specialized prompts
4. Results are stored in database with references to saved images
5. Slack notification is sent with analysis summary
6. Full response returned to client

#### Comment System Architecture
- Comments support three types: "question", "answer", and "note"
- Questions automatically trigger AI responses when posted
- Answers are always nested within their parent questions (never returned at top level)
- The system maintains a hierarchical structure with parent-child relationships

#### Trade Review System
- Accepts chart images with trade entry/exit points marked
- Provides detailed analysis of trade execution quality
- Supports commenting on reviews with automatic AI responses for questions
- Stores review scores and recommendations for improvement

### Database Schema
- **forecast_requests** table: Stores all analysis results
  - `id`: Integer primary key
  - `currency_pair`: Currency pair (e.g., "USDJPY")
  - `timeframes`: JSON array of timeframes
  - `response`: Full AI analysis text
  - `metadata`: JSON field for flexible data
  - `created_at`, `updated_at`: Timestamps with JST timezone

- **forecast_comments** table: Hierarchical comment system
  - `parent_comment_id`: Links to parent for nested replies
  - `comment_type`: Enum of "question", "answer", "note"
  - `is_ai_response`: Boolean flag for AI-generated content

- **trade_reviews** table: Post-trade analysis storage
  - `overall_score`: Float rating (0-10)
  - `entry_analysis`, `good_points`, `improvement_points`: Analysis fields
  - Links to images and comments via foreign keys

### Environment Configuration
Required environment variables:
- `ANTHROPIC_API_KEY`: Claude API access
- `SLACK_WEBHOOK_URL`: Slack integration
- `DATABASE_URL`: SQLite connection string (default provided)

### Important Considerations

1. **Image Handling**: Always validate image formats (JPEG/PNG only) and sizes before processing
2. **Prompt Engineering**: Analysis prompts are in `app/core/prompts.py` - maintain their structure when modifying
3. **Database Migrations**: Always create migrations for model changes, never modify the database directly
4. **Error Handling**: Services should raise appropriate exceptions, endpoints handle and format errors
5. **Async Operations**: FastAPI endpoints are async but database operations use sync SQLAlchemy
6. **Timezone Handling**: All timestamps are converted to JST (Japan Standard Time) using the timezone utilities
7. **Comment API Behavior**: When creating a "question" type comment, the system automatically generates an AI answer