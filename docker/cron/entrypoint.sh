#!/bin/bash
# Entrypoint script for cron container

# Export environment variables for cron
printenv | grep -E '^(DATABASE_URL|ANTHROPIC_API_KEY|SLACK_|TRADERMADE_|PYTHONPATH|POSTGRES_)' >> /etc/environment

# Make sure cron can access the environment variables
env >> /etc/environment

# Apply crontab
crontab /etc/cron.d/fx-cron

# Create log directory if it doesn't exist
mkdir -p /var/log/cron

# Start cron in foreground
exec cron -f