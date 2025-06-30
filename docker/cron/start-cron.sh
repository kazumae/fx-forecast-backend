#!/bin/bash
# Start cron with proper environment

# Export environment variables
printenv | grep -E '^(DATABASE_URL|SLACK_|ANTHROPIC_|TRADERMADE_|PYTHONPATH)' >> /etc/environment

# Install crontab
crontab /etc/cron.d/fx-cron

# Start cron in foreground
cron -f