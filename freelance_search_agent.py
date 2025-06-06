#!/usr/bin/env python3
"""
Freelance Search Agent - Specialized agent for freelance platform searches
Covers Upwork, Toptal, Freelancer.com, Gun.io, Arc.dev
Part of the asynchronous multi-agent job search system
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from collections import defaultdict
from crewai.tools import tool

from async_agent_base import SearchAgentBase
from task_manager import Task, TaskType, TaskStatus

logger = logging.getLogger(__name__)

class FreelanceSearchAgent(SearchAgentBase):
    """Specialized agent for freelance platform searches with platform-specific optimizations"""
    
    def __init__(self, agent_id: str = None, **kwargs):
        if not agent_id:
            agent_id = f"freelance-search-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="Freelance",
            **kwargs
        )
        
        # Freelance platform configurations
        self.freelance_platforms = {
            'upwork': {
                'domain': 'upwork.com',
                'focus': 'hourly and fixed-price projects',
                'rate_structure': 'hourly',
                'typical_range': '$25-75/hour'
            },
            'toptal': {
                'domain': 'toptal.com',
                'focus': 'elite freelancers',
                'rate_structure': 'hourly',
                'typical_range': '$60-150/hour'
            },
            'freelancer': {
                'domain': 'freelancer.com',
                'focus': 'competitive bidding',
                'rate_structure': 'project',
                'typical_range': '$500-5000/project'
            },
            'gun.io': {
                'domain': 'gun.io',
                'focus': 'vetted developers',
                'rate_structure': 'hourly',
                'typical_range': '$50-120/hour'
            },
            'arc.dev': {
                'domain': 'arc.dev',
                'focus': 'remote developers',
                'rate_structure': 'hourly',
                'typical_range': '$40-100/hour'
            }
        }
        
        self.freelance_keywords = [
            "drupal development",
            "drupal website",
            "drupal migration",
            "drupal customization",
            "drupal module development",
            "drupal theme development",
            "drupal api development",
            "cms development drupal"
        ]
        
        self.project_types = [
            "website development",
            "module development",
            "theme customization",
            "migration project",
            "maintenance contract",
            "api integration",
            "performance optimization"
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.SEARCH_FREELANCE]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process freelance search task"""
        if task.type != TaskType.SEARCH_FREELANCE:
            raise ValueError(f"FreelanceSearchAgent cannot handle task type {task.type}")
        
        search_data = task.data
        query = search_data.get('query', '')
        platforms = search_data.get('platforms', list(self.freelance_platforms.keys()))
        project_type = search_data.get('project_type', 'development')
        
        logger.info(f"🔍 Freelance search for: {query} across {len(platforms)} platforms")
        
        # Generate platform-specific search queries
        search_queries = self._generate_freelance_queries(query, platforms, project_type)
        
        # Simulate search execution across platforms
        results = []
        for platform, search_query in search_queries:
            query_results = await self._execute_freelance_search(platform, search_query)
            results.extend(query_results)
        
        # Process and validate results
        processed_results = self._process_search_results(results)
        
        return {
            'platform': 'freelance',
            'query': query,
            'platforms_searched': platforms,
            'project_type': project_type,
            'total_queries': len(search_queries),
            'raw_results': len(results),
            'processed_results': len(processed_results),
            'jobs': processed_results,
            'agent_id': self.agent_id
        }

    def _generate_freelance_queries(self, base_query: str, platforms: List[str], project_type: str) -> List[tuple]:
        """Generate freelance platform-specific search queries"""
        queries = []
        
        for platform in platforms:
            if platform not in self.freelance_platforms:
                continue
                
            platform_info = self.freelance_platforms[platform]
            domain = platform_info['domain']
            
            # Base keyword searches
            for keyword in self.freelance_keywords:
                if keyword.lower() in base_query.lower() or 'drupal' in base_query.lower():
                    # Platform-specific query format
                    query = f'{keyword} {project_type} site:{domain}'
                    queries.append((platform, query))
            
            # Project type specific searches
            for proj_type in self.project_types:
                if proj_type in project_type.lower():
                    query = f'drupal {proj_type} site:{domain}'
                    queries.append((platform, query))
            
            # Platform-specific searches
            if platform == 'upwork':
                queries.append((platform, f'drupal developer hourly contract site:{domain}'))
            elif platform == 'toptal':
                queries.append((platform, f'senior drupal developer site:{domain}'))
            elif platform == 'freelancer':
                queries.append((platform, f'drupal project fixed price site:{domain}'))
            elif platform == 'gun.io':
                queries.append((platform, f'drupal backend developer site:{domain}'))
            elif platform == 'arc.dev':
                queries.append((platform, f'remote drupal developer site:{domain}'))
        
        return queries[:15]  # Limit total queries

    async def _execute_freelance_search(self, platform: str, query: str) -> List[Dict[str, Any]]:
        """Execute freelance platform search (simulated for now)"""
        # Simulate API delay
        await asyncio.sleep(0.6)
        
        platform_info = self.freelance_platforms.get(platform, {})
        
        # Mock results based on platform characteristics
        mock_results = self._generate_platform_specific_results(platform, platform_info)
        
        # Add query context to results
        for result in mock_results:
            result['search_query'] = query
            result['platform'] = platform
            result['source_platform'] = 'freelance'
            
        return mock_results

    def _generate_platform_specific_results(self, platform: str, platform_info: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate platform-specific mock results"""
        
        if platform == 'upwork':
            return [
                {
                    'title': 'Drupal 9 Website Development - Long Term',
                    'client': 'E-commerce Startup',
                    'location': 'Remote',
                    'url': f'https://upwork.com/jobs/drupal-development-123',
                    'description': 'Looking for experienced Drupal developer for ongoing website development. Must have D9/D10 experience...',
                    'posted_date': '2024-01-01',
                    'project_type': 'Hourly',
                    'budget_range': '$35-65/hour',
                    'duration': 'More than 6 months',
                    'client_rating': '4.8',
                    'client_spent': '$50,000+',
                    'proposals': '5-10'
                },
                {
                    'title': 'Drupal Module Development - Custom Payment Integration',
                    'client': 'Digital Agency',
                    'location': 'Remote',
                    'url': f'https://upwork.com/jobs/drupal-module-456',
                    'description': 'Need custom Drupal module for payment gateway integration. Experience with Commerce required...',
                    'posted_date': '2024-01-02',
                    'project_type': 'Fixed Price',
                    'budget_range': '$3,000-5,000',
                    'duration': '1-3 months',
                    'client_rating': '4.9',
                    'client_spent': '$25,000+',
                    'proposals': '10-15'
                }
            ]
        
        elif platform == 'toptal':
            return [
                {
                    'title': 'Senior Drupal Architect - Enterprise Migration',
                    'client': 'Fortune 500 Company',
                    'location': 'Remote',
                    'url': f'https://toptal.com/jobs/drupal-architect-789',
                    'description': 'Elite Drupal architect needed for enterprise D7 to D10 migration. Must have scalability experience...',
                    'posted_date': '2024-01-01',
                    'project_type': 'Hourly',
                    'budget_range': '$80-120/hour',
                    'duration': '6+ months',
                    'client_tier': 'Enterprise',
                    'screening_level': 'Top 3%',
                    'proposals': 'Invitation only'
                }
            ]
        
        elif platform == 'freelancer':
            return [
                {
                    'title': 'Drupal Website Complete Build - Competition',
                    'client': 'Small Business',
                    'location': 'Global',
                    'url': f'https://freelancer.com/projects/drupal-build-101',
                    'description': 'Complete Drupal website build for service business. Need responsive design and content management...',
                    'posted_date': '2024-01-03',
                    'project_type': 'Fixed Price',
                    'budget_range': '$1,000-3,000',
                    'duration': '1-2 months',
                    'bids': '25-50',
                    'avg_bid': '$1,500',
                    'client_reviews': '4.2'
                }
            ]
        
        elif platform == 'gun.io':
            return [
                {
                    'title': 'Drupal Backend Developer - Vetted Network',
                    'client': 'Tech Startup',
                    'location': 'Remote US',
                    'url': f'https://gun.io/jobs/drupal-backend-202',
                    'description': 'Backend-focused Drupal developer for SaaS platform. API development and performance optimization...',
                    'posted_date': '2024-01-02',
                    'project_type': 'Contract',
                    'budget_range': '$70-95/hour',
                    'duration': '3-6 months',
                    'vetting_status': 'Pre-screened',
                    'match_score': '92%'
                }
            ]
        
        elif platform == 'arc.dev':
            return [
                {
                    'title': 'Remote Drupal Developer - Full Stack',
                    'client': 'Remote-First Company',
                    'location': 'Anywhere',
                    'url': f'https://arc.dev/jobs/drupal-fullstack-303',
                    'description': 'Full-stack Drupal developer for remote team. Focus on headless Drupal and React frontend...',
                    'posted_date': '2024-01-01',
                    'project_type': 'Long-term Contract',
                    'budget_range': '$55-85/hour',
                    'duration': '12+ months',
                    'timezone': 'US/EU overlap',
                    'team_size': '5-10 developers'
                }
            ]
        
        return []

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and filter freelance search results"""
        processed = []
        seen_urls = set()
        
        for result in results:
            # Remove duplicates
            url = result.get('url', '')
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Validate required fields
            if not all(result.get(field) for field in ['title', 'client', 'url']):
                logger.warning(f"Skipping invalid result: missing required fields")
                continue
            
            # Freelance-specific relevance scoring
            relevance_score = self._calculate_freelance_relevance(result)
            result['relevance_score'] = relevance_score
            
            # Only include jobs above minimum relevance threshold
            if relevance_score >= 6.0:
                processed.append(result)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return processed

    def _calculate_freelance_relevance(self, job: Dict[str, Any]) -> float:
        """Calculate freelance-specific relevance score"""
        score = 5.0  # Base score
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        platform = job.get('platform', '')
        budget_range = job.get('budget_range', '').lower()
        
        # Drupal relevance
        if 'drupal' in title:
            score += 4.0
        elif 'drupal' in description:
            score += 2.5
        
        # Experience level and complexity
        if any(level in title for level in ['senior', 'lead', 'architect', 'expert']):
            score += 2.0
        elif any(level in description for level in ['senior', 'experienced', 'expert']):
            score += 1.0
        
        # Project type preferences
        project_type = job.get('project_type', '').lower()
        if 'hourly' in project_type:
            score += 1.5  # Prefer hourly for ongoing work
        elif 'contract' in project_type:
            score += 2.0  # Long-term contracts are valuable
        
        # Budget/rate scoring
        if any(rate in budget_range for rate in ['60', '70', '80', '90', '100']):
            score += 2.0  # High-value projects
        elif any(rate in budget_range for rate in ['40', '50']):
            score += 1.0
        
        # Platform-specific bonuses
        if platform == 'toptal':
            score += 1.5  # Premium platform
        elif platform == 'gun.io':
            score += 1.0  # Vetted network
        elif platform == 'upwork':
            try:
                client_rating = float(job.get('client_rating', 0))
                if client_rating > 4.5:
                    score += 1.0  # High-rated clients
            except (ValueError, TypeError):
                pass
        
        # Duration preferences
        duration = job.get('duration', '').lower()
        if any(term in duration for term in ['6 months', '12 months', 'long term', 'ongoing']):
            score += 1.5
        elif any(term in duration for term in ['3 months', '4 months', '5 months']):
            score += 1.0
        
        # Competition level (fewer proposals is better)
        proposals = job.get('proposals', '')
        if 'invitation only' in str(proposals).lower():
            score += 2.0
        elif any(term in str(proposals).lower() for term in ['1-5', '5-10']):
            score += 1.0
        
        return min(score, 10.0)

    @tool
    def search_platform(self, query: str) -> str:
        """Freelance-specific search implementation for CrewAI tool"""
        try:
            # Parse query if it's JSON
            if query.startswith('{'):
                query_data = json.loads(query)
                search_query = query_data.get('query', query)
                platforms = query_data.get('platforms', list(self.freelance_platforms.keys()))
                project_type = query_data.get('project_type', 'development')
            else:
                search_query = query
                platforms = list(self.freelance_platforms.keys())
                project_type = 'development'
            
            # Generate freelance queries
            freelance_queries = self._generate_freelance_queries(search_query, platforms, project_type)
            
            return json.dumps({
                "platform": "freelance",
                "platforms_available": list(self.freelance_platforms.keys()),
                "queries_generated": len(freelance_queries),
                "sample_queries": [q[1] for q in freelance_queries[:3]],
                "platform_focus": {p: info['focus'] for p, info in self.freelance_platforms.items()},
                "status": "queries_ready"
            })
        except Exception as e:
            return json.dumps({"error": str(e), "platform": "freelance"})

    @tool
    def validate_search_results(self, results: str) -> str:
        """Freelance-specific result validation"""
        try:
            data = json.loads(results)
            results_list = data.get('results', [])
            
            validated = []
            platform_breakdown = defaultdict(int)
            
            for result in results_list:
                if self._is_valid_freelance_result(result):
                    validated.append(result)
                    platform_breakdown[result.get('platform', 'unknown')] += 1
            
            return json.dumps({
                "platform": "freelance",
                "total_input": len(results_list),
                "validated_results": len(validated),
                "results": validated[:10],
                "validation_rate": len(validated) / len(results_list) if results_list else 0,
                "platform_breakdown": dict(platform_breakdown),
                "avg_budget": self._calculate_avg_budget(validated)
            })
        except Exception as e:
            return json.dumps({"error": str(e), "validated_results": 0})

    def _is_valid_freelance_result(self, result: Dict[str, Any]) -> bool:
        """Check if result is valid for freelance platforms"""
        required_fields = ['title', 'client', 'url']
        
        # Check required fields
        if not all(result.get(field) for field in required_fields):
            return False
        
        # Check if URL is from supported freelance platform
        url = result.get('url', '')
        if not any(platform_info['domain'] in url for platform_info in self.freelance_platforms.values()):
            return False
        
        # Check for development/Drupal relevance
        text = f"{result.get('title', '')} {result.get('description', '')}".lower()
        if not any(term in text for term in ['drupal', 'development', 'website', 'cms']):
            return False
        
        return True

    def _calculate_avg_budget(self, validated_results: List[Dict[str, Any]]) -> str:
        """Calculate average budget from validated results"""
        budgets = []
        for result in validated_results:
            budget_range = result.get('budget_range', '')
            if budget_range and '$' in budget_range:
                # Extract numbers from budget range
                import re
                numbers = re.findall(r'\$(\d+)', budget_range)
                if len(numbers) >= 2:
                    try:
                        avg_budget = (int(numbers[0]) + int(numbers[1])) / 2
                        if '/hour' in budget_range:
                            budgets.append(avg_budget)
                        elif 'k' in budget_range.lower():
                            budgets.append(avg_budget * 1000)
                        else:
                            budgets.append(avg_budget)
                    except ValueError:
                        continue
        
        if budgets:
            avg = sum(budgets) / len(budgets)
            if avg > 1000:
                return f"${int(avg):,} (project)"
            else:
                return f"${int(avg)}/hour"
        return "N/A"

if __name__ == "__main__":
    # Test the freelance search agent
    async def test_freelance_agent():
        print("🧪 Testing Freelance Search Agent...")
        
        agent = FreelanceSearchAgent()
        
        # Create test task
        test_task = Task(
            type=TaskType.SEARCH_FREELANCE,
            data={
                "query": "Drupal Development",
                "platforms": ["upwork", "toptal", "freelancer"],
                "project_type": "website development"
            }
        )
        
        # Execute task
        result = await agent.execute_task(test_task)
        
        print(f"📊 Freelance Search Results:")
        print(f"  - Platforms: {result['platforms_searched']}")
        print(f"  - Total Queries: {result['total_queries']}")
        print(f"  - Jobs Found: {result['processed_results']}")
        print(f"  - Agent: {result['agent_id']}")
        
        # Show top jobs from each platform
        platform_jobs = {}
        for job in result['jobs']:
            platform = job.get('platform', 'unknown')
            if platform not in platform_jobs:
                platform_jobs[platform] = []
            platform_jobs[platform].append(job)
        
        print(f"\n🎯 Top Results by Platform:")
        for platform, jobs in platform_jobs.items():
            if jobs:
                top_job = jobs[0]
                print(f"  {platform.upper()}:")
                print(f"    - {top_job['title']} (Score: {top_job['relevance_score']:.1f})")
                print(f"    - Client: {top_job['client']}")
                print(f"    - Budget: {top_job.get('budget_range', 'N/A')}")
                print(f"    - Type: {top_job.get('project_type', 'N/A')}")
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ Freelance Search Agent test completed!")
    
    asyncio.run(test_freelance_agent())