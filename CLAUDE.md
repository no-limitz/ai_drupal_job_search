# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an AI-powered Drupal job search system that uses CrewAI multi-agent architecture to find, analyze, and report on Drupal job opportunities. The system includes job storage, duplicate detection, notifications, and comprehensive reporting.

## Key Architecture Components

### Core Modules
- **main_orchestrator.py**: Central coordinator that integrates all system components
- **drupal_job_search.py**: CrewAI multi-agent search implementation with Search, Analysis, and Report agents
- **database_manager.py**: SQLite database operations for job storage and application tracking
- **config_manager.py**: JSON-based configuration management for search parameters
- **enhanced_job_search.py**: Notification system (email, Slack) and enhanced features

### Data Flow
1. **Search Phase**: CrewAI agents search job boards using Serper and Brave APIs
2. **Processing Phase**: Job results are parsed, validated, and deduplicated
3. **Storage Phase**: Valid jobs stored in SQLite database with relevance scoring
4. **Reporting Phase**: Comprehensive reports generated with market insights
5. **Notification Phase**: Reports sent via email and Slack channels

## Common Development Commands

### Setup and Installation
```bash
# Initial setup (creates venv, installs deps, initializes config/db)
chmod +x setup.sh && ./setup.sh

# Manual setup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Running the System
```bash
# Main job search with all features
./run_search.py

# Dashboard view only
./run_search.py --dashboard

# Export jobs to CSV
./run_search.py --export

# Search without notifications
./run_search.py --no-notifications

# System test
./test_system.py
```

### Database Operations
```bash
# View database statistics
python3 -c "from database_manager import JobDatabase; db = JobDatabase(); print(db.get_statistics())"

# Export recent jobs
python3 -c "from database_manager import JobDatabase; db = JobDatabase(); print(db.export_jobs_csv(days=30))"

# Cleanup old jobs
python3 -c "from database_manager import JobDatabase; db = JobDatabase(); print(f'Deleted: {db.cleanup_old_jobs()}')"
```

### Configuration Management
```bash
# View current configuration
python3 -c "from config_manager import JobSearchConfiguration; config = JobSearchConfiguration(); print(config.get_config_summary())"

# Update search keywords programmatically
python3 -c "
from config_manager import JobSearchConfiguration
config = JobSearchConfiguration()
config.update_keywords(['Senior Drupal Developer', 'Drupal Architect'])
"
```

## Required Environment Variables

Create `.env` file with these API keys:
- `SERPER_API_KEY`: Google search API (https://serper.dev/)
- `BRAVE_API_KEY`: Brave search API (https://api.search.brave.com/)
- `OPENAI_API_KEY`: OpenAI API for CrewAI agents (https://platform.openai.com/)

Optional notification settings:
- `SMTP_SERVER`, `SMTP_PORT`, `EMAIL_USER`, `EMAIL_PASSWORD`, `NOTIFICATION_EMAIL`
- `SLACK_WEBHOOK_URL`

## Development Patterns

### Adding New Job Sources
1. Extend `job_boards` list in config
2. Update search queries in `config_manager.py`
3. Modify URL validation in `main_orchestrator.py._validate_job_url()`

### Modifying Relevance Scoring
Update `_calculate_relevance_score()` method in `main_orchestrator.py` to adjust keyword weights and scoring logic.

### Extending Notifications
Add new notification methods to `NotificationManager` class in `enhanced_job_search.py`.

### Database Schema Changes
Modify `JobDatabase.create_tables()` method in `database_manager.py` and handle migrations.

## Testing

### System Tests
```bash
# Full system test
./test_system.py

# Manual verification tests
python3 test_manual_verification.py

# Bug-specific tests
python3 test_bug_001_fix.py
```

### Unit Testing
The system uses built-in validation and error handling rather than formal unit tests. Key validation points:
- Job data validation in `_validate_job_data()`
- URL validation in `_validate_job_url()`
- Configuration validation in `JobSearchConfiguration`

## Daily Automation

### Cron Setup (macOS/Linux)
```bash
# Edit crontab
crontab -e

# Add daily 9 AM search
0 9 * * * /Users/bobby/Sites/Developer/ai_drupal_job_search/run_daily_search.sh
```

### Manual Daily Run
```bash
chmod +x run_daily_search.sh
./run_daily_search.sh
```

## File Structure and Responsibilities

- **Core Logic**: `main_orchestrator.py` coordinates all operations
- **AI Search**: `drupal_job_search.py` contains CrewAI agent definitions
- **Data Layer**: `database_manager.py` handles all database operations
- **Configuration**: `config_manager.py` manages JSON-based settings
- **Notifications**: `enhanced_job_search.py` handles email/Slack integration
- **Entry Points**: `run_search.py` is the main CLI interface

## Error Handling and Logging

The system includes comprehensive error handling:
- API rate limit management
- URL validation and accessibility checks
- Database transaction rollbacks
- Graceful failure notifications

Logs are written to console and can be extended to file logging by modifying the logging configuration in relevant modules.