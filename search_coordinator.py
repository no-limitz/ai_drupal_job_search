#!/usr/bin/env python3
"""
Search Coordinator - Manages multiple specialized search agents
Part of the asynchronous multi-agent job search system
"""

import asyncio
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from task_manager import Task, TaskType, TaskStatus, TaskPriority, TaskManager
from linkedin_search_agent import LinkedInSearchAgent
from indeed_search_agent import IndeedSearchAgent
from dice_search_agent import DiceSearchAgent
from freelance_search_agent import FreelanceSearchAgent
from config_manager import JobSearchConfiguration

logger = logging.getLogger(__name__)

@dataclass
class SearchCoordinatorMetrics:
    total_searches: int = 0
    successful_searches: int = 0
    failed_searches: int = 0
    total_jobs_found: int = 0
    platform_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    search_duration: float = 0.0
    last_search: Optional[datetime] = None

class SearchCoordinator:
    """Coordinates searches across multiple specialized search agents"""
    
    def __init__(self, config: Optional[JobSearchConfiguration] = None):
        self.config = config or JobSearchConfiguration()
        self.task_manager = TaskManager()
        
        # Initialize search agents
        self.search_agents = {
            'linkedin': LinkedInSearchAgent(),
            'indeed': IndeedSearchAgent(), 
            'dice': DiceSearchAgent(),
            'freelance': FreelanceSearchAgent()
        }
        
        self.metrics = SearchCoordinatorMetrics()
        self.running = False
        
        logger.info(f"🎯 Search Coordinator initialized with {len(self.search_agents)} agents")

    async def start(self):
        """Start the search coordinator and all agents"""
        self.running = True
        
        # Start task manager
        await self.task_manager.start()
        
        # Start all search agents
        for platform, agent in self.search_agents.items():
            agent.running = True
            logger.info(f"✅ Started {platform} search agent: {agent.agent_id}")
        
        logger.info("🚀 Search Coordinator started successfully")

    async def stop(self):
        """Stop the search coordinator and all agents"""
        self.running = False
        
        # Stop all search agents
        for platform, agent in self.search_agents.items():
            agent.running = False
            logger.info(f"🛑 Stopped {platform} search agent: {agent.agent_id}")
        
        # Stop task manager
        await self.task_manager.stop()
        
        logger.info("🔴 Search Coordinator stopped")

    async def execute_search(self, search_params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute coordinated search across all platforms"""
        start_time = datetime.now()
        
        query = search_params.get('query', 'Drupal Developer')
        location = search_params.get('location', 'Remote')
        platforms = search_params.get('platforms', ['linkedin', 'indeed', 'dice', 'freelance'])
        
        logger.info(f"🔍 Starting coordinated search: '{query}' in {location}")
        
        # Create search tasks for each platform
        search_tasks = []
        for platform in platforms:
            if platform in self.search_agents:
                task_type = getattr(TaskType, f'SEARCH_{platform.upper()}', None)
                if task_type:
                    task = Task(
                        type=task_type,
                        data={
                            'query': query,
                            'location': location
                        },
                        priority=TaskPriority.HIGH
                    )
                    search_tasks.append((platform, task))
        
        # Execute all search tasks concurrently
        results = await self._execute_concurrent_searches(search_tasks)
        
        # Process and aggregate results
        aggregated_results = self._aggregate_search_results(results)
        
        # Update metrics
        search_duration = (datetime.now() - start_time).total_seconds()
        self._update_search_metrics(results, search_duration)
        
        logger.info(f"✅ Coordinated search completed in {search_duration:.2f}s")
        
        return {
            'search_params': search_params,
            'platforms_searched': len(results),
            'total_jobs_found': aggregated_results['total_jobs'],
            'search_duration': search_duration,
            'platform_results': results,
            'aggregated_jobs': aggregated_results['jobs'],
            'search_summary': aggregated_results['summary'],
            'timestamp': start_time.isoformat()
        }

    async def _execute_concurrent_searches(self, search_tasks: List[tuple]) -> Dict[str, Any]:
        """Execute multiple search tasks concurrently"""
        results = {}
        
        # Create concurrent tasks
        async_tasks = []
        for platform, task in search_tasks:
            agent = self.search_agents[platform]
            async_task = asyncio.create_task(
                self._execute_platform_search(platform, agent, task)
            )
            async_tasks.append((platform, async_task))
        
        # Wait for all searches to complete
        for platform, async_task in async_tasks:
            try:
                result = await async_task
                results[platform] = result
                logger.debug(f"✅ {platform} search completed")
            except Exception as e:
                logger.error(f"❌ {platform} search failed: {e}")
                results[platform] = {
                    'error': str(e),
                    'platform': platform,
                    'jobs': [],
                    'processed_results': 0
                }
        
        return results

    async def _execute_platform_search(self, platform: str, agent, task: Task) -> Dict[str, Any]:
        """Execute search for a specific platform"""
        try:
            result = await agent.execute_task(task)
            return result
        except Exception as e:
            logger.error(f"Platform {platform} search error: {e}")
            raise

    def _aggregate_search_results(self, platform_results: Dict[str, Any]) -> Dict[str, Any]:
        """Aggregate results from all platforms"""
        all_jobs = []
        platform_summary = {}
        
        for platform, result in platform_results.items():
            if 'error' in result:
                platform_summary[platform] = {
                    'status': 'failed',
                    'error': result['error'],
                    'jobs_found': 0
                }
                continue
            
            jobs = result.get('jobs', [])
            
            # Add platform metadata to each job
            for job in jobs:
                job['source_platform'] = platform
                job['search_timestamp'] = datetime.now().isoformat()
            
            all_jobs.extend(jobs)
            
            platform_summary[platform] = {
                'status': 'success',
                'jobs_found': len(jobs),
                'queries_executed': result.get('total_queries', 0),
                'agent_id': result.get('agent_id', 'unknown')
            }
        
        # Remove duplicates based on URL
        unique_jobs = self._deduplicate_jobs(all_jobs)
        
        # Sort by relevance score
        unique_jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return {
            'jobs': unique_jobs,
            'total_jobs': len(unique_jobs),
            'duplicate_jobs_removed': len(all_jobs) - len(unique_jobs),
            'summary': platform_summary
        }

    def _deduplicate_jobs(self, jobs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate jobs based on URL"""
        seen_urls = set()
        unique_jobs = []
        
        for job in jobs:
            url = job.get('url', '')
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_jobs.append(job)
            elif url:
                logger.debug(f"Removed duplicate job: {job.get('title', 'Unknown')} from {job.get('source_platform', 'Unknown')}")
        
        return unique_jobs

    def _update_search_metrics(self, results: Dict[str, Any], duration: float):
        """Update search coordinator metrics"""
        self.metrics.total_searches += 1
        self.metrics.search_duration = duration
        self.metrics.last_search = datetime.now()
        
        successful_platforms = 0
        total_jobs = 0
        
        for platform, result in results.items():
            if 'error' not in result:
                successful_platforms += 1
                jobs_found = result.get('processed_results', 0)
                total_jobs += jobs_found
                
                # Update platform-specific stats
                if platform not in self.metrics.platform_stats:
                    self.metrics.platform_stats[platform] = {
                        'searches': 0,
                        'successful': 0,
                        'total_jobs': 0,
                        'avg_jobs_per_search': 0.0
                    }
                
                stats = self.metrics.platform_stats[platform]
                stats['searches'] += 1
                stats['successful'] += 1
                stats['total_jobs'] += jobs_found
                stats['avg_jobs_per_search'] = stats['total_jobs'] / stats['searches']
            else:
                # Handle failed platform
                if platform not in self.metrics.platform_stats:
                    self.metrics.platform_stats[platform] = {
                        'searches': 0,
                        'successful': 0,
                        'total_jobs': 0,
                        'avg_jobs_per_search': 0.0
                    }
                self.metrics.platform_stats[platform]['searches'] += 1
        
        if successful_platforms > 0:
            self.metrics.successful_searches += 1
        else:
            self.metrics.failed_searches += 1
        
        self.metrics.total_jobs_found += total_jobs

    async def get_search_status(self) -> Dict[str, Any]:
        """Get current search coordinator status"""
        agent_status = {}
        for platform, agent in self.search_agents.items():
            agent_status[platform] = agent.get_status()
        
        return {
            'coordinator_running': self.running,
            'total_agents': len(self.search_agents),
            'metrics': {
                'total_searches': self.metrics.total_searches,
                'successful_searches': self.metrics.successful_searches,
                'failed_searches': self.metrics.failed_searches,
                'success_rate': self.metrics.successful_searches / max(self.metrics.total_searches, 1),
                'total_jobs_found': self.metrics.total_jobs_found,
                'avg_jobs_per_search': self.metrics.total_jobs_found / max(self.metrics.total_searches, 1),
                'last_search': self.metrics.last_search.isoformat() if self.metrics.last_search else None,
                'platform_stats': self.metrics.platform_stats
            },
            'agents': agent_status,
            'task_manager_status': await self.task_manager.get_status()
        }

    async def search_drupal_jobs(self, 
                                keywords: Optional[List[str]] = None,
                                locations: Optional[List[str]] = None,
                                platforms: Optional[List[str]] = None) -> Dict[str, Any]:
        """High-level method to search for Drupal jobs with configuration"""
        
        # Use config defaults if not provided
        keywords = keywords or self.config.config['search_parameters']['keywords']
        locations = locations or self.config.config['search_parameters']['locations']
        platforms = platforms or ['linkedin', 'indeed', 'dice', 'freelance']
        
        all_results = []
        
        # Execute searches for each keyword/location combination
        for keyword in keywords[:3]:  # Limit to prevent excessive API calls
            for location in locations[:2]:  # Limit locations
                search_params = {
                    'query': keyword,
                    'location': location,
                    'platforms': platforms
                }
                
                try:
                    result = await self.execute_search(search_params)
                    all_results.append(result)
                    
                    # Add delay between searches to respect rate limits
                    await asyncio.sleep(1.0)
                    
                except Exception as e:
                    logger.error(f"Search failed for {keyword} in {location}: {e}")
        
        # Aggregate all results
        return self._aggregate_multiple_searches(all_results)

    def _aggregate_multiple_searches(self, search_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate results from multiple search executions"""
        all_jobs = []
        total_duration = 0.0
        
        for result in search_results:
            all_jobs.extend(result.get('aggregated_jobs', []))
            total_duration += result.get('search_duration', 0.0)
        
        # Remove duplicates across all searches
        unique_jobs = self._deduplicate_jobs(all_jobs)
        
        # Sort by relevance
        unique_jobs.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        
        return {
            'total_searches_executed': len(search_results),
            'total_jobs_found': len(unique_jobs),
            'duplicates_removed': len(all_jobs) - len(unique_jobs),
            'total_search_duration': total_duration,
            'jobs': unique_jobs[:50],  # Return top 50 jobs
            'search_summary': {
                'platforms_used': list(self.search_agents.keys()),
                'agents_active': len([a for a in self.search_agents.values() if a.running]),
                'timestamp': datetime.now().isoformat()
            }
        }

if __name__ == "__main__":
    # Test the search coordinator
    async def test_search_coordinator():
        print("🧪 Testing Search Coordinator...")
        
        coordinator = SearchCoordinator()
        await coordinator.start()
        
        try:
            # Test single search
            search_params = {
                'query': 'Senior Drupal Developer',
                'location': 'Remote',
                'platforms': ['linkedin', 'indeed', 'dice', 'freelance']
            }
            
            result = await coordinator.execute_search(search_params)
            
            print(f"📊 Search Results:")
            print(f"  - Platforms: {result['platforms_searched']}")
            print(f"  - Jobs Found: {result['total_jobs_found']}")
            print(f"  - Duration: {result['search_duration']:.2f}s")
            
            # Show platform breakdown
            for platform, stats in result['search_summary'].items():
                print(f"  - {platform}: {stats['jobs_found']} jobs ({stats['status']})")
            
            # Show top jobs
            print(f"\n🎯 Top 3 Jobs:")
            for i, job in enumerate(result['aggregated_jobs'][:3], 1):
                print(f"  {i}. {job['title']} at {job['company']} (Score: {job['relevance_score']:.1f})")
                print(f"     Platform: {job['source_platform']} | Location: {job['location']}")
            
            # Test status
            status = await coordinator.get_search_status()
            print(f"\n📈 Coordinator Status:")
            print(f"  - Total Searches: {status['metrics']['total_searches']}")
            print(f"  - Success Rate: {status['metrics']['success_rate']:.1%}")
            print(f"  - Avg Jobs/Search: {status['metrics']['avg_jobs_per_search']:.1f}")
            
        finally:
            await coordinator.stop()
        
        print("✅ Search Coordinator test completed!")
    
    asyncio.run(test_search_coordinator())