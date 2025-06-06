#!/usr/bin/env python3
"""
Browser Pool Manager - Manages concurrent browser instances for job data extraction
Part of the asynchronous multi-agent job search system
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager
from enum import Enum
import uuid

try:
    from playwright.async_api import async_playwright, Browser, BrowserContext, Page
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    Browser = None
    BrowserContext = None
    Page = None

logger = logging.getLogger(__name__)

class BrowserType(Enum):
    CHROMIUM = "chromium"
    FIREFOX = "firefox"
    WEBKIT = "webkit"

@dataclass
class BrowserInstance:
    id: str
    browser: Optional[Browser]
    context: Optional[BrowserContext]
    created_at: datetime
    last_used: datetime
    active_pages: int = 0
    max_pages: int = 5
    domain_restrictions: Set[str] = field(default_factory=set)
    user_agent: Optional[str] = None
    proxy: Optional[str] = None
    is_healthy: bool = True
    total_requests: int = 0
    failed_requests: int = 0

@dataclass
class BrowserPoolMetrics:
    total_browsers: int = 0
    active_browsers: int = 0
    total_pages: int = 0
    active_pages: int = 0
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    avg_response_time: float = 0.0
    pool_utilization: float = 0.0
    browser_creation_count: int = 0
    browser_cleanup_count: int = 0

class BrowserPoolManager:
    """Manages a pool of browser instances for concurrent web scraping"""
    
    def __init__(self, 
                 max_browsers: int = 10,
                 max_pages_per_browser: int = 5,
                 browser_type: BrowserType = BrowserType.CHROMIUM,
                 headless: bool = True,
                 enable_stealth: bool = True,
                 request_timeout: int = 30000,
                 browser_timeout: int = 300):
        
        if not PLAYWRIGHT_AVAILABLE:
            raise ImportError("Playwright is required for browser pool management. Install with: pip install playwright")
        
        self.max_browsers = max_browsers
        self.max_pages_per_browser = max_pages_per_browser
        self.browser_type = browser_type
        self.headless = headless
        self.enable_stealth = enable_stealth
        self.request_timeout = request_timeout
        self.browser_timeout = browser_timeout
        
        # Browser pool state
        self.browsers: Dict[str, BrowserInstance] = {}
        self.available_browsers: asyncio.Queue = asyncio.Queue()
        self.playwright = None
        self.browser_launcher = None
        self.running = False
        
        # Metrics and monitoring
        self.metrics = BrowserPoolMetrics()
        self.request_history: List[Dict[str, Any]] = []
        
        # Rate limiting per domain
        self.domain_last_request: Dict[str, datetime] = {}
        self.domain_request_delay = {
            'linkedin.com': 2.0,
            'indeed.com': 1.5,
            'dice.com': 1.0,
            'upwork.com': 2.0,
            'toptal.com': 3.0,
            'freelancer.com': 1.5,
            'default': 1.0
        }
        
        logger.info(f"🌐 Browser Pool Manager initialized (max_browsers={max_browsers}, type={browser_type.value})")

    async def start(self):
        """Start the browser pool manager"""
        if self.running:
            return
        
        self.playwright = await async_playwright().start()
        
        if self.browser_type == BrowserType.CHROMIUM:
            self.browser_launcher = self.playwright.chromium
        elif self.browser_type == BrowserType.FIREFOX:
            self.browser_launcher = self.playwright.firefox
        elif self.browser_type == BrowserType.WEBKIT:
            self.browser_launcher = self.playwright.webkit
        
        # Pre-create initial browsers
        initial_browsers = min(3, self.max_browsers)
        for _ in range(initial_browsers):
            await self._create_browser()
        
        self.running = True
        
        # Start cleanup task
        asyncio.create_task(self._cleanup_task())
        
        logger.info(f"🚀 Browser Pool started with {len(self.browsers)} initial browsers")

    async def stop(self):
        """Stop the browser pool and cleanup all browsers"""
        if not self.running:
            return
        
        self.running = False
        
        # Close all browsers
        for browser_id, browser_instance in list(self.browsers.items()):
            await self._close_browser(browser_id)
        
        # Stop playwright
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
        
        logger.info("🔴 Browser Pool stopped")

    async def _create_browser(self, domain_restrictions: Optional[Set[str]] = None) -> str:
        """Create a new browser instance"""
        if len(self.browsers) >= self.max_browsers:
            raise RuntimeError(f"Maximum browser limit reached ({self.max_browsers})")
        
        browser_id = str(uuid.uuid4())
        
        # Browser launch options
        launch_options = {
            'headless': self.headless,
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--no-first-run',
                '--no-default-browser-check',
                '--disable-default-apps'
            ]
        }
        
        # Add stealth options
        if self.enable_stealth:
            launch_options['args'].extend([
                '--disable-blink-features=AutomationControlled',
                '--disable-web-security',
                '--disable-features=VizDisplayCompositor'
            ])
        
        try:
            browser = await self.browser_launcher.launch(**launch_options)
            
            # Create context with stealth settings
            context_options = {
                'viewport': {'width': 1920, 'height': 1080},
                'user_agent': self._get_random_user_agent(),
                'locale': 'en-US',
                'timezone_id': 'America/New_York'
            }
            
            if self.enable_stealth:
                context_options['extra_http_headers'] = {
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            
            context = await browser.new_context(**context_options)
            
            # Add stealth JavaScript if enabled
            if self.enable_stealth:
                await context.add_init_script("""
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                """)
            
            browser_instance = BrowserInstance(
                id=browser_id,
                browser=browser,
                context=context,
                created_at=datetime.now(),
                last_used=datetime.now(),
                max_pages=self.max_pages_per_browser,
                domain_restrictions=domain_restrictions or set(),
                user_agent=context_options['user_agent']
            )
            
            self.browsers[browser_id] = browser_instance
            await self.available_browsers.put(browser_id)
            
            self.metrics.total_browsers += 1
            self.metrics.active_browsers += 1
            self.metrics.browser_creation_count += 1
            
            logger.debug(f"✅ Created browser {browser_id[:8]}")
            return browser_id
            
        except Exception as e:
            logger.error(f"❌ Failed to create browser: {e}")
            raise

    async def _close_browser(self, browser_id: str):
        """Close a specific browser instance"""
        if browser_id not in self.browsers:
            return
        
        browser_instance = self.browsers[browser_id]
        
        try:
            if browser_instance.context:
                await browser_instance.context.close()
            if browser_instance.browser:
                await browser_instance.browser.close()
            
            del self.browsers[browser_id]
            self.metrics.active_browsers -= 1
            self.metrics.browser_cleanup_count += 1
            
            logger.debug(f"🗑️ Closed browser {browser_id[:8]}")
            
        except Exception as e:
            logger.error(f"❌ Error closing browser {browser_id[:8]}: {e}")

    @asynccontextmanager
    async def get_page(self, url: str, domain_restrictions: Optional[Set[str]] = None):
        """Get a page from the browser pool with automatic cleanup"""
        browser_id = None
        page = None
        
        try:
            # Apply rate limiting
            await self._apply_rate_limiting(url)
            
            # Get available browser
            browser_id = await self._get_available_browser(domain_restrictions)
            browser_instance = self.browsers[browser_id]
            
            # Create new page
            page = await browser_instance.context.new_page()
            page.set_default_timeout(self.request_timeout)
            
            # Update metrics
            browser_instance.active_pages += 1
            browser_instance.last_used = datetime.now()
            self.metrics.active_pages += 1
            
            logger.debug(f"📄 Created page for {url} using browser {browser_id[:8]}")
            
            yield page
            
        except Exception as e:
            logger.error(f"❌ Error with page for {url}: {e}")
            raise
            
        finally:
            # Cleanup page
            if page:
                try:
                    await page.close()
                    if browser_id and browser_id in self.browsers:
                        self.browsers[browser_id].active_pages -= 1
                        self.metrics.active_pages -= 1
                        
                        # Return browser to pool if healthy
                        if self.browsers[browser_id].is_healthy:
                            await self.available_browsers.put(browser_id)
                        
                except Exception as e:
                    logger.error(f"❌ Error closing page: {e}")

    async def _get_available_browser(self, domain_restrictions: Optional[Set[str]] = None) -> str:
        """Get an available browser from the pool"""
        timeout = 30  # seconds
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            try:
                # Try to get browser from queue (with short timeout)
                browser_id = await asyncio.wait_for(self.available_browsers.get(), timeout=1.0)
                
                # Check if browser is still valid
                if browser_id in self.browsers:
                    browser_instance = self.browsers[browser_id]
                    
                    # Check health and capacity
                    if (browser_instance.is_healthy and 
                        browser_instance.active_pages < browser_instance.max_pages):
                        
                        # Check domain restrictions
                        if (not domain_restrictions or 
                            not browser_instance.domain_restrictions or
                            domain_restrictions.intersection(browser_instance.domain_restrictions)):
                            
                            return browser_id
                
                # Browser not suitable, put back and continue
                await self.available_browsers.put(browser_id)
                
            except asyncio.TimeoutError:
                # No browsers available, try to create one
                if len(self.browsers) < self.max_browsers:
                    try:
                        new_browser_id = await self._create_browser(domain_restrictions)
                        return new_browser_id
                    except Exception as e:
                        logger.warning(f"Failed to create new browser: {e}")
                
                # Wait a bit before retrying
                await asyncio.sleep(0.5)
        
        raise RuntimeError("Timeout waiting for available browser")

    async def _apply_rate_limiting(self, url: str):
        """Apply rate limiting based on domain"""
        from urllib.parse import urlparse
        
        try:
            domain = urlparse(url).netloc.lower()
            
            # Find matching delay
            delay = self.domain_request_delay.get('default', 1.0)
            for domain_pattern, domain_delay in self.domain_request_delay.items():
                if domain_pattern in domain:
                    delay = domain_delay
                    break
            
            # Check if we need to wait
            if domain in self.domain_last_request:
                elapsed = (datetime.now() - self.domain_last_request[domain]).total_seconds()
                if elapsed < delay:
                    wait_time = delay - elapsed
                    logger.debug(f"⏱️ Rate limiting {domain}: waiting {wait_time:.1f}s")
                    await asyncio.sleep(wait_time)
            
            # Update last request time
            self.domain_last_request[domain] = datetime.now()
            
        except Exception as e:
            logger.warning(f"Rate limiting error for {url}: {e}")

    async def fetch_page_content(self, url: str, 
                                wait_for_selector: Optional[str] = None,
                                scroll_to_bottom: bool = False,
                                screenshot: bool = False) -> Dict[str, Any]:
        """Fetch page content with optional waiting and actions"""
        start_time = time.time()
        
        try:
            async with self.get_page(url) as page:
                # Navigate to page
                response = await page.goto(url, wait_until='domcontentloaded')
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                
                # Scroll to bottom if requested
                if scroll_to_bottom:
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await asyncio.sleep(1)
                
                # Get page content
                content = await page.content()
                title = await page.title()
                
                # Take screenshot if requested
                screenshot_data = None
                if screenshot:
                    screenshot_data = await page.screenshot(type='png')
                
                # Update metrics
                duration = time.time() - start_time
                self.metrics.total_requests += 1
                self.metrics.successful_requests += 1
                self._update_response_time(duration)
                
                return {
                    'url': url,
                    'content': content,
                    'title': title,
                    'status_code': response.status if response else None,
                    'response_time': duration,
                    'screenshot': screenshot_data,
                    'timestamp': datetime.now().isoformat()
                }
                
        except Exception as e:
            # Update failure metrics
            self.metrics.total_requests += 1
            self.metrics.failed_requests += 1
            
            logger.error(f"❌ Failed to fetch {url}: {e}")
            raise

    def _update_response_time(self, duration: float):
        """Update average response time metric"""
        if self.metrics.successful_requests == 1:
            self.metrics.avg_response_time = duration
        else:
            # Running average
            total_time = self.metrics.avg_response_time * (self.metrics.successful_requests - 1)
            self.metrics.avg_response_time = (total_time + duration) / self.metrics.successful_requests

    def _get_random_user_agent(self) -> str:
        """Get a random user agent string"""
        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15'
        ]
        import random
        return random.choice(user_agents)

    async def _cleanup_task(self):
        """Background task to cleanup idle browsers"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.now()
                browsers_to_close = []
                
                for browser_id, browser_instance in self.browsers.items():
                    # Close idle browsers (inactive for > browser_timeout seconds)
                    idle_time = (current_time - browser_instance.last_used).total_seconds()
                    
                    if (idle_time > self.browser_timeout and 
                        browser_instance.active_pages == 0 and
                        len(self.browsers) > 1):  # Keep at least one browser
                        
                        browsers_to_close.append(browser_id)
                
                # Close idle browsers
                for browser_id in browsers_to_close:
                    logger.info(f"🧹 Closing idle browser {browser_id[:8]}")
                    await self._close_browser(browser_id)
                
                # Update pool utilization metric
                if self.max_browsers > 0:
                    self.metrics.pool_utilization = len(self.browsers) / self.max_browsers
                
            except Exception as e:
                logger.error(f"❌ Cleanup task error: {e}")

    async def get_pool_status(self) -> Dict[str, Any]:
        """Get current browser pool status and metrics"""
        active_pages = sum(b.active_pages for b in self.browsers.values())
        
        browser_details = []
        for browser_id, browser in self.browsers.items():
            browser_details.append({
                'id': browser_id[:8],
                'created_at': browser.created_at.isoformat(),
                'last_used': browser.last_used.isoformat(),
                'active_pages': browser.active_pages,
                'max_pages': browser.max_pages,
                'total_requests': browser.total_requests,
                'failed_requests': browser.failed_requests,
                'is_healthy': browser.is_healthy,
                'user_agent': browser.user_agent[:50] + '...' if browser.user_agent else None
            })
        
        return {
            'running': self.running,
            'metrics': {
                'total_browsers': len(self.browsers),
                'active_browsers': len(self.browsers),
                'active_pages': active_pages,
                'max_browsers': self.max_browsers,
                'max_pages': self.max_browsers * self.max_pages_per_browser,
                'pool_utilization': len(self.browsers) / self.max_browsers if self.max_browsers > 0 else 0,
                'total_requests': self.metrics.total_requests,
                'successful_requests': self.metrics.successful_requests,
                'failed_requests': self.metrics.failed_requests,
                'success_rate': self.metrics.successful_requests / max(self.metrics.total_requests, 1),
                'avg_response_time': self.metrics.avg_response_time,
                'browser_creation_count': self.metrics.browser_creation_count,
                'browser_cleanup_count': self.metrics.browser_cleanup_count
            },
            'browsers': browser_details,
            'rate_limits': self.domain_request_delay
        }

if __name__ == "__main__":
    # Test the browser pool manager
    async def test_browser_pool():
        print("🧪 Testing Browser Pool Manager...")
        
        if not PLAYWRIGHT_AVAILABLE:
            print("❌ Playwright not available. Install with: pip install playwright")
            return
        
        pool = BrowserPoolManager(max_browsers=3, max_pages_per_browser=2)
        
        try:
            await pool.start()
            
            # Test fetching multiple pages concurrently
            test_urls = [
                'https://httpbin.org/html',
                'https://httpbin.org/json',
                'https://httpbin.org/xml'
            ]
            
            tasks = []
            for url in test_urls:
                task = asyncio.create_task(pool.fetch_page_content(url))
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            print(f"📊 Fetch Results:")
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    print(f"  {i+1}. ❌ Error: {result}")
                else:
                    print(f"  {i+1}. ✅ {result['url']} - {len(result['content'])} chars, {result['response_time']:.2f}s")
            
            # Show pool status
            status = await pool.get_pool_status()
            print(f"\n📈 Pool Status:")
            print(f"  - Browsers: {status['metrics']['total_browsers']}/{status['metrics']['max_browsers']}")
            print(f"  - Success Rate: {status['metrics']['success_rate']:.1%}")
            print(f"  - Avg Response Time: {status['metrics']['avg_response_time']:.2f}s")
            print(f"  - Pool Utilization: {status['metrics']['pool_utilization']:.1%}")
            
        finally:
            await pool.stop()
        
        print("✅ Browser Pool Manager test completed!")
    
    asyncio.run(test_browser_pool())