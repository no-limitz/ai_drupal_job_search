#!/usr/bin/env python3
"""
CrewAI-powered Drupal Job Search Script
Searches for Senior Drupal Developer contract jobs across major job boards
"""

import os
import json
import logging
import re
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin
from crewai import Agent, Task, Crew, Process
from crewai_tools import SerperDevTool
from crewai.tools import tool
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from browser_job_scraper import extract_job_details_browser_tool

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class JobListing:
    title: str
    company: str
    location: str
    url: str
    description: str
    posted_date: str
    source: str
    salary_range: str = ""

class JobSearchConfig:
    def __init__(self):
        self.serper_api_key = os.getenv('SERPER_API_KEY')
        self.brave_api_key = os.getenv('BRAVE_API_KEY')
        self.openai_api_key = os.getenv('OPENAI_API_KEY')
        
        if not all([self.serper_api_key, self.brave_api_key, self.openai_api_key]):
            raise ValueError("Missing required API keys. Please set SERPER_API_KEY, BRAVE_API_KEY, and OPENAI_API_KEY")
        
        # Job search parameters
        self.job_keywords = [
            "Senior Drupal Developer",
            "Drupal Developer Contract",
            "Drupal Backend Developer",
            "Drupal CMS Developer",
            "Drupal Architect"
        ]
        
        self.job_boards = [
            "indeed.com",
            "linkedin.com/jobs",
            "dice.com",
            "flexjobs.com",
            "upwork.com",
            "freelancer.com",
            "toptal.com",
            "gun.io",
            "arc.dev",
            "stackoverflow.com/jobs"
        ]
        
        self.location_filters = ["United States", "Remote USA", "US Remote"]

def _brave_search_implementation(query: str) -> str:
    """Internal implementation for Brave search"""
    config = JobSearchConfig()
    
    headers = {
        'Accept': 'application/json',
        'Accept-Encoding': 'gzip',
        'X-Subscription-Token': config.brave_api_key
    }
    
    params = {
        'q': query,
        'count': 20,
        'offset': 0,
        'mkt': 'en-US',
        'safesearch': 'moderate',
        'freshness': 'pw'  # Past week
    }
    
    try:
        response = requests.get(
            'https://api.search.brave.com/res/v1/web/search',
            headers=headers,
            params=params
        )
        response.raise_for_status()
        return json.dumps(response.json())
    except Exception as e:
        logger.error(f"Brave search error: {e}")
        return f"Error searching with Brave: {str(e)}"

@tool
def brave_search_tool(query: str) -> str:
    """Custom tool to search using Brave API"""
    return _brave_search_implementation(query)

def _extract_job_details_implementation(url: str) -> str:
    """Internal implementation for job details extraction"""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Extract job details based on the site
        domain = urlparse(url).netloc.lower()
        
        job_data = {
            'url': url,
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'posted_date': '',
            'source': domain
        }
        
        if 'indeed.com' in domain:
            job_data.update(_extract_indeed_job(soup))
        elif 'linkedin.com' in domain:
            job_data.update(_extract_linkedin_job(soup))
        elif 'dice.com' in domain:
            job_data.update(_extract_dice_job(soup))
        else:
            job_data.update(_extract_generic_job(soup))
        
        return json.dumps(job_data)
        
    except Exception as e:
        logger.error(f"Error extracting job details from {url}: {e}")
        return json.dumps({
            'url': url,
            'error': str(e),
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'posted_date': '',
            'source': urlparse(url).netloc if url else 'unknown'
        })

@tool
def extract_job_details(url: str) -> str:
    """Extract job details from a job posting URL"""
    return _extract_job_details_implementation(url)

def _extract_indeed_job(soup):
    """Extract job data from Indeed job page"""
    data = {}
    
    # Title
    title_elem = soup.find('h1', {'data-jk': True}) or soup.find('h1', class_=re.compile('jobsearch-JobInfoHeader-title'))
    data['title'] = title_elem.get_text(strip=True) if title_elem else ''
    
    # Company
    company_elem = soup.find('div', {'data-testid': 'inlineHeader-companyName'}) or soup.find('span', class_=re.compile('companyName'))
    data['company'] = company_elem.get_text(strip=True) if company_elem else ''
    
    # Location
    location_elem = soup.find('div', {'data-testid': 'job-location'}) or soup.find('div', class_=re.compile('companyLocation'))
    data['location'] = location_elem.get_text(strip=True) if location_elem else ''
    
    # Description
    desc_elem = soup.find('div', {'id': 'jobDescriptionText'}) or soup.find('div', class_=re.compile('jobsearch-jobDescriptionText'))
    data['description'] = desc_elem.get_text(strip=True)[:500] if desc_elem else ''
    
    # Salary
    salary_elem = soup.find('span', class_=re.compile('salary')) or soup.find('div', class_=re.compile('salary'))
    data['salary'] = salary_elem.get_text(strip=True) if salary_elem else ''
    
    return data

def _extract_linkedin_job(soup):
    """Extract job data from LinkedIn job page"""
    data = {}
    
    # Title
    title_elem = soup.find('h1', class_=re.compile('top-card-layout__title'))
    data['title'] = title_elem.get_text(strip=True) if title_elem else ''
    
    # Company
    company_elem = soup.find('a', class_=re.compile('topcard__org-name-link')) or soup.find('span', class_=re.compile('topcard__flavor'))
    data['company'] = company_elem.get_text(strip=True) if company_elem else ''
    
    # Location
    location_elem = soup.find('span', class_=re.compile('topcard__flavor--bullet'))
    data['location'] = location_elem.get_text(strip=True) if location_elem else ''
    
    # Description
    desc_elem = soup.find('div', class_=re.compile('show-more-less-html__markup'))
    data['description'] = desc_elem.get_text(strip=True)[:500] if desc_elem else ''
    
    return data

def _extract_dice_job(soup):
    """Extract job data from Dice job page"""
    data = {}
    
    # Title
    title_elem = soup.find('h1', {'data-cy': 'jobTitle'})
    data['title'] = title_elem.get_text(strip=True) if title_elem else ''
    
    # Company
    company_elem = soup.find('a', {'data-cy': 'companyNameLink'})
    data['company'] = company_elem.get_text(strip=True) if company_elem else ''
    
    # Location
    location_elem = soup.find('li', {'data-cy': 'jobLocation'})
    data['location'] = location_elem.get_text(strip=True) if location_elem else ''
    
    # Description
    desc_elem = soup.find('div', {'data-cy': 'jobDescription'})
    data['description'] = desc_elem.get_text(strip=True)[:500] if desc_elem else ''
    
    return data

def _extract_generic_job(soup):
    """Extract job data from generic job posting page"""
    data = {}
    
    # Try common patterns for title
    title_elem = soup.find('h1') or soup.find('title')
    data['title'] = title_elem.get_text(strip=True) if title_elem else ''
    
    # Try to find company in common locations
    for selector in ['span.company', 'div.company', 'a.company', '.employer']:
        company_elem = soup.select_one(selector)
        if company_elem:
            data['company'] = company_elem.get_text(strip=True)
            break
    
    # Try to find location
    for selector in ['span.location', 'div.location', '.job-location']:
        location_elem = soup.select_one(selector)
        if location_elem:
            data['location'] = location_elem.get_text(strip=True)
            break
    
    # Get first paragraph or main content as description
    desc_elem = soup.find('div', class_=re.compile('description|content|job-detail'))
    if not desc_elem:
        desc_elem = soup.find('p')
    data['description'] = desc_elem.get_text(strip=True)[:500] if desc_elem else ''
    
    return data

def _extract_job_urls_implementation(search_context) -> str:
    """Internal implementation for URL extraction from search results"""
    try:
        import re
        import json
        
        logger.info("🔍 Starting URL extraction from search results...")
        
        job_urls = []
        
        # Handle both string and dictionary inputs
        if isinstance(search_context, dict):
            logger.info("📋 Processing dictionary search results...")
            search_text = json.dumps(search_context)
            
            # Extract URLs from organic results if available
            if 'organic' in search_context:
                logger.info(f"📊 Found {len(search_context['organic'])} organic results to process")
                for result in search_context['organic']:
                    if 'link' in result:
                        url = result['link']
                        if _is_individual_job_url(url):
                            job_urls.append(url)
                            logger.info(f"✅ Added job URL: {url}")
        else:
            logger.info("📝 Processing string search results...")
            search_text = str(search_context)
        
        # Patterns for individual job URLs
        individual_job_patterns = [
            r'https://www\.indeed\.com/viewjob\?jk=[a-f0-9]+',
            r'https://[a-z]*\.?linkedin\.com/jobs/view/[a-zA-Z0-9\-]+',
            r'https://www\.dice\.com/jobs/detail/[a-zA-Z0-9\-]+',
            r'https://www\.flexjobs\.com/jobs/[a-zA-Z0-9\-]+',
            r'https://www\.upwork\.com/freelance-jobs/apply/[a-zA-Z0-9\-_]+'
        ]
        
        logger.info("🔎 Scanning for job URLs with regex patterns...")
        # Extract URLs using regex patterns
        for pattern in individual_job_patterns:
            matches = re.findall(pattern, search_text)
            for match in matches:
                if match not in job_urls:
                    job_urls.append(match)
                    logger.info(f"✅ Found job URL: {match}")
        
        # Also try to parse JSON and extract from 'link' fields
        try:
            # Look for JSON-like structures in the context
            json_matches = re.findall(r'\{[^}]*"link":\s*"([^"]+)"[^}]*\}', search_text)
            for url in json_matches:
                # Check if it's an individual job URL
                if _is_individual_job_url(url) and url not in job_urls:
                    job_urls.append(url)
                    logger.info(f"✅ Extracted job URL from JSON: {url}")
        except:
            pass
        
        # Remove duplicates and filter valid job URLs
        unique_urls = []
        for url in job_urls:
            if url not in unique_urls:
                # Skip search pages and general listing pages
                if not any(skip in url for skip in ['/jobs?q=', 'jobs-', '/jobs/q-', '/m/jobs?q=']):
                    unique_urls.append(url)
        
        logger.info(f"🎯 Final result: Found {len(unique_urls)} unique individual job URLs")
        
        result = {
            'individual_job_urls': unique_urls,
            'count': len(unique_urls)
        }
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"❌ Error extracting job URLs: {e}")
        return json.dumps({
            'individual_job_urls': [],
            'count': 0,
            'error': str(e)
        })

@tool
def extract_job_urls_from_search_results(search_context: str) -> str:
    """Extract individual job posting URLs from search results context"""
    return _extract_job_urls_implementation(search_context)

def _is_individual_job_url(url):
    """Helper function to check if URL is an individual job posting"""
    job_indicators = [
        'viewjob?jk=',
        '/jobs/view/',
        'jobs/detail/',
        '/freelance-jobs/apply/',
        '/job_',
        '/position/'
    ]
    return any(indicator in url for indicator in job_indicators)

def _validate_job_url_implementation(url: str) -> bool:
    """Internal implementation for job URL validation"""
    try:
        if not url or url.startswith('#') or 'example.com' in url:
            return False
        
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return False
        
        # Check if it's a job-related URL
        job_indicators = ['job', 'career', 'position', 'opening', 'hiring']
        url_lower = url.lower()
        
        return any(indicator in url_lower for indicator in job_indicators)
        
    except Exception:
        return False

@tool
def validate_job_url(url: str) -> bool:
    """Validate that a URL is a legitimate job posting"""
    return _validate_job_url_implementation(url)

class DrupalJobSearchCrew:
    """
    Cost-optimized CrewAI implementation for Drupal job searching.
    
    Uses different LLM models based on agent complexity:
    - Search Agent: gpt-3.5-turbo (90% cost savings vs GPT-4)
    - Analysis Agent: gpt-4o (78% cost savings vs GPT-4) 
    - Report Agent: gpt-4o-mini (99% cost savings vs GPT-4)
    
    Total estimated savings: ~89% vs all-GPT-4 configuration
    """
    
    def __init__(self):
        self.config = JobSearchConfig()
        
        # Cost-optimized LLM configuration per agent complexity
        self.search_llm = ChatOpenAI(
            model="gpt-3.5-turbo",  # Cost-effective for search tasks
            temperature=0.1,
            openai_api_key=self.config.openai_api_key
        )
        
        self.analysis_llm = ChatOpenAI(
            model="gpt-4o",  # Balanced capability/cost for complex analysis
            temperature=0.1,
            openai_api_key=self.config.openai_api_key
        )
        
        self.report_llm = ChatOpenAI(
            model="gpt-4o-mini",  # Very cost-effective for formatting
            temperature=0.1,
            openai_api_key=self.config.openai_api_key
        )
        
        # Initialize search tools
        self.serper_tool = SerperDevTool(api_key=self.config.serper_api_key)
        
    def create_agents(self):
        """Create specialized agents for job searching"""
        
        # Job Board Search Agent
        job_searcher = Agent(
            role='Job Board Search Specialist',
            goal='Find Senior Drupal Developer contract positions on major job boards',
            backstory="""You are an expert at finding developer jobs across various job boards.
            You know how to craft effective search queries and identify relevant contract opportunities.
            You focus on senior-level Drupal positions in the United States.""",
            tools=[self.serper_tool, brave_search_tool],
            llm=self.search_llm,  # Using cost-effective gpt-3.5-turbo
            verbose=True
        )
        
        # Job Analysis Agent  
        job_analyzer = Agent(
            role='Job Listing Analyzer',
            goal='Extract real job details from job posting URLs using browser automation to bypass anti-bot protection',
            backstory="""You are an expert at extracting detailed information from job posting URLs using 
            advanced browser automation that mimics human behavior. You use realistic browser automation 
            with human-like delays, scrolling, and behavior patterns to bypass anti-bot protection systems.
            You NEVER make up or hallucinate job data - you only work with real extracted information 
            from actual job posting websites accessed through automated browsers.""",
            tools=[extract_job_urls_from_search_results, extract_job_details_browser_tool, validate_job_url],
            llm=self.analysis_llm,  # Using balanced gpt-4o for complex analysis
            verbose=True
        )
        
        # Report Generator Agent
        report_generator = Agent(
            role='Job Report Specialist',
            goal='Generate comprehensive daily reports of new Drupal job opportunities',
            backstory="""You create detailed, well-organized reports of job opportunities.
            You format information clearly and provide actionable insights for job seekers.""",
            tools=[],
            llm=self.report_llm,  # Using very cost-effective gpt-4o-mini for formatting
            verbose=True
        )
        
        return job_searcher, job_analyzer, report_generator
    
    def create_tasks(self, job_searcher, job_analyzer, report_generator):
        """Create tasks for the crew"""
        
        search_queries = []
        for keyword in self.config.job_keywords:
            for board in self.config.job_boards:
                search_queries.append(f'"{keyword}" site:{board} contract remote USA')
        
        # Task 1: Search for jobs
        search_task = Task(
            description=f"""
            Search for Senior Drupal Developer contract jobs using these queries:
            {chr(10).join(search_queries)}
            
            Focus on:
            - Contract/freelance positions
            - Senior level roles (3+ years experience)
            - Remote or US-based positions
            - Posted within the last week
            
            Extract:
            - Job title
            - Company name
            - Location
            - Job URL
            - Brief description
            - Posted date
            - Salary/rate if available
            """,
            agent=job_searcher,
            expected_output="List of job search results with detailed information for each position found"
        )
        
        # Task 2: Extract real job details and analyze
        analysis_task = Task(
            description="""
            CRITICAL: Extract REAL job details from INDIVIDUAL job posting URLs found in the search results. 
            DO NOT make up or hallucinate any job information.
            
            Step 1 - EXTRACT INDIVIDUAL JOB URLs FROM SEARCH CONTEXT:
            1. Use extract_job_urls_from_search_results tool with the full search results context
            2. This will return a JSON with individual job URLs that need to be processed
            3. The tool will filter out search pages and only return individual job posting URLs
            
            Step 2 - PROCESS EACH INDIVIDUAL JOB URL:
            For EACH URL returned by the extraction tool:
            1. Use validate_job_url tool to verify the URL is valid
            2. Use extract_job_details_browser_tool to get real job information using browser automation
            3. Only include jobs with successfully extracted data (non-empty title and company)
            
            Step 3 - ANALYZE AND SCORE EXTRACTED JOBS:
            For each successfully extracted job:
            - Check if it mentions Drupal specifically in title or description
            - Verify it's a contract/freelance role (not full-time permanent)
            - Confirm it's senior level (3+ years experience)
            - Assign relevance score (1-10) based on actual extracted content
            - Include actual job data: title, company, location, URL, description snippet
            
            WORKFLOW EXAMPLE:
            1. Call extract_job_urls_from_search_results(search_context) -> gets list of individual job URLs
            2. For each URL: call extract_job_details_browser_tool(url) -> gets real job data
            3. Analyze the real extracted data for Drupal relevance and scoring
            
            IMPORTANT: 
            - Use ALL individual job URLs found by the extraction tool
            - Only report jobs with real extracted data (not empty/error responses)
            - Include the actual extracted job details in your output
            """,
            agent=job_analyzer,
            context=[search_task],
            expected_output="List of real jobs with extracted data including: title, company, location, URL, relevance score, and Drupal-related analysis"
        )
        
        # Task 3: Generate daily report with real data only
        report_task = Task(
            description="""
            Create a comprehensive daily report using ONLY the real job data extracted from actual job postings.
            DO NOT add any fictional or placeholder information.
            
            Use ONLY the actual extracted job data from the analysis task. If no real jobs were found, 
            report that honestly.
            
            Report structure:
            1. Executive Summary (actual number of real jobs found)
            2. High Priority Jobs (score 8-10) - with real company names and URLs
            3. Medium Priority Jobs (score 6-7) - with real company names and URLs
            4. Job Market Insights (based on actual extracted data)
            
            For each REAL job include:
            - Actual job title (from extracted data)
            - Real company name (from extracted data)
            - Actual location (from extracted data)
            - Real salary/rate information (from extracted data, or "Not specified" if not found)
            - Current date as search date
            - Actual working job URL (from extracted data)
            
            CRITICAL: Only include jobs with real extracted data. Do not use placeholder companies like 
            "Company A", "Company B" or fake URLs like "#" or "Apply Here". If no real jobs were 
            extracted, report "No real job opportunities found that could be extracted from job posting URLs."
            """,
            agent=report_generator,
            context=[analysis_task],
            expected_output="Professional daily report with only real extracted job data, no placeholders or fictional content"
        )
        
        return [search_task, analysis_task, report_task]
    
    def run_daily_search(self):
        """Execute the daily job search"""
        logger.info("🚀 Starting daily Drupal job search...")
        
        try:
            # Create agents and tasks
            logger.info("👥 Creating specialized agents...")
            job_searcher, job_analyzer, report_generator = self.create_agents()
            logger.info("✅ Created 3 agents: Search Specialist, Job Analyzer, Report Generator")
            
            logger.info("📋 Creating tasks...")
            tasks = self.create_tasks(job_searcher, job_analyzer, report_generator)
            logger.info(f"✅ Created {len(tasks)} tasks for the crew")
            
            # Create and run crew
            logger.info("🤖 Initializing CrewAI with sequential processing...")
            crew = Crew(
                agents=[job_searcher, job_analyzer, report_generator],
                tasks=tasks,
                process=Process.sequential,
                verbose=True
            )
            
            logger.info("🎬 Starting CrewAI execution...")
            logger.info("📊 Task 1: Job Board Search Specialist will search for positions")
            logger.info("🔍 Task 2: Job Analyzer will extract real job details")
            logger.info("📝 Task 3: Report Generator will create final report")
            
            # Execute the crew
            result = crew.kickoff()
            
            # Save report
            logger.info("💾 Saving report to file...")
            self.save_report(result)
            
            logger.info("🎉 Daily job search completed successfully!")
            return result
            
        except Exception as e:
            logger.error(f"❌ Error during job search: {e}")
            raise
    
    def save_report(self, report_content):
        """Save the daily report to file"""
        today = datetime.now().strftime("%Y-%m-%d")
        filename = f"drupal_jobs_report_{today}.md"
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(f"# Daily Drupal Jobs Report - {today}\n\n")
            f.write(str(report_content))
        
        logger.info(f"Report saved to {filename}")

def main():
    """Main function to run the job search"""
    try:
        # Initialize the job search crew
        search_crew = DrupalJobSearchCrew()
        
        # Run daily search
        report = search_crew.run_daily_search()
        
        print("\n" + "="*50)
        print("DAILY DRUPAL JOBS SEARCH COMPLETED")
        print("="*50)
        print(report)
        
    except Exception as e:
        logger.error(f"Script failed: {e}")
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
