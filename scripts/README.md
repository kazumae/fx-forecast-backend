# Database Scripts

This directory contains utility scripts for managing the database.

## add_sample_comments.py

This script adds sample comment data to existing forecasts in the database, demonstrating the hierarchical comment structure with replies.

### Features

- Adds questions with AI-generated answers
- Creates standalone notes
- Adds nested replies to show the comment hierarchy
- Supports different comment types: "question", "answer", "note"
- Distinguishes between User and AI comments

### Usage

From the backend directory, run:

```bash
# Add sample comments to the database
./add_sample_data.sh

# Or run directly in the container
docker-compose exec api python scripts/add_sample_comments.py

# View the comment structure
docker-compose exec api python scripts/add_sample_comments.py --show
```

### Comment Structure

The script creates the following comment hierarchy:

```
Forecast
├── Question (User)
│   ├── Answer (AI Assistant)
│   │   └── Reply Note (User) - optional
├── Note (User)
│   └── Reply Note (User) - optional
```

### Prerequisites

- The database must have at least one forecast entry
- Docker container must be running

### Sample Data

The script adds:
- Technical analysis questions about support lines, volume indicators, and MACD divergence
- AI responses with confidence levels and reasoning
- User notes about important market events and patterns
- Follow-up replies and discussions