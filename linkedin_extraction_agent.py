#!/usr/bin/env python3
"""
LinkedIn Extraction Agent - Specialized agent for extracting job data from LinkedIn
Part of the asynchronous multi-agent job search system
"""

import asyncio
import json
import logging
import re
from typing import Dict, List, Any, Optional
from datetime import datetime
from crewai.tools import tool
from urllib.parse import urlparse, parse_qs

from async_agent_base import ExtractionAgentBase
from task_manager import Task, TaskType, TaskStatus
from browser_pool_manager import BrowserPoolManager

logger = logging.getLogger(__name__)

class LinkedInExtractionAgent(ExtractionAgentBase):
    """Specialized agent for extracting job data from LinkedIn with anti-detection measures"""
    
    def __init__(self, agent_id: str = None, browser_pool: Optional[BrowserPoolManager] = None, **kwargs):
        if not agent_id:
            agent_id = f"linkedin-extract-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="LinkedIn",
            **kwargs
        )
        
        self.browser_pool = browser_pool
        
        # LinkedIn-specific selectors
        self.selectors = {
            'job_title': [
                'h1.t-24.t-bold.inline',
                '.jobs-unified-top-card__job-title h1',
                '.job-details-jobs-unified-top-card__job-title h1',
                'h1[data-automation-id="jobPostingHeader"]'
            ],
            'company_name': [
                '.jobs-unified-top-card__company-name a',
                '.job-details-jobs-unified-top-card__company-name a',
                '.jobs-unified-top-card__subtitle-primary-grouping a',
                'a[data-automation-id="jobPostingCompanyLink"]'
            ],
            'location': [
                '.jobs-unified-top-card__bullet',
                '.job-details-jobs-unified-top-card__primary-description-container .t-black--light',
                '.jobs-unified-top-card__subtitle-secondary-grouping',
                '[data-automation-id="jobPostingLocation"]'
            ],
            'job_description': [
                '.jobs-description-content__text',
                '.jobs-box__html-content',
                '.job-view-layout .jobs-description',
                '[data-automation-id="jobPostingDescription"]'
            ],
            'employment_type': [
                '.jobs-unified-top-card__job-insight span',
                '.job-details-jobs-unified-top-card__job-insight span',
                '.jobs-unified-top-card__subtitle-secondary-grouping span'
            ],
            'seniority_level': [
                '.jobs-unified-top-card__job-insight span',
                '.job-details-jobs-unified-top-card__job-insight span'
            ],
            'posted_date': [
                '.jobs-unified-top-card__posted-date',
                '.job-details-jobs-unified-top-card__posted-date',
                'time[datetime]'
            ],
            'applicant_count': [
                '.jobs-unified-top-card__applicant-count',
                '.job-details-jobs-unified-top-card__applicant-count'
            ]
        }
        
        # LinkedIn domains and patterns
        self.linkedin_domains = {'linkedin.com', 'www.linkedin.com'}
        self.job_url_patterns = [
            r'linkedin\.com/jobs/view/(\d+)',
            r'linkedin\.com/jobs/collections/.*?/(\d+)',
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.EXTRACT_LINKEDIN]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process LinkedIn extraction task"""
        if task.type != TaskType.EXTRACT_LINKEDIN:
            raise ValueError(f"LinkedInExtractionAgent cannot handle task type {task.type}")
        
        url = task.data.get('url', '')
        if not self._is_linkedin_job_url(url):
            raise ValueError(f"Invalid LinkedIn job URL: {url}")
        
        logger.info(f"🔍 Extracting LinkedIn job: {url}")
        
        try:
            # Extract job data using browser pool
            job_data = await self._extract_job_data_with_browser(url)
            
            # Validate and enhance extracted data
            validated_data = self._validate_and_enhance_data(job_data, url)
            
            return {
                'platform': 'linkedin',
                'url': url,
                'extraction_successful': True,
                'job_data': validated_data,
                'agent_id': self.agent_id,
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ LinkedIn extraction failed for {url}: {e}")
            return {
                'platform': 'linkedin',
                'url': url,
                'extraction_successful': False,
                'error': str(e),
                'agent_id': self.agent_id,
                'extracted_at': datetime.now().isoformat()
            }

    async def _extract_job_data_with_browser(self, url: str) -> Dict[str, Any]:
        """Extract job data using browser automation"""
        if not self.browser_pool:
            raise RuntimeError("Browser pool not available for extraction")
        
        domain_restrictions = self.linkedin_domains
        
        async with self.browser_pool.get_page(url, domain_restrictions) as page:
            # Navigate to job page
            response = await page.goto(url, wait_until='networkidle')
            
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status} error for {url}")
            
            # Wait for key elements to load
            try:
                await page.wait_for_selector('h1', timeout=10000)
            except:
                logger.warning(f"Timeout waiting for job title on {url}")
            
            # Handle LinkedIn login/gate if present
            await self._handle_linkedin_gates(page)
            
            # Extract job data
            job_data = await self._extract_job_elements(page, url)
            
            return job_data

    async def _handle_linkedin_gates(self, page):
        """Handle LinkedIn login prompts and access gates"""
        try:
            # Check for login gate
            login_selectors = [
                '.guest-homepage',
                '.authwall',
                'form[data-automation-id="signInForm"]'
            ]
            
            for selector in login_selectors:
                if await page.query_selector(selector):
                    logger.warning("LinkedIn login gate detected - limited extraction possible")
                    break
            
            # Check for "Join LinkedIn" prompts
            join_prompts = await page.query_selector_all('button:has-text("Join now")')
            if join_prompts:
                logger.warning("LinkedIn join prompt detected")
            
            # Wait a bit for dynamic content
            await asyncio.sleep(2)
            
        except Exception as e:
            logger.warning(f"Error handling LinkedIn gates: {e}")

    async def _extract_job_elements(self, page, url: str) -> Dict[str, Any]:
        """Extract individual job elements from the page"""
        job_data = {
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'employment_type': '',
            'seniority_level': '',
            'posted_date': '',
            'applicant_count': '',
            'linkedin_job_id': self._extract_job_id_from_url(url),
            'skills_required': [],
            'benefits': [],
            'raw_html_snippet': ''
        }
        
        # Extract title
        job_data['title'] = await self._extract_text_by_selectors(page, self.selectors['job_title'])
        
        # Extract company
        company_element = await self._extract_element_by_selectors(page, self.selectors['company_name'])
        if company_element:
            job_data['company'] = await company_element.text_content()
            job_data['company'] = job_data['company'].strip()
        
        # Extract location
        location_text = await self._extract_text_by_selectors(page, self.selectors['location'])
        job_data['location'] = self._clean_location_text(location_text)
        
        # Extract description
        job_data['description'] = await self._extract_text_by_selectors(page, self.selectors['job_description'])
        
        # Extract employment type and seniority
        insights = await self._extract_job_insights(page)
        job_data.update(insights)
        
        # Extract posted date
        posted_date = await self._extract_posted_date(page)
        job_data['posted_date'] = posted_date
        
        # Extract applicant count
        job_data['applicant_count'] = await self._extract_text_by_selectors(page, self.selectors['applicant_count'])
        
        # Extract skills from description
        job_data['skills_required'] = self._extract_skills_from_description(job_data['description'])
        
        # Get raw HTML snippet for debugging
        try:
            body_html = await page.evaluate('() => document.body.innerHTML')
            job_data['raw_html_snippet'] = body_html[:1000] + '...' if len(body_html) > 1000 else body_html
        except:
            pass
        
        return job_data

    async def _extract_text_by_selectors(self, page, selectors: List[str]) -> str:
        """Try multiple selectors to extract text content"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    text = await element.text_content()
                    if text and text.strip():
                        return text.strip()
            except Exception as e:
                logger.debug(f"Selector failed {selector}: {e}")
                continue
        return ''

    async def _extract_element_by_selectors(self, page, selectors: List[str]):
        """Try multiple selectors to extract element"""
        for selector in selectors:
            try:
                element = await page.query_selector(selector)
                if element:
                    return element
            except Exception as e:
                logger.debug(f"Selector failed {selector}: {e}")
                continue
        return None

    async def _extract_job_insights(self, page) -> Dict[str, str]:
        """Extract employment type, seniority level, and other insights"""
        insights = {
            'employment_type': '',
            'seniority_level': '',
            'industry': '',
            'function': ''
        }
        
        try:
            # Look for insights container
            insight_selectors = [
                '.jobs-unified-top-card__job-insight',
                '.job-details-jobs-unified-top-card__job-insight',
                '.jobs-unified-top-card__subtitle-secondary-grouping'
            ]
            
            for selector in insight_selectors:
                elements = await page.query_selector_all(f'{selector} span')
                
                for element in elements:
                    text = await element.text_content()
                    text = text.strip() if text else ''
                    
                    if not text:
                        continue
                    
                    # Classify the insight
                    text_lower = text.lower()
                    
                    if any(term in text_lower for term in ['full-time', 'part-time', 'contract', 'temporary', 'internship']):
                        insights['employment_type'] = text
                    elif any(term in text_lower for term in ['entry level', 'associate', 'mid-senior', 'director', 'executive']):
                        insights['seniority_level'] = text
                    elif any(term in text_lower for term in ['technology', 'healthcare', 'finance', 'education']):
                        insights['industry'] = text
                    elif any(term in text_lower for term in ['engineering', 'marketing', 'sales', 'operations']):
                        insights['function'] = text
        
        except Exception as e:
            logger.debug(f"Error extracting job insights: {e}")
        
        return insights

    async def _extract_posted_date(self, page) -> str:
        """Extract and normalize posted date"""
        try:
            # Try datetime attribute first
            time_elements = await page.query_selector_all('time[datetime]')
            for element in time_elements:
                datetime_value = await element.get_attribute('datetime')
                if datetime_value:
                    return datetime_value
            
            # Fall back to text content
            date_text = await self._extract_text_by_selectors(page, self.selectors['posted_date'])
            
            if date_text:
                # Normalize common LinkedIn date formats
                date_text = date_text.lower().strip()
                
                if 'ago' in date_text:
                    return self._parse_relative_date(date_text)
                else:
                    return date_text
        
        except Exception as e:
            logger.debug(f"Error extracting posted date: {e}")
        
        return ''

    def _parse_relative_date(self, date_text: str) -> str:
        """Parse relative dates like '2 days ago' into ISO format"""
        try:
            from datetime import timedelta
            
            now = datetime.now()
            
            if 'hour' in date_text:
                hours = int(re.search(r'(\d+)', date_text).group(1))
                date = now - timedelta(hours=hours)
            elif 'day' in date_text:
                days = int(re.search(r'(\d+)', date_text).group(1))
                date = now - timedelta(days=days)
            elif 'week' in date_text:
                weeks = int(re.search(r'(\d+)', date_text).group(1))
                date = now - timedelta(weeks=weeks)
            elif 'month' in date_text:
                months = int(re.search(r'(\d+)', date_text).group(1))
                date = now - timedelta(days=months * 30)
            else:
                return date_text
            
            return date.date().isoformat()
            
        except Exception:
            return date_text

    def _clean_location_text(self, location: str) -> str:
        """Clean and normalize location text"""
        if not location:
            return ''
        
        # Remove extra whitespace and bullet points
        location = re.sub(r'[•·]', '', location)
        location = re.sub(r'\s+', ' ', location)
        location = location.strip()
        
        # Extract main location (remove secondary info)
        if '(' in location:
            location = location.split('(')[0].strip()
        
        return location

    def _extract_skills_from_description(self, description: str) -> List[str]:
        """Extract skills mentioned in job description"""
        if not description:
            return []
        
        drupal_skills = []
        description_lower = description.lower()
        
        # Common Drupal/web development skills
        skill_patterns = {
            'drupal': ['drupal', 'drupal 8', 'drupal 9', 'drupal 10'],
            'php': ['php', 'php 7', 'php 8'],
            'cms': ['cms', 'content management'],
            'mysql': ['mysql', 'mariadb'],
            'javascript': ['javascript', 'js', 'jquery'],
            'css': ['css', 'css3', 'sass', 'scss'],
            'html': ['html', 'html5'],
            'git': ['git', 'version control'],
            'linux': ['linux', 'ubuntu', 'centos'],
            'apache': ['apache', 'nginx'],
            'composer': ['composer'],
            'twig': ['twig'],
            'symfony': ['symfony'],
            'api': ['api', 'rest api', 'graphql'],
            'docker': ['docker', 'containerization'],
            'aws': ['aws', 'amazon web services']
        }
        
        for skill_category, patterns in skill_patterns.items():
            for pattern in patterns:
                if pattern in description_lower:
                    drupal_skills.append(skill_category)
                    break
        
        return drupal_skills

    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract LinkedIn job ID from URL"""
        for pattern in self.job_url_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return ''

    def _is_linkedin_job_url(self, url: str) -> bool:
        """Check if URL is a valid LinkedIn job URL"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc.lower() in self.linkedin_domains and
                    '/jobs/' in parsed.path and
                    any(re.search(pattern, url) for pattern in self.job_url_patterns))
        except:
            return False

    def _validate_and_enhance_data(self, job_data: Dict[str, Any], url: str) -> Dict[str, Any]:
        """Validate and enhance extracted job data"""
        validated_data = job_data.copy()
        
        # Ensure required fields
        required_fields = ['title', 'company', 'description']
        for field in required_fields:
            if not validated_data.get(field):
                logger.warning(f"Missing required field '{field}' for {url}")
        
        # Add metadata
        validated_data.update({
            'source_url': url,
            'extraction_agent': self.agent_id,
            'platform': 'linkedin',
            'extracted_at': datetime.now().isoformat(),
            'data_quality_score': self._calculate_data_quality_score(validated_data)
        })
        
        # Clean up text fields
        text_fields = ['title', 'company', 'location', 'description', 'employment_type']
        for field in text_fields:
            if validated_data.get(field):
                validated_data[field] = self._clean_text(validated_data[field])
        
        return validated_data

    def _calculate_data_quality_score(self, job_data: Dict[str, Any]) -> float:
        """Calculate data quality score (0-10)"""
        score = 0.0
        
        # Required fields
        if job_data.get('title'):
            score += 3.0
        if job_data.get('company'):
            score += 2.0
        if job_data.get('description') and len(job_data['description']) > 100:
            score += 2.0
        
        # Optional but valuable fields
        if job_data.get('location'):
            score += 1.0
        if job_data.get('employment_type'):
            score += 0.5
        if job_data.get('posted_date'):
            score += 0.5
        if job_data.get('skills_required'):
            score += 1.0
        
        return min(score, 10.0)

    def _clean_text(self, text: str) -> str:
        """Clean and normalize text content"""
        if not text:
            return ''
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        
        # Remove common artifacts
        text = re.sub(r'[\u200b\u200c\u200d\ufeff]', '', text)  # Zero-width characters
        
        return text

    @tool
    def extract_job_data(self, url: str) -> str:
        """Extract job data from LinkedIn URL - CrewAI tool interface"""
        try:
            if not self._is_linkedin_job_url(url):
                return json.dumps({
                    "error": "Invalid LinkedIn job URL",
                    "url": url,
                    "platform": "linkedin"
                })
            
            # Note: This is a synchronous tool interface
            # In practice, this would need to be called from an async context
            return json.dumps({
                "platform": "linkedin",
                "url": url,
                "status": "extraction_queued",
                "message": "Job extraction queued for processing"
            })
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url,
                "platform": "linkedin"
            })

    @tool
    def validate_job_data(self, job_data: str) -> str:
        """Validate LinkedIn job data - CrewAI tool interface"""
        try:
            data = json.loads(job_data)
            
            # Check required fields
            required_fields = ['title', 'company', 'url']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            # LinkedIn-specific validation
            is_valid_url = self._is_linkedin_job_url(data.get('url', ''))
            has_drupal_content = 'drupal' in data.get('description', '').lower()
            
            quality_score = self._calculate_data_quality_score(data)
            
            return json.dumps({
                "valid": len(missing_fields) == 0 and is_valid_url,
                "platform": "linkedin",
                "missing_fields": missing_fields,
                "linkedin_url_valid": is_valid_url,
                "drupal_relevant": has_drupal_content,
                "data_quality_score": quality_score,
                "job_data": data
            })
            
        except Exception as e:
            return json.dumps({
                "valid": False,
                "error": str(e),
                "platform": "linkedin"
            })

if __name__ == "__main__":
    # Test the LinkedIn extraction agent
    async def test_linkedin_extraction():
        print("🧪 Testing LinkedIn Extraction Agent...")
        
        # Mock browser pool for testing
        class MockBrowserPool:
            async def get_page(self, url, domain_restrictions=None):
                return MockPage()
        
        class MockPage:
            async def goto(self, url, **kwargs):
                class MockResponse:
                    status = 200
                return MockResponse()
            
            async def wait_for_selector(self, selector, **kwargs):
                pass
            
            async def query_selector(self, selector):
                return MockElement()
            
            async def query_selector_all(self, selector):
                return [MockElement()]
            
            async def evaluate(self, script):
                return "<html>Mock HTML content</html>"
        
        class MockElement:
            async def text_content(self):
                return "Mock Text Content"
            
            async def get_attribute(self, attr):
                return "2024-01-01"
        
        mock_browser_pool = MockBrowserPool()
        agent = LinkedInExtractionAgent(browser_pool=mock_browser_pool)
        
        # Test URL validation
        valid_url = "https://linkedin.com/jobs/view/123456789"
        invalid_url = "https://example.com/job/123"
        
        print(f"📊 URL Validation:")
        print(f"  - Valid LinkedIn URL: {agent._is_linkedin_job_url(valid_url)}")
        print(f"  - Invalid URL: {agent._is_linkedin_job_url(invalid_url)}")
        
        # Test skill extraction
        description = "We are looking for a Senior Drupal Developer with experience in PHP, MySQL, JavaScript, and Git version control."
        skills = agent._extract_skills_from_description(description)
        print(f"\n🔧 Skills Extracted: {skills}")
        
        # Test data quality scoring
        job_data = {
            'title': 'Senior Drupal Developer',
            'company': 'Tech Company Inc',
            'description': description,
            'location': 'Remote, USA',
            'employment_type': 'Full-time'
        }
        
        quality_score = agent._calculate_data_quality_score(job_data)
        print(f"\n📈 Data Quality Score: {quality_score}/10")
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ LinkedIn Extraction Agent test completed!")
    
    asyncio.run(test_linkedin_extraction())