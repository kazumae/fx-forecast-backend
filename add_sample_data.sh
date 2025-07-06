#!/bin/bash

echo "Adding sample comment data to the database..."

# Run the script inside the Docker container
docker-compose exec api python scripts/add_sample_comments.py

echo "Done! You can view the comment structure with:"
echo "docker-compose exec api python scripts/add_sample_comments.py --show"