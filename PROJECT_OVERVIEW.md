# 🚀 AI Drupal Job Search System - Project Overview

## 📁 Project Structure

```
/Users/bobby/Sites/Developer/ai_drupal_job_search/
├── 📋 Core Files
│   ├── drupal_job_search.py       # Main CrewAI search logic
│   ├── main_orchestrator.py       # Central orchestrator
│   ├── enhanced_job_search.py     # Enhanced version with notifications
│   ├── database_manager.py        # SQLite database operations
│   └── config_manager.py          # Configuration management
│
├── 🔧 Setup & Configuration
│   ├── setup.sh                   # Automated setup script
│   ├── requirements.txt           # Python dependencies
│   ├── .env.example              # Environment variables template
│   └── .gitignore                # Git ignore rules
│
├── 🏃 Runners & Scripts
│   ├── run_search.py             # Main runner script
│   ├── run_daily_search.sh       # Daily automation script
│   └── test_system.py            # System testing script
│
└── 📚 Documentation
    └── README.md                 # Detailed setup instructions
```

## 🎯 Key Features

### 1. **Multi-Agent AI Search**
- **Search Agent**: Scours job boards using Serper and Brave APIs
- **Analysis Agent**: Filters and scores job relevance (1-10 scale)
- **Report Agent**: Generates professional daily reports

### 2. **Comprehensive Database**
- **Job Storage**: SQLite database with duplicate detection
- **Application Tracking**: Mark jobs as applied with notes
- **Statistics**: Track search performance and trends
- **Data Export**: CSV export functionality

### 3. **Smart Configuration**
- **Customizable Keywords**: Easy to modify search terms
- **Job Board Management**: Add/remove job boards
- **Relevance Scoring**: Adjustable minimum thresholds
- **JSON Configuration**: Persistent settings

### 4. **Multi-Channel Notifications**
- **Email Reports**: HTML-formatted daily summaries
- **Slack Integration**: Real-time notifications
- **File Reports**: Markdown reports with timestamps

### 5. **Automation Ready**
- **Cron Integration**: Daily scheduled searches
- **Logging**: Detailed execution logs
- **Error Handling**: Robust error recovery
- **Cleanup**: Automatic old job removal

## 🛠 Quick Setup

1. **Navigate to the project:**
   ```bash
   cd /Users/bobby/Sites/Developer/ai_drupal_job_search
   ```

2. **Run automated setup:**
   ```bash
   chmod +x setup.sh
   ./setup.sh
   ```

3. **Configure API keys:**
   ```bash
   cp .env.example .env
   # Edit .env with your actual API keys
   ```

4. **Test the system:**
   ```bash
   chmod +x test_system.py
   ./test_system.py
   ```

5. **Run your first search:**
   ```bash
   chmod +x run_search.py
   ./run_search.py
   ```

## 🔑 Required API Keys

| Service | Free Tier | Get Key From |
|---------|-----------|--------------|
| **Serper** | 2,500 searches/month | https://serper.dev/ |
| **Brave Search** | 2,000 queries/month | https://api.search.brave.com/ |
| **OpenAI** | Pay-per-use | https://platform.openai.com/ |

**Monthly Cost Estimate: $10-30**

## 📊 Usage Examples

### Basic Daily Search
```bash
./run_search.py
```

### Dashboard View
```bash
./run_search.py --dashboard
```

### Export Jobs to CSV
```bash
./run_search.py --export
```

### Search with Custom Config
```bash
./run_search.py --config my_config.json
```

### Disable Notifications
```bash
./run_search.py --no-notifications
```

## 🔄 Daily Automation

### Setup Cron Job (macOS/Linux)
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

## 📈 Customization Examples

### Add New Keywords
```python
from config_manager import JobSearchConfiguration
config = JobSearchConfiguration()
config.update_keywords([
    "Senior Drupal Developer",
    "Drupal Technical Lead", 
    "Drupal Solutions Architect"
])
```

### Add New Job Board
```python
config.add_job_board("remoteok.io")
```

### Adjust Relevance Threshold
```python
config.set_relevance_threshold(8.0)  # Only high-quality jobs
```

## 🔍 Job Search Coverage

### Primary Job Boards
- Indeed.com
- LinkedIn Jobs
- Dice.com
- FlexJobs.com

### Freelance Platforms
- Upwork.com
- Freelancer.com
- Toptal.com
- Gun.io
- Arc.dev

### Developer-Focused
- Stack Overflow Jobs
- AngelList
- RemoteOK.io
- WeWorkRemotely.com

## 📊 Report Features

### Executive Summary
- Total new opportunities found
- High/medium priority job counts
- Average relevance scores
- Search execution metrics

### Job Details
- Company and position title
- Location and remote options
- Salary/rate information
- Relevance scoring (1-10)
- Direct application links

### Market Insights
- Top hiring companies
- Trending skill requirements
- Geographic distribution
- Application success tracking

## 🔧 Advanced Features

### Database Operations
```python
from database_manager import JobDatabase
db = JobDatabase()

# Get recent high-quality jobs
jobs = db.get_recent_jobs(days=7, min_relevance=8.0)

# Mark job as applied
db.mark_applied(job_id=123, notes="Applied via email")

# Export to CSV
filename, count = db.export_jobs_csv(days=30)
```

### Email Notifications
Configure in `.env`:
```bash
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
EMAIL_USER=your_email@gmail.com
EMAIL_PASSWORD=your_app_password
NOTIFICATION_EMAIL=recipient@example.com
```

### Slack Integration
Add webhook to `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/your/webhook/url
```

## 🐛 Troubleshooting

### Common Issues

1. **API Rate Limits**
   - Check usage on provider dashboards
   - Upgrade to paid plans if needed

2. **Missing Dependencies**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

3. **Permission Errors**
   ```bash
   chmod +x *.sh *.py
   ```

4. **Database Issues**
   ```bash
   rm drupal_jobs.db  # Reset database
   python3 -c "from database_manager import JobDatabase; JobDatabase()"
   ```

## 📞 Support

- **System Test**: `./test_system.py`
- **Dashboard**: `./run_search.py --dashboard`
- **Logs**: Check `logs/` directory
- **Configuration**: Review `config.json`

## 🚀 Future Enhancements

- **Web Dashboard**: Flask/Django interface
- **Machine Learning**: Job relevance prediction
- **API Integration**: Direct application submissions
- **Mobile App**: iOS/Android companion
- **Team Features**: Multi-user support

---

**Created:** $(date)
**Location:** /Users/bobby/Sites/Developer/ai_drupal_job_search/
**System:** AI-Powered CrewAI Job Search with Multi-Agent Architecture
