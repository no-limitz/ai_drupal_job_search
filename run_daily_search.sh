#!/bin/bash

# Daily Drupal Job Search Runner
# This script should be added to crontab for daily automation

# Get the directory where this script is located
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"

# Change to the script directory
cd "$SCRIPT_DIR"

# Activate virtual environment
source venv/bin/activate

# Run the search with logging
LOG_FILE="logs/daily_search_$(date +%Y%m%d).log"

# Create logs directory if it doesn't exist
mkdir -p logs

# Run the search and log output
echo "$(date): Starting daily Drupal job search..." >> "$LOG_FILE"

python3 run_search.py >> "$LOG_FILE" 2>&1

SEARCH_EXIT_CODE=$?

if [ $SEARCH_EXIT_CODE -eq 0 ]; then
    echo "$(date): Daily search completed successfully" >> "$LOG_FILE"
else
    echo "$(date): Daily search failed with exit code $SEARCH_EXIT_CODE" >> "$LOG_FILE"
fi

# Keep only last 30 days of logs
find logs -name "daily_search_*.log" -mtime +30 -delete

echo "Daily search completed. Check $LOG_FILE for details."
