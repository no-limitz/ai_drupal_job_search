#!/usr/bin/env python3
"""
Extraction Coordinator - Manages multiple specialized extraction agents
Part of the asynchronous multi-agent job search system
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field
from urllib.parse import urlparse

from task_manager import Task, TaskType, TaskStatus, TaskPriority, TaskManager
from browser_pool_manager import BrowserPoolManager
from linkedin_extraction_agent import LinkedInExtractionAgent
from indeed_extraction_agent import IndeedExtractionAgent
from async_agent_base import ExtractionAgentBase

logger = logging.getLogger(__name__)

@dataclass
class ExtractionCoordinatorMetrics:
    total_extractions: int = 0
    successful_extractions: int = 0
    failed_extractions: int = 0
    total_jobs_extracted: int = 0
    platform_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    avg_extraction_time: float = 0.0
    last_extraction: Optional[datetime] = None

class ExtractionCoordinator:
    """Coordinates job data extraction across multiple specialized extraction agents"""
    
    def __init__(self, 
                 browser_pool: Optional[BrowserPoolManager] = None,
                 max_concurrent_extractions: int = 5):
        
        self.browser_pool = browser_pool or BrowserPoolManager(max_browsers=8, max_pages_per_browser=3)
        self.max_concurrent_extractions = max_concurrent_extractions
        self.task_manager = TaskManager()
        
        # Initialize extraction agents
        self.extraction_agents = {
            'linkedin': LinkedInExtractionAgent(browser_pool=self.browser_pool),
            'indeed': IndeedExtractionAgent(browser_pool=self.browser_pool),
            'dice': self._create_generic_extraction_agent('dice'),
            'freelance': self._create_generic_extraction_agent('freelance'),
            'generic': self._create_generic_extraction_agent('generic')
        }
        
        self.metrics = ExtractionCoordinatorMetrics()
        self.running = False
        
        # Semaphore to limit concurrent extractions
        self.extraction_semaphore = asyncio.Semaphore(max_concurrent_extractions)
        
        logger.info(f"🎯 Extraction Coordinator initialized with {len(self.extraction_agents)} agents")

    def _create_generic_extraction_agent(self, platform: str) -> ExtractionAgentBase:
        """Create a generic extraction agent for platforms without specialized agents"""
        from async_agent_base import ExtractionAgentBase
        
        class GenericExtractionAgent(ExtractionAgentBase):
            def __init__(self, platform: str, browser_pool: Optional[BrowserPoolManager] = None):
                super().__init__(
                    agent_id=f"generic-extract-{platform}-{id(self)}",
                    platform=platform,
                    max_concurrent_tasks=3
                )
                self.browser_pool = browser_pool
            
            def get_supported_task_types(self) -> List[TaskType]:
                return [TaskType.EXTRACT_GENERIC]
            
            async def process_task(self, task: Task) -> Dict[str, Any]:
                url = task.data.get('url', '')
                
                try:
                    # Basic extraction using browser pool
                    if self.browser_pool:
                        content = await self.browser_pool.fetch_page_content(url)
                        
                        # Basic data extraction
                        job_data = {
                            'title': self._extract_title_from_content(content['content']),
                            'company': self._extract_company_from_url(url),
                            'description': content['content'][:2000],  # First 2000 chars
                            'url': url,
                            'platform': platform,
                            'extraction_method': 'generic'
                        }
                        
                        return {
                            'platform': platform,
                            'url': url,
                            'extraction_successful': True,
                            'job_data': job_data,
                            'agent_id': self.agent_id
                        }
                    else:
                        raise RuntimeError("Browser pool not available")
                        
                except Exception as e:
                    return {
                        'platform': platform,
                        'url': url,
                        'extraction_successful': False,
                        'error': str(e),
                        'agent_id': self.agent_id
                    }
            
            def _extract_title_from_content(self, content: str) -> str:
                """Extract job title from HTML content"""
                import re
                title_patterns = [
                    r'<title>([^<]+)</title>',
                    r'<h1[^>]*>([^<]+)</h1>',
                    r'job[_-]?title[^>]*>([^<]+)<'
                ]
                
                for pattern in title_patterns:
                    match = re.search(pattern, content, re.IGNORECASE)
                    if match:
                        return match.group(1).strip()
                
                return 'Unknown Job Title'
            
            def _extract_company_from_url(self, url: str) -> str:
                """Extract company name from URL domain"""
                try:
                    domain = urlparse(url).netloc
                    company = domain.replace('www.', '').replace('.com', '').replace('.', ' ').title()
                    return company
                except:
                    return 'Unknown Company'
        
        return GenericExtractionAgent(platform, self.browser_pool)

    async def start(self):
        """Start the extraction coordinator and all agents"""
        self.running = True
        
        # Start browser pool
        await self.browser_pool.start()
        
        # Start task manager
        await self.task_manager.start()
        
        # Start all extraction agents
        for platform, agent in self.extraction_agents.items():
            agent.running = True
            logger.info(f"✅ Started {platform} extraction agent: {agent.agent_id}")
        
        logger.info("🚀 Extraction Coordinator started successfully")

    async def stop(self):
        """Stop the extraction coordinator and all agents"""
        self.running = False
        
        # Stop all extraction agents
        for platform, agent in self.extraction_agents.items():
            agent.running = False
            logger.info(f"🛑 Stopped {platform} extraction agent: {agent.agent_id}")
        
        # Stop task manager
        await self.task_manager.stop()
        
        # Stop browser pool
        await self.browser_pool.stop()
        
        logger.info("🔴 Extraction Coordinator stopped")

    async def extract_jobs(self, urls: List[str]) -> Dict[str, Any]:
        """Extract job data from a list of URLs"""
        start_time = datetime.now()
        
        logger.info(f"🔍 Starting extraction for {len(urls)} URLs")
        
        # Group URLs by platform
        platform_urls = self._group_urls_by_platform(urls)
        
        # Create extraction tasks
        extraction_tasks = []
        for platform, platform_urls_list in platform_urls.items():
            for url in platform_urls_list:
                task = self._create_extraction_task(platform, url)
                extraction_tasks.append((platform, task))
        
        # Execute extractions with concurrency control
        results = await self._execute_concurrent_extractions(extraction_tasks)
        
        # Process and aggregate results
        aggregated_results = self._aggregate_extraction_results(results)
        
        # Update metrics
        extraction_duration = (datetime.now() - start_time).total_seconds()
        self._update_extraction_metrics(results, extraction_duration)
        
        logger.info(f"✅ Extraction completed in {extraction_duration:.2f}s")
        
        return {
            'total_urls': len(urls),
            'successful_extractions': aggregated_results['successful_count'],
            'failed_extractions': aggregated_results['failed_count'],
            'extraction_duration': extraction_duration,
            'platform_breakdown': aggregated_results['platform_stats'],
            'extracted_jobs': aggregated_results['jobs'],
            'extraction_summary': aggregated_results['summary'],
            'timestamp': start_time.isoformat()
        }

    def _group_urls_by_platform(self, urls: List[str]) -> Dict[str, List[str]]:
        """Group URLs by their platform"""
        platform_urls = {platform: [] for platform in self.extraction_agents.keys()}
        
        for url in urls:
            platform = self._detect_platform_from_url(url)
            platform_urls[platform].append(url)
        
        # Remove empty platform groups
        return {k: v for k, v in platform_urls.items() if v}

    def _detect_platform_from_url(self, url: str) -> str:
        """Detect platform from URL"""
        try:
            domain = urlparse(url).netloc.lower()
            
            if 'linkedin.com' in domain:
                return 'linkedin'
            elif 'indeed.com' in domain:
                return 'indeed'
            elif 'dice.com' in domain:
                return 'dice'
            elif any(freelance_domain in domain for freelance_domain in ['upwork.com', 'toptal.com', 'freelancer.com', 'gun.io', 'arc.dev']):
                return 'freelance'
            else:
                return 'generic'
        except:
            return 'generic'

    def _create_extraction_task(self, platform: str, url: str) -> Task:
        """Create extraction task for specific platform and URL"""
        task_type_map = {
            'linkedin': TaskType.EXTRACT_LINKEDIN,
            'indeed': TaskType.EXTRACT_INDEED,
            'dice': TaskType.EXTRACT_GENERIC,
            'freelance': TaskType.EXTRACT_GENERIC,
            'generic': TaskType.EXTRACT_GENERIC
        }
        
        task_type = task_type_map.get(platform, TaskType.EXTRACT_GENERIC)
        
        return Task(
            type=task_type,
            data={'url': url, 'platform': platform},
            priority=TaskPriority.HIGH
        )

    async def _execute_concurrent_extractions(self, extraction_tasks: List[tuple]) -> Dict[str, Any]:
        """Execute multiple extraction tasks concurrently with rate limiting"""
        results = {}
        
        # Create semaphore-controlled extraction tasks
        async def controlled_extraction(platform: str, task: Task):
            async with self.extraction_semaphore:
                try:
                    agent = self.extraction_agents[platform]
                    result = await agent.execute_task(task)
                    return platform, result
                except Exception as e:
                    logger.error(f"❌ {platform} extraction failed: {e}")
                    return platform, {
                        'platform': platform,
                        'url': task.data.get('url', ''),
                        'extraction_successful': False,
                        'error': str(e),
                        'agent_id': f'{platform}-agent'
                    }
        
        # Create async tasks
        async_tasks = []
        for platform, task in extraction_tasks:
            async_task = asyncio.create_task(controlled_extraction(platform, task))
            async_tasks.append(async_task)
        
        # Wait for all extractions to complete
        extraction_results = await asyncio.gather(*async_tasks, return_exceptions=True)
        
        # Process results
        for result in extraction_results:
            if isinstance(result, Exception):
                logger.error(f"Extraction task exception: {result}")
                continue
            
            platform, extraction_result = result
            
            if platform not in results:
                results[platform] = []
            results[platform].append(extraction_result)
        
        return results

    def _aggregate_extraction_results(self, platform_results: Dict[str, List[Dict[str, Any]]]) -> Dict[str, Any]:
        """Aggregate extraction results from all platforms"""
        all_jobs = []
        successful_count = 0
        failed_count = 0
        platform_stats = {}
        
        for platform, results in platform_results.items():
            platform_successful = 0
            platform_failed = 0
            platform_jobs = []
            
            for result in results:
                if result.get('extraction_successful', False):
                    platform_successful += 1
                    successful_count += 1
                    
                    job_data = result.get('job_data', {})
                    if job_data:
                        # Add extraction metadata
                        job_data.update({
                            'extraction_platform': platform,
                            'extraction_agent': result.get('agent_id', ''),
                            'extraction_timestamp': result.get('extracted_at', datetime.now().isoformat())
                        })
                        platform_jobs.append(job_data)
                        all_jobs.append(job_data)
                else:
                    platform_failed += 1
                    failed_count += 1
            
            platform_stats[platform] = {
                'successful': platform_successful,
                'failed': platform_failed,
                'total': platform_successful + platform_failed,
                'success_rate': platform_successful / max(platform_successful + platform_failed, 1),
                'jobs_extracted': len(platform_jobs)
            }
        
        # Sort jobs by data quality if available
        all_jobs.sort(key=lambda x: x.get('data_quality_score', 0), reverse=True)
        
        return {
            'jobs': all_jobs,
            'successful_count': successful_count,
            'failed_count': failed_count,
            'platform_stats': platform_stats,
            'summary': {
                'total_platforms': len(platform_results),
                'total_extractions': successful_count + failed_count,
                'overall_success_rate': successful_count / max(successful_count + failed_count, 1),
                'jobs_with_descriptions': len([j for j in all_jobs if j.get('description') and len(j['description']) > 100]),
                'drupal_relevant_jobs': len([j for j in all_jobs if 'drupal' in j.get('description', '').lower()])
            }
        }

    def _update_extraction_metrics(self, results: Dict[str, List[Dict[str, Any]]], duration: float):
        """Update extraction coordinator metrics"""
        self.metrics.total_extractions += 1
        self.metrics.last_extraction = datetime.now()
        
        # Count successful/failed extractions
        total_successful = 0
        total_failed = 0
        total_jobs = 0
        
        for platform, platform_results in results.items():
            platform_successful = 0
            platform_failed = 0
            platform_jobs = 0
            
            for result in platform_results:
                if result.get('extraction_successful', False):
                    platform_successful += 1
                    total_successful += 1
                    if result.get('job_data'):
                        platform_jobs += 1
                        total_jobs += 1
                else:
                    platform_failed += 1
                    total_failed += 1
            
            # Update platform-specific stats
            if platform not in self.metrics.platform_stats:
                self.metrics.platform_stats[platform] = {
                    'extractions': 0,
                    'successful': 0,
                    'total_jobs': 0,
                    'avg_success_rate': 0.0
                }
            
            stats = self.metrics.platform_stats[platform]
            stats['extractions'] += 1
            stats['successful'] += platform_successful
            stats['total_jobs'] += platform_jobs
            stats['avg_success_rate'] = stats['successful'] / max(stats['extractions'], 1)
        
        self.metrics.successful_extractions += total_successful
        self.metrics.failed_extractions += total_failed
        self.metrics.total_jobs_extracted += total_jobs
        
        # Update average extraction time
        if self.metrics.total_extractions == 1:
            self.metrics.avg_extraction_time = duration
        else:
            total_time = self.metrics.avg_extraction_time * (self.metrics.total_extractions - 1)
            self.metrics.avg_extraction_time = (total_time + duration) / self.metrics.total_extractions

    async def get_extraction_status(self) -> Dict[str, Any]:
        """Get current extraction coordinator status"""
        agent_status = {}
        for platform, agent in self.extraction_agents.items():
            agent_status[platform] = agent.get_status()
        
        browser_pool_status = await self.browser_pool.get_pool_status()
        
        return {
            'coordinator_running': self.running,
            'total_agents': len(self.extraction_agents),
            'max_concurrent_extractions': self.max_concurrent_extractions,
            'metrics': {
                'total_extractions': self.metrics.total_extractions,
                'successful_extractions': self.metrics.successful_extractions,
                'failed_extractions': self.metrics.failed_extractions,
                'success_rate': self.metrics.successful_extractions / max(self.metrics.total_extractions, 1),
                'total_jobs_extracted': self.metrics.total_jobs_extracted,
                'avg_extraction_time': self.metrics.avg_extraction_time,
                'last_extraction': self.metrics.last_extraction.isoformat() if self.metrics.last_extraction else None,
                'platform_stats': self.metrics.platform_stats
            },
            'agents': agent_status,
            'browser_pool': browser_pool_status,
            'task_manager_status': await self.task_manager.get_status()
        }

if __name__ == "__main__":
    # Test the extraction coordinator
    async def test_extraction_coordinator():
        print("🧪 Testing Extraction Coordinator...")
        
        coordinator = ExtractionCoordinator(max_concurrent_extractions=3)
        
        try:
            await coordinator.start()
            
            # Test URLs for different platforms
            test_urls = [
                'https://linkedin.com/jobs/view/123456789',
                'https://indeed.com/viewjob?jk=abc123def',
                'https://dice.com/jobs/detail/xyz789',
                'https://upwork.com/jobs/drupal-development-456',
                'https://example.com/job/generic-123'
            ]
            
            result = await coordinator.extract_jobs(test_urls)
            
            print(f"📊 Extraction Results:")
            print(f"  - Total URLs: {result['total_urls']}")
            print(f"  - Successful: {result['successful_extractions']}")
            print(f"  - Failed: {result['failed_extractions']}")
            print(f"  - Duration: {result['extraction_duration']:.2f}s")
            
            # Show platform breakdown
            print(f"\n🎯 Platform Breakdown:")
            for platform, stats in result['platform_breakdown'].items():
                print(f"  - {platform}: {stats['successful']}/{stats['total']} ({stats['success_rate']:.1%})")
            
            # Show extracted jobs
            print(f"\n📋 Extracted Jobs: {len(result['extracted_jobs'])}")
            for i, job in enumerate(result['extracted_jobs'][:3], 1):
                print(f"  {i}. {job.get('title', 'Unknown')} at {job.get('company', 'Unknown')}")
                print(f"     Platform: {job.get('extraction_platform', 'Unknown')}")
            
            # Test status
            status = await coordinator.get_extraction_status()
            print(f"\n📈 Coordinator Status:")
            print(f"  - Total Extractions: {status['metrics']['total_extractions']}")
            print(f"  - Success Rate: {status['metrics']['success_rate']:.1%}")
            print(f"  - Jobs Extracted: {status['metrics']['total_jobs_extracted']}")
            
        finally:
            await coordinator.stop()
        
        print("✅ Extraction Coordinator test completed!")
    
    # Skip test if Playwright not available
    try:
        from playwright.async_api import async_playwright
        asyncio.run(test_extraction_coordinator())
    except ImportError:
        print("⚠️ Playwright not available - skipping extraction coordinator test")
        print("Install with: pip install playwright && playwright install")