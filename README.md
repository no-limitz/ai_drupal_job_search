# Drupal Job Search Setup Guide

## Quick Start

1. **Navigate to the project directory:**
```bash
cd /Users/bobby/Sites/Developer/ai_drupal_job_search
```

2. **Run the automated setup (recommended):**
```bash
chmod +x setup.sh
./setup.sh
```

**OR manually:**

2. **Create virtual environment:**
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies (IMPORTANT - Do this first):**
```bash
pip install -r requirements.txt
```

**Note:** The requirements.txt file contains all necessary dependencies including `crewai` and `crewai-tools`. If you encounter any missing module errors, the requirements.txt should resolve them.

4. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env file with your actual API keys
```

5. **Make scripts executable:**
```bash
chmod +x run_search.py
chmod +x test_system.py
```

6. **Run the script:**
```bash
# For the main job search with dashboard
./run_search.py --dashboard

# Or run the basic script
python drupal_job_search.py

# To test the system
./test_system.py
```

## Getting API Keys

### 1. Serper API Key (Free tier: 2,500 searches/month)
- Go to https://serper.dev/
- Sign up for free account
- Copy your API key from dashboard
- Add to `.env` file: `SERPER_API_KEY=your_key_here`

### 2. Brave Search API Key (Free tier: 2,000 queries/month)
- Visit https://api.search.brave.com/
- Create free account
- Get API key from dashboard
- Add to `.env` file: `BRAVE_API_KEY=your_key_here`

### 3. OpenAI API Key (Pay-per-use)
- Go to https://platform.openai.com/
- Create account and add billing method
- Generate API key
- Add to `.env` file: `OPENAI_API_KEY=your_key_here`

## Daily Automation

### macOS/Linux (using cron):
```bash
# Edit crontab
crontab -e

# Add this line to run daily at 9 AM
0 9 * * * /Users/bobby/Sites/Developer/ai_drupal_job_search/venv/bin/python /Users/bobby/Sites/Developer/ai_drupal_job_search/drupal_job_search.py
```

### Windows (using Task Scheduler):
1. Open Task Scheduler
2. Create Basic Task
3. Set to run daily at preferred time
4. Set action to start program:
   - Program: `python.exe`
   - Arguments: `drupal_job_search.py`
   - Start in: `/Users/bobby/Sites/Developer/ai_drupal_job_search`

## Customization

### Modify Search Keywords
Edit `job_keywords` in the script:
```python
self.job_keywords = [
    "Senior Drupal Developer",
    "Drupal Developer Contract",
    "Drupal Backend Developer",
    "Drupal CMS Developer",
    "Drupal Architect",
    # Add your custom keywords here
]
```

### Add More Job Boards
Edit `job_boards` list:
```python
self.job_boards = [
    "indeed.com",
    "linkedin.com/jobs",
    "dice.com",
    # Add more sites here
]
```

### Change Search Timeframe
Modify the `freshness` parameter in `brave_search_tool`:
- `'pd'` = Past day
- `'pw'` = Past week (current setting)
- `'pm'` = Past month
- `'py'` = Past year

## Output

The script generates:
- **Console output**: Real-time progress and results
- **Daily report**: `drupal_jobs_report_YYYY-MM-DD.md` file
- **Logs**: Detailed execution logs

## Troubleshooting

### Common Issues:

1. **API Rate Limits:**
   - Check your usage on each API provider's dashboard
   - Upgrade to paid plans if needed
   - The script includes built-in rate limiting

2. **Dependencies:**
   ```bash
   pip install --upgrade -r requirements.txt
   ```

3. **Environment Variables:**
   ```bash
   # Check if .env file exists and has correct format
   cat .env
   ```

4. **Permissions:**
   ```bash
   # Make scripts executable
   chmod +x run_search.py
   chmod +x test_system.py
   chmod +x setup.sh
   ```

5. **Missing Dependencies:**
   ```bash
   # If you get module errors, reinstall requirements
   pip install -r requirements.txt
   
   # Or install individual packages if needed
   pip install crewai crewai-tools
   ```

## Advanced Features

### Email Notifications
Uncomment and configure email settings in `.env` to receive daily reports via email.

### Slack Integration
Add your Slack webhook URL to `.env` to receive notifications in Slack channels.

### Database Storage
The script can be extended to store job listings in a database to track duplicates and maintain history.

## Support

If you encounter issues:
1. Check the logs for specific error messages
2. Verify all API keys are correct and active
3. Ensure you have sufficient API credits
4. Check internet connectivity

## Cost Estimation

**Monthly costs (approximate):**
- Serper API: Free (2,500 searches)
- Brave API: Free (2,000 queries)  
- OpenAI API: $10-30 (depending on usage)

**Total estimated monthly cost: $10-30**
