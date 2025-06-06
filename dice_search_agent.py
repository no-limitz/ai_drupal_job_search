#!/usr/bin/env python3
"""
Dice Search Agent - Specialized agent for Dice.com job searches
Part of the asynchronous multi-agent job search system
"""

import asyncio
import json
import logging
from typing import Dict, List, Any
from crewai.tools import tool

from async_agent_base import SearchAgentBase
from task_manager import Task, TaskType, TaskStatus

logger = logging.getLogger(__name__)

class DiceSearchAgent(SearchAgentBase):
    """Specialized agent for Dice.com job searches with platform-specific optimizations"""
    
    def __init__(self, agent_id: str = None, **kwargs):
        if not agent_id:
            agent_id = f"dice-search-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="Dice",
            **kwargs
        )
        
        # Dice-specific configurations
        self.dice_domains = [
            "dice.com",
            "www.dice.com"
        ]
        
        self.dice_keywords = [
            "drupal",
            "drupal developer",
            "drupal cms",
            "drupal php",
            "drupal backend",
            "drupal front-end",
            "drupal architect",
            "drupal consultant"
        ]
        
        self.tech_skills = [
            "php",
            "mysql", 
            "javascript",
            "css",
            "html",
            "symfony",
            "twig",
            "composer",
            "git",
            "linux"
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.SEARCH_DICE]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process Dice search task"""
        if task.type != TaskType.SEARCH_DICE:
            raise ValueError(f"DiceSearchAgent cannot handle task type {task.type}")
        
        search_data = task.data
        query = search_data.get('query', '')
        location = search_data.get('location', 'Remote')
        
        logger.info(f"🔍 Dice search for: {query} in {location}")
        
        # Generate Dice-specific search queries
        search_queries = self._generate_dice_queries(query, location)
        
        # Simulate search execution
        results = []
        for search_query in search_queries:
            query_results = await self._execute_dice_search(search_query)
            results.extend(query_results)
        
        # Process and validate results
        processed_results = self._process_search_results(results)
        
        return {
            'platform': 'dice',
            'query': query,
            'location': location,
            'total_queries': len(search_queries),
            'raw_results': len(results),
            'processed_results': len(processed_results),
            'jobs': processed_results,
            'agent_id': self.agent_id
        }

    def _generate_dice_queries(self, base_query: str, location: str) -> List[str]:
        """Generate Dice-specific search queries with platform optimizations"""
        queries = []
        
        # Dice focuses on tech jobs, so we can be more specific
        for keyword in self.dice_keywords:
            if keyword.lower() in base_query.lower() or keyword == "drupal":
                # Standard Dice search
                query = f'{keyword} {location} site:dice.com'
                queries.append(query)
                
                # Contract specific (Dice is heavy on contract work)
                contract_query = f'{keyword} contract {location} site:dice.com'
                queries.append(contract_query)
                
                # With tech skills
                tech_query = f'{keyword} php mysql {location} site:dice.com'
                queries.append(tech_query)
        
        # Remote-specific searches (popular on Dice)
        if location.lower() in ['remote', 'anywhere']:
            queries.extend([
                f'drupal developer remote site:dice.com',
                f'drupal contract remote site:dice.com',
                f'drupal php remote site:dice.com'
            ])
        
        # Fallback query
        if not queries:
            queries.append(f'"{base_query}" {location} site:dice.com')
            
        return queries[:6]  # Dice has good content density

    async def _execute_dice_search(self, query: str) -> List[Dict[str, Any]]:
        """Execute actual Dice search (simulated for now)"""
        # Simulate API delay
        await asyncio.sleep(0.4)
        
        # Mock Dice results - replace with actual Dice API integration
        mock_results = [
            {
                'title': 'Senior Drupal Developer - Contract',
                'company': 'TechStaff Inc',
                'location': 'Remote USA',
                'url': 'https://www.dice.com/jobs/detail/12345',
                'description': 'Contract opportunity for Senior Drupal Developer. 6-month project with possible extension. Drupal 9/10, PHP 8+, MySQL...',
                'posted_date': '2024-01-01',
                'employment_type': 'Contract',
                'contract_duration': '6 months',
                'rate_range': '$85-110/hour',
                'skills_required': ['Drupal', 'PHP', 'MySQL', 'JavaScript', 'Git'],
                'security_clearance': False,
                'remote_friendly': True
            },
            {
                'title': 'Drupal Architect - Remote Contract',
                'company': 'Digital Consulting Partners',
                'location': 'Remote',
                'url': 'https://www.dice.com/jobs/detail/67890',
                'description': 'Lead Drupal architect for enterprise migration project. Experience with Drupal 8/9/10, microservices, AWS...',
                'posted_date': '2024-01-02',
                'employment_type': 'Contract',
                'contract_duration': '12 months',
                'rate_range': '$120-150/hour',
                'skills_required': ['Drupal', 'PHP', 'AWS', 'Docker', 'Kubernetes'],
                'security_clearance': False,
                'remote_friendly': True
            },
            {
                'title': 'Drupal Backend Developer - Long Term Contract',
                'company': 'Enterprise Solutions Corp',
                'location': 'Austin, TX (Remote Available)',
                'url': 'https://www.dice.com/jobs/detail/54321',
                'description': 'Backend Drupal developer for government contract. Must have experience with Drupal 9, custom modules...',
                'posted_date': '2024-01-03',
                'employment_type': 'Contract',
                'contract_duration': '18 months',
                'rate_range': '$90-120/hour',
                'skills_required': ['Drupal', 'PHP', 'MySQL', 'Linux', 'Security'],
                'security_clearance': True,
                'remote_friendly': True
            }
        ]
        
        # Add query context to results
        for result in mock_results:
            result['search_query'] = query
            result['platform'] = 'dice'
            
        return mock_results

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and filter Dice search results"""
        processed = []
        seen_urls = set()
        
        for result in results:
            # Remove duplicates
            url = result.get('url', '')
            if url in seen_urls:
                continue
            seen_urls.add(url)
            
            # Validate required fields
            if not all(result.get(field) for field in ['title', 'company', 'url']):
                logger.warning(f"Skipping invalid result: missing required fields")
                continue
            
            # Dice-specific relevance scoring
            relevance_score = self._calculate_dice_relevance(result)
            result['relevance_score'] = relevance_score
            
            # Only include jobs above minimum relevance threshold
            if relevance_score >= 6.0:
                processed.append(result)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return processed

    def _calculate_dice_relevance(self, job: Dict[str, Any]) -> float:
        """Calculate Dice-specific relevance score"""
        score = 5.0  # Base score
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        employment_type = job.get('employment_type', '').lower()
        skills = job.get('skills_required', [])
        
        # Drupal relevance
        if 'drupal' in title:
            score += 4.0
        elif 'drupal' in description:
            score += 2.5
        
        # Experience level bonuses
        if any(level in title for level in ['senior', 'lead', 'architect', 'principal']):
            score += 2.0
        elif any(level in description for level in ['senior', 'lead', 'architect']):
            score += 1.0
        
        # Contract work (Dice specializes in this)
        if 'contract' in employment_type:
            score += 2.0
        
        # Remote work bonus
        if job.get('remote_friendly'):
            score += 1.5
        
        # Rate range bonus (high-value contracts)
        rate_range = job.get('rate_range', '')
        if rate_range:
            score += 1.0
            # Bonus for high rates
            if any(rate in rate_range for rate in ['100', '110', '120', '130', '140', '150']):
                score += 0.5
        
        # Duration bonus (longer contracts are often better)
        duration = job.get('contract_duration', '')
        if duration:
            if any(term in duration for term in ['12 month', '18 month', '24 month', 'year']):
                score += 1.0
            elif any(term in duration for term in ['6 month', '9 month']):
                score += 0.5
        
        # Skills relevance
        drupal_skills = sum(1 for skill in skills if 'drupal' in skill.lower())
        tech_skills_count = sum(1 for skill in skills if skill.lower() in [s.lower() for s in self.tech_skills])
        
        score += drupal_skills * 0.5
        score += min(tech_skills_count * 0.2, 1.0)  # Cap at 1.0
        
        # Security clearance jobs often pay more
        if job.get('security_clearance'):
            score += 0.5
        
        return min(score, 10.0)

    @tool
    def search_platform(self, query: str) -> str:
        """Dice-specific search implementation for CrewAI tool"""
        try:
            # Parse query if it's JSON
            if query.startswith('{'):
                query_data = json.loads(query)
                search_query = query_data.get('query', query)
                location = query_data.get('location', 'Remote')
            else:
                search_query = query
                location = 'Remote'
            
            # Generate Dice queries
            dice_queries = self._generate_dice_queries(search_query, location)
            
            return json.dumps({
                "platform": "dice",
                "queries_generated": len(dice_queries),
                "queries": dice_queries[:3],  # Return first 3 for tool response
                "status": "queries_ready",
                "platform_focus": "contract and consulting opportunities",
                "search_tips": [
                    "Dice specializes in contract and tech consulting",
                    "Look for rate ranges and contract duration",
                    "Check for security clearance requirements"
                ]
            })
        except Exception as e:
            return json.dumps({"error": str(e), "platform": "dice"})

    @tool
    def validate_search_results(self, results: str) -> str:
        """Dice-specific result validation"""
        try:
            data = json.loads(results)
            results_list = data.get('results', [])
            
            validated = []
            contract_count = 0
            
            for result in results_list:
                if self._is_valid_dice_result(result):
                    validated.append(result)
                    if 'contract' in result.get('employment_type', '').lower():
                        contract_count += 1
            
            return json.dumps({
                "platform": "dice",
                "total_input": len(results_list),
                "validated_results": len(validated),
                "results": validated[:10],  # Return top 10
                "validation_rate": len(validated) / len(results_list) if results_list else 0,
                "contract_opportunities": contract_count,
                "avg_rate_range": self._calculate_avg_rate(validated)
            })
        except Exception as e:
            return json.dumps({"error": str(e), "validated_results": 0})

    def _is_valid_dice_result(self, result: Dict[str, Any]) -> bool:
        """Check if result is valid for Dice"""
        required_fields = ['title', 'company', 'url']
        
        # Check required fields
        if not all(result.get(field) for field in required_fields):
            return False
        
        # Check if URL is Dice
        url = result.get('url', '')
        if not any(domain in url for domain in self.dice_domains):
            return False
        
        # Check for tech relevance (Dice is tech-focused)
        text = f"{result.get('title', '')} {result.get('description', '')}".lower()
        if not any(skill in text for skill in ['drupal', 'php', 'developer', 'engineer', 'programmer']):
            return False
        
        return True

    def _calculate_avg_rate(self, validated_results: List[Dict[str, Any]]) -> str:
        """Calculate average rate range from validated results"""
        rates = []
        for result in validated_results:
            rate_range = result.get('rate_range', '')
            if rate_range and '$' in rate_range:
                # Extract numbers from rate range like "$85-110/hour"
                import re
                numbers = re.findall(r'\$(\d+)', rate_range)
                if len(numbers) >= 2:
                    try:
                        avg_rate = (int(numbers[0]) + int(numbers[1])) / 2
                        rates.append(avg_rate)
                    except ValueError:
                        continue
        
        if rates:
            return f"${int(sum(rates) / len(rates))}/hour"
        return "N/A"

if __name__ == "__main__":
    # Test the Dice search agent
    async def test_dice_agent():
        print("🧪 Testing Dice Search Agent...")
        
        agent = DiceSearchAgent()
        
        # Create test task
        test_task = Task(
            type=TaskType.SEARCH_DICE,
            data={
                "query": "Drupal Architect Contract",
                "location": "Remote"
            }
        )
        
        # Execute task
        result = await agent.execute_task(test_task)
        
        print(f"📊 Dice Search Results:")
        print(f"  - Platform: {result['platform']}")
        print(f"  - Total Queries: {result['total_queries']}")
        print(f"  - Jobs Found: {result['processed_results']}")
        print(f"  - Agent: {result['agent_id']}")
        
        # Show top job
        if result['jobs']:
            top_job = result['jobs'][0]
            print(f"\n🎯 Top Result (Score: {top_job['relevance_score']}):")
            print(f"  - {top_job['title']} at {top_job['company']}")
            print(f"  - {top_job['location']}")
            print(f"  - {top_job['employment_type']}")
            print(f"  - Rate: {top_job.get('rate_range', 'N/A')}")
            print(f"  - Duration: {top_job.get('contract_duration', 'N/A')}")
            print(f"  - Remote: {top_job.get('remote_friendly', 'N/A')}")
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ Dice Search Agent test completed!")
    
    asyncio.run(test_dice_agent())