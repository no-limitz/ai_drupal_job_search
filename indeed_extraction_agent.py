#!/usr/bin/env python3
"""
Indeed Extraction Agent - Specialized agent for extracting job data from Indeed
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

class IndeedExtractionAgent(ExtractionAgentBase):
    """Specialized agent for extracting job data from Indeed with robust parsing"""
    
    def __init__(self, agent_id: str = None, browser_pool: Optional[BrowserPoolManager] = None, **kwargs):
        if not agent_id:
            agent_id = f"indeed-extract-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="Indeed",
            **kwargs
        )
        
        self.browser_pool = browser_pool
        
        # Indeed-specific selectors
        self.selectors = {
            'job_title': [
                'h1[data-testid="jobsearch-JobInfoHeader-title"]',
                '.jobsearch-JobInfoHeader-title',
                'h1.icl-u-xs-mb--xs.icl-u-xs-mt--none',
                '.jobsearch-JobInfoHeader-title span[title]'
            ],
            'company_name': [
                '[data-testid="inlineHeader-companyName"] a',
                '.jobsearch-InlineCompanyRating .jobsearch-InlineCompanyRating-companyHeader a',
                '.icl-u-lg-mr--sm.icl-u-xs-mr--xs a[data-jk]',
                'a[data-testid="company-name"]'
            ],
            'location': [
                '[data-testid="job-location"]',
                '.jobsearch-JobInfoHeader-subtitle div',
                '.icl-u-colorForeground--secondary.icl-u-xs-mt--xs',
                '.jobsearch-JobInfoHeader-subtitle .icl-u-xs-mt--xs'
            ],
            'job_description': [
                '#jobDescriptionText',
                '.jobsearch-jobDescriptionText',
                '.jobsearch-JobComponent-description',
                '[data-testid="jobsearch-JobComponent-description"]'
            ],
            'salary': [
                '.icl-u-xs-mr--xs .attribute_snippet',
                '.jobsearch-JobInfoHeader-subtitle .attribute_snippet',
                '[data-testid="job-salary"]',
                '.salary-snippet'
            ],
            'employment_type': [
                '.jobsearch-JobInfoHeader-subtitle .icl-u-xs-mt--xs',
                '.jobsearch-JobDescriptionSection-sectionItem .icl-u-lg-mr--sm'
            ],
            'benefits': [
                '.jobsearch-JobDescriptionSection-benefits',
                '.jobsearch-benefits',
                '[data-testid="job-benefits"]'
            ],
            'company_rating': [
                '.icl-Ratings--gold .icl-Ratings-starsCountWrapper',
                '[data-testid="company-rating"]',
                '.jobsearch-InlineCompanyRating .icl-Ratings-starsCountWrapper'
            ],
            'job_type_badges': [
                '.jobsearch-JobInfoHeader-subtitle .jobsearch-JobInfoHeader-subtitle-item',
                '.attribute_snippet'
            ]
        }
        
        # Indeed domains and patterns
        self.indeed_domains = {'indeed.com', 'www.indeed.com', 'indeed.ca', 'indeed.co.uk'}
        self.job_url_patterns = [
            r'indeed\.com/viewjob\?jk=([a-zA-Z0-9]+)',
            r'indeed\.com/jobs/view/([a-zA-Z0-9]+)',
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.EXTRACT_INDEED]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process Indeed extraction task"""
        if task.type != TaskType.EXTRACT_INDEED:
            raise ValueError(f"IndeedExtractionAgent cannot handle task type {task.type}")
        
        url = task.data.get('url', '')
        if not self._is_indeed_job_url(url):
            raise ValueError(f"Invalid Indeed job URL: {url}")
        
        logger.info(f"🔍 Extracting Indeed job: {url}")
        
        try:
            # Extract job data using browser pool
            job_data = await self._extract_job_data_with_browser(url)
            
            # Validate and enhance extracted data
            validated_data = self._validate_and_enhance_data(job_data, url)
            
            return {
                'platform': 'indeed',
                'url': url,
                'extraction_successful': True,
                'job_data': validated_data,
                'agent_id': self.agent_id,
                'extracted_at': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Indeed extraction failed for {url}: {e}")
            return {
                'platform': 'indeed',
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
        
        domain_restrictions = self.indeed_domains
        
        async with self.browser_pool.get_page(url, domain_restrictions) as page:
            # Navigate to job page
            response = await page.goto(url, wait_until='domcontentloaded')
            
            if response.status >= 400:
                raise RuntimeError(f"HTTP {response.status} error for {url}")
            
            # Wait for key elements to load
            try:
                await page.wait_for_selector('h1', timeout=10000)
            except:
                logger.warning(f"Timeout waiting for job title on {url}")
            
            # Handle Indeed overlays and modals
            await self._handle_indeed_overlays(page)
            
            # Extract job data
            job_data = await self._extract_job_elements(page, url)
            
            return job_data

    async def _handle_indeed_overlays(self, page):
        """Handle Indeed popups, modals, and overlays"""
        try:
            # Close popup modals
            close_selectors = [
                'button[aria-label="close"]',
                '.icl-CloseButton',
                '.pn-CloseButton',
                'button[data-testid="close-button"]'
            ]
            
            for selector in close_selectors:
                close_button = await page.query_selector(selector)
                if close_button:
                    await close_button.click()
                    await asyncio.sleep(0.5)
            
            # Handle cookie consent
            cookie_selectors = [
                'button[id*="cookie"]',
                'button:has-text("Accept")',
                'button:has-text("OK")'
            ]
            
            for selector in cookie_selectors:
                cookie_button = await page.query_selector(selector)
                if cookie_button:
                    await cookie_button.click()
                    await asyncio.sleep(0.5)
                    break
            
            # Wait for overlays to disappear
            await asyncio.sleep(1)
            
        except Exception as e:
            logger.warning(f"Error handling Indeed overlays: {e}")

    async def _extract_job_elements(self, page, url: str) -> Dict[str, Any]:
        """Extract individual job elements from the page"""
        job_data = {
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'employment_type': '',
            'benefits': [],
            'company_rating': '',
            'indeed_job_id': self._extract_job_id_from_url(url),
            'skills_required': [],
            'posted_date': '',
            'application_url': url,
            'indeed_apply': False,
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
        job_data['location'] = await self._extract_text_by_selectors(page, self.selectors['location'])
        
        # Extract description
        job_data['description'] = await self._extract_description(page)
        
        # Extract salary
        job_data['salary'] = await self._extract_salary(page)
        
        # Extract employment type and job details
        job_details = await self._extract_job_details(page)
        job_data.update(job_details)
        
        # Extract company rating
        job_data['company_rating'] = await self._extract_company_rating(page)
        
        # Extract benefits
        job_data['benefits'] = await self._extract_benefits(page)
        
        # Check for Indeed Apply
        job_data['indeed_apply'] = await self._check_indeed_apply(page)
        
        # Extract skills from description
        job_data['skills_required'] = self._extract_skills_from_description(job_data['description'])
        
        # Get raw HTML snippet for debugging
        try:
            snippet = await page.evaluate('() => document.querySelector("#jobDescriptionText")?.innerHTML || document.body.innerHTML.slice(0, 1000)')
            job_data['raw_html_snippet'] = snippet[:1000] + '...' if len(snippet) > 1000 else snippet
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

    async def _extract_description(self, page) -> str:
        """Extract job description with fallback methods"""
        description = await self._extract_text_by_selectors(page, self.selectors['job_description'])
        
        if not description:
            # Try alternative extraction methods
            try:
                description = await page.evaluate('''
                    () => {
                        const desc = document.querySelector('#jobDescriptionText') || 
                                   document.querySelector('.jobsearch-jobDescriptionText') ||
                                   document.querySelector('.jobsearch-JobComponent-description');
                        return desc ? desc.textContent : '';
                    }
                ''')
            except:
                pass
        
        return description.strip() if description else ''

    async def _extract_salary(self, page) -> str:
        """Extract salary information"""
        salary = await self._extract_text_by_selectors(page, self.selectors['salary'])
        
        if not salary:
            # Look for salary in job header
            try:
                salary_elements = await page.query_selector_all('.attribute_snippet')
                for element in salary_elements:
                    text = await element.text_content()
                    if text and ('$' in text or 'hour' in text.lower() or 'year' in text.lower()):
                        salary = text.strip()
                        break
            except:
                pass
        
        return self._clean_salary_text(salary)

    async def _extract_job_details(self, page) -> Dict[str, str]:
        """Extract employment type and other job details"""
        details = {
            'employment_type': '',
            'experience_level': '',
            'posted_date': ''
        }
        
        try:
            # Look for job type badges and attributes
            badge_elements = await page.query_selector_all('.jobsearch-JobInfoHeader-subtitle-item')
            badge_elements.extend(await page.query_selector_all('.attribute_snippet'))
            
            for element in badge_elements:
                text = await element.text_content()
                text = text.strip().lower() if text else ''
                
                if any(term in text for term in ['full-time', 'part-time', 'contract', 'temporary']):
                    details['employment_type'] = text.title()
                elif any(term in text for term in ['entry level', 'senior', 'mid level', 'experienced']):
                    details['experience_level'] = text.title()
                elif any(term in text for term in ['ago', 'posted', 'day', 'hour']):
                    details['posted_date'] = text
        
        except Exception as e:
            logger.debug(f"Error extracting job details: {e}")
        
        return details

    async def _extract_company_rating(self, page) -> str:
        """Extract company rating"""
        try:
            rating_element = await self._extract_element_by_selectors(page, self.selectors['company_rating'])
            if rating_element:
                rating_text = await rating_element.text_content()
                # Extract numeric rating
                rating_match = re.search(r'(\d+\.?\d*)', rating_text)
                if rating_match:
                    return rating_match.group(1)
        except Exception as e:
            logger.debug(f"Error extracting company rating: {e}")
        
        return ''

    async def _extract_benefits(self, page) -> List[str]:
        """Extract job benefits"""
        benefits = []
        
        try:
            benefits_sections = await page.query_selector_all('.jobsearch-JobDescriptionSection-benefits')
            benefits_sections.extend(await page.query_selector_all('[data-testid="job-benefits"]'))
            
            for section in benefits_sections:
                benefit_items = await section.query_selector_all('li, .benefit-item')
                for item in benefit_items:
                    benefit_text = await item.text_content()
                    if benefit_text and benefit_text.strip():
                        benefits.append(benefit_text.strip())
        
        except Exception as e:
            logger.debug(f"Error extracting benefits: {e}")
        
        return benefits[:10]  # Limit to 10 benefits

    async def _check_indeed_apply(self, page) -> bool:
        """Check if job has Indeed Apply feature"""
        try:
            apply_selectors = [
                'button[data-testid="apply-button"]',
                '.indeed-apply-button',
                'button:has-text("Apply now")',
                '.ia-BasePage-button'
            ]
            
            for selector in apply_selectors:
                apply_button = await page.query_selector(selector)
                if apply_button:
                    return True
        
        except Exception as e:
            logger.debug(f"Error checking Indeed Apply: {e}")
        
        return False

    def _clean_salary_text(self, salary: str) -> str:
        """Clean and normalize salary text"""
        if not salary:
            return ''
        
        # Remove extra whitespace
        salary = re.sub(r'\s+', ' ', salary).strip()
        
        # Remove common prefixes
        salary = re.sub(r'^(salary:?|pay:?|compensation:?)\s*', '', salary, flags=re.IGNORECASE)
        
        return salary

    def _extract_skills_from_description(self, description: str) -> List[str]:
        """Extract skills mentioned in job description"""
        if not description:
            return []
        
        skills = []
        description_lower = description.lower()
        
        # Common tech skills relevant to Drupal jobs
        skill_patterns = {
            'drupal': ['drupal', 'drupal 8', 'drupal 9', 'drupal 10'],
            'php': ['php', 'php 7', 'php 8'],
            'cms': ['cms', 'content management'],
            'mysql': ['mysql', 'mariadb', 'database'],
            'javascript': ['javascript', 'js', 'jquery', 'ajax'],
            'css': ['css', 'css3', 'sass', 'scss', 'styling'],
            'html': ['html', 'html5', 'markup'],
            'git': ['git', 'version control', 'svn'],
            'linux': ['linux', 'ubuntu', 'server'],
            'apache': ['apache', 'nginx', 'web server'],
            'composer': ['composer', 'dependency management'],
            'twig': ['twig', 'templating'],
            'symfony': ['symfony', 'framework'],
            'api': ['api', 'rest', 'json', 'web services'],
            'docker': ['docker', 'container'],
            'aws': ['aws', 'cloud', 'amazon web services']
        }
        
        for skill_category, patterns in skill_patterns.items():
            for pattern in patterns:
                if pattern in description_lower:
                    skills.append(skill_category)
                    break
        
        return skills

    def _extract_job_id_from_url(self, url: str) -> str:
        """Extract Indeed job ID from URL"""
        for pattern in self.job_url_patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        
        # Try to extract from jk parameter
        try:
            parsed = urlparse(url)
            query_params = parse_qs(parsed.query)
            if 'jk' in query_params:
                return query_params['jk'][0]
        except:
            pass
        
        return ''

    def _is_indeed_job_url(self, url: str) -> bool:
        """Check if URL is a valid Indeed job URL"""
        try:
            parsed = urlparse(url)
            return (parsed.netloc.lower() in self.indeed_domains and
                    ('viewjob' in parsed.path or '/jobs/' in parsed.path))
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
            'platform': 'indeed',
            'extracted_at': datetime.now().isoformat(),
            'data_quality_score': self._calculate_data_quality_score(validated_data)
        })
        
        # Clean up text fields
        text_fields = ['title', 'company', 'location', 'description', 'employment_type', 'salary']
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
        
        # Indeed-specific valuable fields
        if job_data.get('location'):
            score += 1.0
        if job_data.get('salary'):
            score += 1.0
        if job_data.get('employment_type'):
            score += 0.5
        if job_data.get('company_rating'):
            score += 0.5
        
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
        """Extract job data from Indeed URL - CrewAI tool interface"""
        try:
            if not self._is_indeed_job_url(url):
                return json.dumps({
                    "error": "Invalid Indeed job URL",
                    "url": url,
                    "platform": "indeed"
                })
            
            return json.dumps({
                "platform": "indeed",
                "url": url,
                "status": "extraction_queued",
                "message": "Job extraction queued for processing"
            })
            
        except Exception as e:
            return json.dumps({
                "error": str(e),
                "url": url,
                "platform": "indeed"
            })

    @tool
    def validate_job_data(self, job_data: str) -> str:
        """Validate Indeed job data - CrewAI tool interface"""
        try:
            data = json.loads(job_data)
            
            # Check required fields
            required_fields = ['title', 'company', 'url']
            missing_fields = [field for field in required_fields if not data.get(field)]
            
            # Indeed-specific validation
            is_valid_url = self._is_indeed_job_url(data.get('url', ''))
            has_drupal_content = 'drupal' in data.get('description', '').lower()
            
            quality_score = self._calculate_data_quality_score(data)
            
            return json.dumps({
                "valid": len(missing_fields) == 0 and is_valid_url,
                "platform": "indeed",
                "missing_fields": missing_fields,
                "indeed_url_valid": is_valid_url,
                "drupal_relevant": has_drupal_content,
                "data_quality_score": quality_score,
                "indeed_apply_available": data.get('indeed_apply', False),
                "job_data": data
            })
            
        except Exception as e:
            return json.dumps({
                "valid": False,
                "error": str(e),
                "platform": "indeed"
            })

if __name__ == "__main__":
    # Test the Indeed extraction agent
    async def test_indeed_extraction():
        print("🧪 Testing Indeed Extraction Agent...")
        
        agent = IndeedExtractionAgent()
        
        # Test URL validation
        valid_url = "https://indeed.com/viewjob?jk=abc123def456"
        invalid_url = "https://example.com/job/123"
        
        print(f"📊 URL Validation:")
        print(f"  - Valid Indeed URL: {agent._is_indeed_job_url(valid_url)}")
        print(f"  - Invalid URL: {agent._is_indeed_job_url(invalid_url)}")
        
        # Test job ID extraction
        job_id = agent._extract_job_id_from_url(valid_url)
        print(f"  - Extracted Job ID: {job_id}")
        
        # Test skill extraction
        description = "We need a Drupal developer with PHP, MySQL, JavaScript, and Git experience for this contract position."
        skills = agent._extract_skills_from_description(description)
        print(f"\n🔧 Skills Extracted: {skills}")
        
        # Test salary cleaning
        dirty_salary = "  Salary: $75 - $95 per hour  "
        clean_salary = agent._clean_salary_text(dirty_salary)
        print(f"\n💰 Salary Cleaning: '{dirty_salary}' -> '{clean_salary}'")
        
        # Test data quality scoring
        job_data = {
            'title': 'Senior Drupal Developer',
            'company': 'Web Solutions Inc',
            'description': description,
            'location': 'Remote',
            'salary': '$75-95/hour',
            'employment_type': 'Contract'
        }
        
        quality_score = agent._calculate_data_quality_score(job_data)
        print(f"\n📈 Data Quality Score: {quality_score}/10")
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ Indeed Extraction Agent test completed!")
    
    asyncio.run(test_indeed_extraction())