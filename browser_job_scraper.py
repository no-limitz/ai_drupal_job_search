#!/usr/bin/env python3
"""
Browser-based job scraper that mimics human behavior to bypass anti-bot protection
Uses Playwright with stealth techniques and human-like patterns
"""

import asyncio
import random
import time
import json
import logging
from typing import Dict, List, Optional
from urllib.parse import urlparse, urljoin
from playwright.async_api import async_playwright, Browser, Page
from bs4 import BeautifulSoup
from crewai.tools import tool

logger = logging.getLogger(__name__)

class HumanBehaviorScraper:
    def __init__(self):
        self.browser: Optional[Browser] = None
        self.page: Optional[Page] = None
        self.playwright = None
        
    async def __aenter__(self):
        self.playwright = await async_playwright().start()
        
        # Launch browser with enhanced stealth settings
        self.browser = await self.playwright.chromium.launch(
            headless=True,  # Set to False for debugging
            args=[
                '--no-sandbox',
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor',
                '--disable-background-timer-throttling',
                '--disable-backgrounding-occluded-windows',
                '--disable-renderer-backgrounding',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps',
                '--disable-extensions',
                '--disable-ipc-flooding-protection',
                '--enable-features=NetworkService,NetworkServiceLogging',
                '--user-agent=Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                '--accept-lang=en-US,en;q=0.9',
                '--disable-blink-features=AutomationControlled'
            ]
        )
        
        # Create new page with realistic settings
        self.page = await self.browser.new_page()
        
        # Set realistic viewport
        await self.page.set_viewport_size({"width": 1366, "height": 768})
        
        # Enhanced stealth scripts to avoid detection
        await self.page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Mock plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Set languages
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Mock chrome object
            window.chrome = {
                runtime: {}
            };
            
            // Mock permissions
            Object.defineProperty(navigator, 'permissions', {
                get: () => ({
                    query: async () => ({ state: 'granted' })
                }),
            });
            
            // Override automation detection
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Mock screen properties
            Object.defineProperty(screen, 'colorDepth', { get: () => 24 });
            Object.defineProperty(screen, 'pixelDepth', { get: () => 24 });
            
            // Mock connection
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    effectiveType: '4g',
                    rtt: 50,
                    downlink: 10
                })
            });
            
            // Mock hardware concurrency
            Object.defineProperty(navigator, 'hardwareConcurrency', { get: () => 8 });
            
            // Mock device memory
            Object.defineProperty(navigator, 'deviceMemory', { get: () => 8 });
        """)
        
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def human_delay(self, min_seconds=1, max_seconds=3):
        """Add random human-like delay"""
        delay = random.uniform(min_seconds, max_seconds)
        await asyncio.sleep(delay)
    
    async def human_scroll(self):
        """Scroll like a human"""
        # Random scroll patterns
        scroll_actions = [
            "window.scrollBy(0, 200)",
            "window.scrollBy(0, 400)", 
            "window.scrollBy(0, -100)",
            "window.scrollBy(0, 600)"
        ]
        
        for _ in range(random.randint(2, 4)):
            action = random.choice(scroll_actions)
            await self.page.evaluate(action)
            await self.human_delay(0.5, 1.5)
    
    async def extract_job_details_browser(self, url: str) -> Dict:
        """Extract job details using browser automation"""
        try:
            logger.info(f"🌐 Starting extraction from: {url}")
            
            # Navigate to the job page
            logger.info(f"📡 Loading page...")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
            # Human-like behavior
            logger.info(f"👤 Simulating human behavior...")
            await self.human_delay(2, 4)
            await self.human_scroll()
            await self.human_delay(1, 2)
            
            # Wait for content to load
            logger.info(f"⏳ Waiting for content to load...")
            await self.page.wait_for_timeout(3000)
            
            # Get page content
            content = await self.page.content()
            soup = BeautifulSoup(content, 'html.parser')
            
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
                'source': domain,
                'extracted_with': 'browser_automation'
            }
            
            logger.info(f"🔍 Using site-specific extraction for: {domain}")
            if 'indeed.com' in domain:
                logger.info("🎯 Using Indeed extractor...")
                job_data.update(await self._extract_indeed_job_browser(soup, self.page))
            elif 'linkedin.com' in domain:
                logger.info("🎯 Using LinkedIn extractor...")
                job_data.update(await self._extract_linkedin_job_browser(soup, self.page))
            elif 'dice.com' in domain:
                logger.info("🎯 Using Dice extractor...")
                job_data.update(await self._extract_dice_job_browser(soup, self.page))
            else:
                logger.info("🎯 Using generic extractor...")
                job_data.update(await self._extract_generic_job_browser(soup, self.page))
            
            if job_data.get('title'):
                logger.info(f"✅ Successfully extracted: {job_data['title']} at {job_data.get('company', 'Unknown')}")
            else:
                logger.warning(f"⚠️ No job title found for: {url}")
            return job_data
            
        except Exception as e:
            logger.error(f"Error extracting job details from {url}: {e}")
            return {
                'url': url,
                'error': str(e),
                'title': '',
                'company': '',
                'location': '',
                'description': '',
                'salary': '',
                'posted_date': '',
                'source': urlparse(url).netloc if url else 'unknown',
                'extracted_with': 'browser_automation'
            }
    
    async def _extract_indeed_job_browser(self, soup, page):
        """Extract job data from Indeed using browser automation"""
        data = {}
        
        try:
            # Try multiple selectors for title
            title_selectors = [
                '[data-jk] h1',
                '.jobsearch-JobInfoHeader-title',
                'h1[data-jk]',
                '.jobsearch-JobInfoHeader-title span',
                'h1'
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = await page.query_selector(selector)
                    if title_elem:
                        data['title'] = await title_elem.inner_text()
                        break
                except:
                    continue
            
            # Company name
            company_selectors = [
                '[data-testid="inlineHeader-companyName"]',
                '.companyName',
                '[data-testid="companyName"]',
                '.icl-u-lg-mr--sm .icl-u-xs-mr--xs'
            ]
            
            for selector in company_selectors:
                try:
                    company_elem = await page.query_selector(selector)
                    if company_elem:
                        data['company'] = await company_elem.inner_text()
                        break
                except:
                    continue
            
            # Location
            location_selectors = [
                '[data-testid="job-location"]',
                '.companyLocation',
                '[data-testid="companyLocation"]'
            ]
            
            for selector in location_selectors:
                try:
                    location_elem = await page.query_selector(selector)
                    if location_elem:
                        data['location'] = await location_elem.inner_text()
                        break
                except:
                    continue
            
            # Job description
            desc_selectors = [
                '#jobDescriptionText',
                '.jobsearch-jobDescriptionText',
                '[data-testid="jobDescription"]'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_elem = await page.query_selector(selector)
                    if desc_elem:
                        desc_text = await desc_elem.inner_text()
                        data['description'] = desc_text[:500] if desc_text else ''
                        break
                except:
                    continue
            
            # Salary information
            salary_selectors = [
                '.icl-u-xs-mr--xs .attribute_snippet',
                '.salary-snippet',
                '[data-testid="salary-snippet"]'
            ]
            
            for selector in salary_selectors:
                try:
                    salary_elem = await page.query_selector(selector)
                    if salary_elem:
                        data['salary'] = await salary_elem.inner_text()
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting Indeed job data: {e}")
        
        return data
    
    async def _extract_linkedin_job_browser(self, soup, page):
        """Extract job data from LinkedIn using browser automation"""
        data = {}
        
        try:
            # Job title
            title_selectors = [
                '.top-card-layout__title',
                '.job-details-jobs-unified-top-card__job-title',
                'h1'
            ]
            
            for selector in title_selectors:
                try:
                    title_elem = await page.query_selector(selector)
                    if title_elem:
                        data['title'] = await title_elem.inner_text()
                        break
                except:
                    continue
            
            # Company
            company_selectors = [
                '.topcard__org-name-link',
                '.job-details-jobs-unified-top-card__company-name',
                '.topcard__flavor'
            ]
            
            for selector in company_selectors:
                try:
                    company_elem = await page.query_selector(selector)
                    if company_elem:
                        data['company'] = await company_elem.inner_text()
                        break
                except:
                    continue
            
            # Location
            location_selectors = [
                '.topcard__flavor--bullet',
                '.job-details-jobs-unified-top-card__bullet'
            ]
            
            for selector in location_selectors:
                try:
                    location_elem = await page.query_selector(selector)
                    if location_elem:
                        data['location'] = await location_elem.inner_text()
                        break
                except:
                    continue
            
            # Description
            desc_selectors = [
                '.show-more-less-html__markup',
                '.job-details-jobs-unified-top-card__job-description'
            ]
            
            for selector in desc_selectors:
                try:
                    desc_elem = await page.query_selector(selector)
                    if desc_elem:
                        desc_text = await desc_elem.inner_text()
                        data['description'] = desc_text[:500] if desc_text else ''
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting LinkedIn job data: {e}")
        
        return data
    
    async def _extract_dice_job_browser(self, soup, page):
        """Extract job data from Dice using browser automation"""
        data = {}
        
        try:
            # Job title
            title_elem = await page.query_selector('[data-cy="jobTitle"]')
            if title_elem:
                data['title'] = await title_elem.inner_text()
            
            # Company
            company_elem = await page.query_selector('[data-cy="companyNameLink"]')
            if company_elem:
                data['company'] = await company_elem.inner_text()
            
            # Location
            location_elem = await page.query_selector('[data-cy="jobLocation"]')
            if location_elem:
                data['location'] = await location_elem.inner_text()
            
            # Description
            desc_elem = await page.query_selector('[data-cy="jobDescription"]')
            if desc_elem:
                desc_text = await desc_elem.inner_text()
                data['description'] = desc_text[:500] if desc_text else ''
                
        except Exception as e:
            logger.error(f"Error extracting Dice job data: {e}")
        
        return data
    
    async def _extract_generic_job_browser(self, soup, page):
        """Extract job data from generic job posting page"""
        data = {}
        
        try:
            # Try to find title in h1
            title_elem = await page.query_selector('h1')
            if title_elem:
                data['title'] = await title_elem.inner_text()
            
            # Try common company selectors
            company_selectors = ['.company', '.employer', '[class*="company"]']
            for selector in company_selectors:
                try:
                    company_elem = await page.query_selector(selector)
                    if company_elem:
                        data['company'] = await company_elem.inner_text()
                        break
                except:
                    continue
            
            # Try common location selectors
            location_selectors = ['.location', '.job-location', '[class*="location"]']
            for selector in location_selectors:
                try:
                    location_elem = await page.query_selector(selector)
                    if location_elem:
                        data['location'] = await location_elem.inner_text()
                        break
                except:
                    continue
            
            # Get main content as description
            desc_selectors = ['.description', '.job-description', '.content', 'main', 'article']
            for selector in desc_selectors:
                try:
                    desc_elem = await page.query_selector(selector)
                    if desc_elem:
                        desc_text = await desc_elem.inner_text()
                        data['description'] = desc_text[:500] if desc_text else ''
                        break
                except:
                    continue
                    
        except Exception as e:
            logger.error(f"Error extracting generic job data: {e}")
        
        return data

# Global scraper instance
_scraper_instance = None

async def get_scraper():
    """Get or create scraper instance"""
    global _scraper_instance
    if _scraper_instance is None:
        _scraper_instance = HumanBehaviorScraper()
        await _scraper_instance.__aenter__()
    return _scraper_instance

@tool
def extract_job_details_browser_tool(url: str) -> str:
    """Extract job details from a job posting URL using browser automation that mimics human behavior"""
    try:
        logger.info(f"🌐 Starting browser extraction for: {url}")
        
        # Run the async function
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        async def run_extraction():
            logger.info(f"🤖 Launching browser automation for: {urlparse(url).netloc}")
            async with HumanBehaviorScraper() as scraper:
                result = await scraper.extract_job_details_browser(url)
                if result.get('title'):
                    logger.info(f"✅ Successfully extracted: {result['title']} at {result.get('company', 'Unknown Company')}")
                else:
                    logger.warning(f"⚠️ No job title found for: {url}")
                return result
        
        result = loop.run_until_complete(run_extraction())
        loop.close()
        
        return json.dumps(result)
        
    except Exception as e:
        logger.error(f"❌ Browser extraction error for {url}: {e}")
        return json.dumps({
            'url': url,
            'error': str(e),
            'title': '',
            'company': '',
            'location': '',
            'description': '',
            'salary': '',
            'posted_date': '',
            'source': urlparse(url).netloc if url else 'unknown',
            'extracted_with': 'browser_automation'
        })

if __name__ == "__main__":
    # Test the scraper
    async def test_scraper():
        async with HumanBehaviorScraper() as scraper:
            # Test with a real job URL
            test_url = "https://www.indeed.com/viewjob?jk=fa6834a1d5f7a675"
            result = await scraper.extract_job_details_browser(test_url)
            print(json.dumps(result, indent=2))
    
    asyncio.run(test_scraper())