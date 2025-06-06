# AI-Powered Drupal Job Search System

A sophisticated job search system using CrewAI multi-agent architecture with cost-optimized LLM usage and hybrid data extraction approach.

## Architecture Overview

This system combines multiple technologies for comprehensive job searching:

- **🔍 Search Phase**: Serper + Brave APIs for broad job discovery
- **🤖 Analysis Phase**: Playwright browser automation for detailed data extraction  
- **📊 AI Processing**: Cost-optimized multi-LLM approach (89% cost savings)
- **📝 Reporting**: Automated daily reports with real job data

## Quick Start

1. **Clone the repository:**
```bash
git clone https://github.com/no-limitz/ai_drupal_job_search.git
cd ai_drupal_job_search
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

**Note:** The requirements.txt includes:
- `crewai` & `crewai-tools` - Multi-agent framework
- `playwright` & `playwright-stealth` - Browser automation
- `langchain-openai` - LLM integration
- Additional utilities for web scraping and data processing

4. **Install Playwright browsers:**
```bash
playwright install chromium
```

5. **Set up environment variables:**
```bash
cp .env.example .env
# Edit .env file with your actual API keys
```

6. **Make scripts executable:**
```bash
chmod +x run_search.py
chmod +x test_system.py
```

7. **Run the script:**
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

## Cost Optimization Features

This system implements intelligent cost optimization:

### Multi-LLM Architecture (89% cost savings vs all-GPT-4)
- **Search Agent**: `gpt-3.5-turbo` - Cost-effective for search queries
- **Analysis Agent**: `gpt-4o` - Balanced capability/cost for complex analysis  
- **Report Agent**: `gpt-4o-mini` - Ultra-low cost for formatting tasks

### Hybrid Data Extraction
- **APIs First**: Fast, cheap job discovery via Serper/Brave
- **Browser Automation**: Playwright for detailed extraction when needed
- **Smart Fallbacks**: Multiple extraction strategies for reliability

## Daily Automation

Set up a daily cron job to run the search automatically:

```bash
# Edit crontab
crontab -e

# Add this line to run daily at 9 AM
0 9 * * * cd /full/path/to/ai_drupal_job_search && ./venv/bin/python drupal_job_search.py
```

Or use the included daily runner script:
```bash
chmod +x run_daily_search.sh
# Then add to cron:
0 9 * * * /full/path/to/ai_drupal_job_search/run_daily_search.sh
```

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
   pip install crewai crewai-tools playwright
   ```

6. **Playwright Browser Issues:**
   ```bash
   # Install/reinstall Playwright browsers
   playwright install chromium
   
   # For headless browser issues
   playwright install-deps
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
- OpenAI API: $3-10 (89% cost optimized vs GPT-4 only)
- Playwright: Free (open source)

**Total estimated monthly cost: $3-10** (previously $10-30 before optimization)

### Cost Optimization Benefits
- **89% LLM cost reduction** through intelligent model selection
- **Free browser automation** via Playwright (vs paid scraping services)
- **API-first approach** minimizes expensive browser automation usage
