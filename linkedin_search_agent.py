#!/usr/bin/env python3
"""
LinkedIn Search Agent - Specialized agent for LinkedIn job searches
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

class LinkedInSearchAgent(SearchAgentBase):
    """Specialized agent for LinkedIn job searches with platform-specific optimizations"""
    
    def __init__(self, agent_id: str = None, **kwargs):
        if not agent_id:
            agent_id = f"linkedin-search-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="LinkedIn",
            **kwargs
        )
        
        # LinkedIn-specific configurations
        self.linkedin_domains = [
            "linkedin.com/jobs",
            "linkedin.com/in",
            "linkedin.com/company"
        ]
        
        self.linkedin_keywords = [
            "drupal developer",
            "drupal architect", 
            "drupal backend",
            "drupal cms",
            "drupal site builder",
            "drupal module developer",
            "php drupal",
            "senior drupal",
            "lead drupal"
        ]
        
        self.contract_keywords = [
            "contract",
            "freelance", 
            "consultant",
            "temporary",
            "project-based",
            "part-time"
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.SEARCH_LINKEDIN]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process LinkedIn search task"""
        if task.type != TaskType.SEARCH_LINKEDIN:
            raise ValueError(f"LinkedInSearchAgent cannot handle task type {task.type}")
        
        search_data = task.data
        query = search_data.get('query', '')
        location = search_data.get('location', 'Remote')
        
        logger.info(f"🔍 LinkedIn search for: {query} in {location}")
        
        # Generate LinkedIn-specific search queries
        search_queries = self._generate_linkedin_queries(query, location)
        
        # Simulate search execution (replace with actual LinkedIn API/scraping)
        results = []
        for search_query in search_queries:
            query_results = await self._execute_linkedin_search(search_query)
            results.extend(query_results)
        
        # Process and validate results
        processed_results = self._process_search_results(results)
        
        return {
            'platform': 'linkedin',
            'query': query,
            'location': location,
            'total_queries': len(search_queries),
            'raw_results': len(results),
            'processed_results': len(processed_results),
            'jobs': processed_results,
            'agent_id': self.agent_id
        }

    def _generate_linkedin_queries(self, base_query: str, location: str) -> List[str]:
        """Generate LinkedIn-specific search queries with platform optimizations"""
        queries = []
        
        # Base query variations
        for keyword in self.linkedin_keywords:
            if keyword.lower() in base_query.lower():
                # Core search
                query = f'"{keyword}" {location} site:linkedin.com/jobs'
                queries.append(query)
                
                # Contract variations
                for contract_type in self.contract_keywords:
                    contract_query = f'"{keyword}" {contract_type} {location} site:linkedin.com/jobs'
                    queries.append(contract_query)
        
        # If no keyword matches, use base query
        if not queries:
            queries.append(f'"{base_query}" {location} site:linkedin.com/jobs')
            
        return queries[:10]  # Limit to prevent rate limiting

    async def _execute_linkedin_search(self, query: str) -> List[Dict[str, Any]]:
        """Execute actual LinkedIn search (simulated for now)"""
        # Simulate API delay
        await asyncio.sleep(0.5)
        
        # Mock results - replace with actual LinkedIn API integration
        mock_results = [
            {
                'title': 'Senior Drupal Developer - Remote',
                'company': 'Tech Solutions Inc.',
                'location': 'Remote, USA',
                'url': 'https://linkedin.com/jobs/view/123456789',
                'description': 'We are seeking a Senior Drupal Developer for remote contract work...',
                'posted_date': '2024-01-01',
                'employment_type': 'Contract',
                'experience_level': 'Senior',
                'salary_range': '$80-120/hour'
            },
            {
                'title': 'Drupal Technical Lead',
                'company': 'Digital Agency Corp',
                'location': 'New York, NY (Remote OK)',
                'url': 'https://linkedin.com/jobs/view/987654321',
                'description': 'Lead Drupal developer position with remote flexibility...',
                'posted_date': '2024-01-02',
                'employment_type': 'Full-time',
                'experience_level': 'Lead',
                'salary_range': '$120,000-150,000'
            }
        ]
        
        # Add query context to results
        for result in mock_results:
            result['search_query'] = query
            result['platform'] = 'linkedin'
            
        return mock_results

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and filter LinkedIn search results"""
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
            
            # LinkedIn-specific relevance scoring
            relevance_score = self._calculate_linkedin_relevance(result)
            result['relevance_score'] = relevance_score
            
            # Only include jobs above minimum relevance threshold
            if relevance_score >= 6.0:
                processed.append(result)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return processed

    def _calculate_linkedin_relevance(self, job: Dict[str, Any]) -> float:
        """Calculate LinkedIn-specific relevance score"""
        score = 5.0  # Base score
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        employment_type = job.get('employment_type', '').lower()
        
        # Drupal relevance
        if 'drupal' in title:
            score += 4.0
        elif 'drupal' in description:
            score += 2.0
        
        # Experience level bonuses
        if any(level in title for level in ['senior', 'lead', 'principal', 'architect']):
            score += 2.0
        
        # Contract/freelance preference
        if any(term in employment_type for term in ['contract', 'freelance', 'temporary']):
            score += 1.5
        
        # Remote work bonus
        location = job.get('location', '').lower()
        if any(term in location for term in ['remote', 'work from home', 'anywhere']):
            score += 1.0
        
        # LinkedIn-specific bonuses
        if 'linkedin.com/jobs' in job.get('url', ''):
            score += 0.5
            
        # Salary information bonus
        if job.get('salary_range'):
            score += 0.5
        
        return min(score, 10.0)

    @tool
    def search_platform(self, query: str) -> str:
        """LinkedIn-specific search implementation for CrewAI tool"""
        # This is called by the CrewAI agent
        try:
            # Parse query if it's JSON
            if query.startswith('{'):
                query_data = json.loads(query)
                search_query = query_data.get('query', query)
                location = query_data.get('location', 'Remote')
            else:
                search_query = query
                location = 'Remote'
            
            # Generate LinkedIn queries
            linkedin_queries = self._generate_linkedin_queries(search_query, location)
            
            return json.dumps({
                "platform": "linkedin",
                "queries_generated": len(linkedin_queries),
                "queries": linkedin_queries[:3],  # Return first 3 for tool response
                "status": "queries_ready"
            })
        except Exception as e:
            return json.dumps({"error": str(e), "platform": "linkedin"})

    @tool
    def validate_search_results(self, results: str) -> str:
        """LinkedIn-specific result validation"""
        try:
            data = json.loads(results)
            results_list = data.get('results', [])
            
            validated = []
            for result in results_list:
                # LinkedIn-specific validation
                if self._is_valid_linkedin_result(result):
                    validated.append(result)
            
            return json.dumps({
                "platform": "linkedin",
                "total_input": len(results_list),
                "validated_results": len(validated),
                "results": validated[:10],  # Return top 10
                "validation_rate": len(validated) / len(results_list) if results_list else 0
            })
        except Exception as e:
            return json.dumps({"error": str(e), "validated_results": 0})

    def _is_valid_linkedin_result(self, result: Dict[str, Any]) -> bool:
        """Check if result is valid for LinkedIn"""
        required_fields = ['title', 'company', 'url']
        
        # Check required fields
        if not all(result.get(field) for field in required_fields):
            return False
        
        # Check if URL is LinkedIn
        url = result.get('url', '')
        if not any(domain in url for domain in self.linkedin_domains):
            return False
        
        # Check for Drupal relevance
        text = f"{result.get('title', '')} {result.get('description', '')}".lower()
        if 'drupal' not in text:
            return False
        
        return True

if __name__ == "__main__":
    # Test the LinkedIn search agent
    async def test_linkedin_agent():
        print("🧪 Testing LinkedIn Search Agent...")
        
        agent = LinkedInSearchAgent()
        
        # Create test task
        test_task = Task(
            type=TaskType.SEARCH_LINKEDIN,
            data={
                "query": "Senior Drupal Developer",
                "location": "Remote USA"
            }
        )
        
        # Execute task
        result = await agent.execute_task(test_task)
        
        print(f"📊 LinkedIn Search Results:")
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
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ LinkedIn Search Agent test completed!")
    
    asyncio.run(test_linkedin_agent())