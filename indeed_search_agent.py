#!/usr/bin/env python3
"""
Indeed Search Agent - Specialized agent for Indeed job searches
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

class IndeedSearchAgent(SearchAgentBase):
    """Specialized agent for Indeed job searches with platform-specific optimizations"""
    
    def __init__(self, agent_id: str = None, **kwargs):
        if not agent_id:
            agent_id = f"indeed-search-{id(self)}"
        
        super().__init__(
            agent_id=agent_id,
            platform="Indeed",
            **kwargs
        )
        
        # Indeed-specific configurations
        self.indeed_domains = [
            "indeed.com",
            "indeed.ca", 
            "indeed.co.uk"
        ]
        
        self.indeed_keywords = [
            "drupal",
            "drupal developer",
            "drupal programmer",
            "drupal engineer",
            "drupal specialist",
            "cms developer drupal",
            "php drupal developer",
            "web developer drupal"
        ]
        
        self.location_modifiers = [
            "remote",
            "work from home",
            "telecommute",
            "virtual",
            "anywhere"
        ]

    def get_supported_task_types(self) -> List[TaskType]:
        """Return task types this agent can handle"""
        return [TaskType.SEARCH_INDEED]

    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process Indeed search task"""
        if task.type != TaskType.SEARCH_INDEED:
            raise ValueError(f"IndeedSearchAgent cannot handle task type {task.type}")
        
        search_data = task.data
        query = search_data.get('query', '')
        location = search_data.get('location', 'Remote')
        
        logger.info(f"🔍 Indeed search for: {query} in {location}")
        
        # Generate Indeed-specific search queries
        search_queries = self._generate_indeed_queries(query, location)
        
        # Simulate search execution
        results = []
        for search_query in search_queries:
            query_results = await self._execute_indeed_search(search_query)
            results.extend(query_results)
        
        # Process and validate results
        processed_results = self._process_search_results(results)
        
        return {
            'platform': 'indeed',
            'query': query,
            'location': location,
            'total_queries': len(search_queries),
            'raw_results': len(results),
            'processed_results': len(processed_results),
            'jobs': processed_results,
            'agent_id': self.agent_id
        }

    def _generate_indeed_queries(self, base_query: str, location: str) -> List[str]:
        """Generate Indeed-specific search queries with platform optimizations"""
        queries = []
        
        # Indeed uses different query formats
        for keyword in self.indeed_keywords:
            if keyword.lower() in base_query.lower() or keyword == "drupal":
                # Standard Indeed search
                query = f'{keyword} {location} site:indeed.com'
                queries.append(query)
                
                # Contract/freelance specific
                contract_query = f'{keyword} contract {location} site:indeed.com'
                queries.append(contract_query)
                
                # Remote specific
                remote_query = f'{keyword} remote site:indeed.com'
                queries.append(remote_query)
        
        # Fallback query
        if not queries:
            queries.append(f'"{base_query}" {location} site:indeed.com')
            
        return queries[:8]  # Limit for Indeed rate limits

    async def _execute_indeed_search(self, query: str) -> List[Dict[str, Any]]:
        """Execute actual Indeed search (simulated for now)"""
        # Simulate API delay
        await asyncio.sleep(0.3)
        
        # Mock Indeed results - replace with actual Indeed API integration
        mock_results = [
            {
                'title': 'Senior Drupal Developer (Remote)',
                'company': 'Web Development Partners',
                'location': 'Remote',
                'url': 'https://indeed.com/viewjob?jk=abc123def456',
                'description': 'Senior Drupal developer needed for long-term contract project. Must have 5+ years experience with Drupal 9/10...',
                'posted_date': '2024-01-01',
                'employment_type': 'Contract',
                'salary_estimate': '$75-95/hour',
                'company_rating': '4.2',
                'indeed_apply': True
            },
            {
                'title': 'Drupal Backend Developer - Contract',
                'company': 'Digital Solutions Group',
                'location': 'Austin, TX (Remote OK)',
                'url': 'https://indeed.com/viewjob?jk=xyz789ghi012',
                'description': 'Contract position for experienced Drupal backend developer. Working on e-commerce platform migration...',
                'posted_date': '2024-01-03',
                'employment_type': 'Contract',
                'salary_estimate': '$80-100/hour',
                'company_rating': '3.8',
                'indeed_apply': False
            },
            {
                'title': 'Freelance Drupal Developer',
                'company': 'Creative Agency LLC',
                'location': 'Nationwide Remote',
                'url': 'https://indeed.com/viewjob?jk=mnp345qrs678',
                'description': 'Freelance Drupal developer for multiple client projects. Flexible schedule, competitive rates...',
                'posted_date': '2024-01-02',
                'employment_type': 'Freelance',
                'salary_estimate': '$60-85/hour',
                'company_rating': '4.0',
                'indeed_apply': True
            }
        ]
        
        # Add query context to results
        for result in mock_results:
            result['search_query'] = query
            result['platform'] = 'indeed'
            
        return mock_results

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Process and filter Indeed search results"""
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
            
            # Indeed-specific relevance scoring
            relevance_score = self._calculate_indeed_relevance(result)
            result['relevance_score'] = relevance_score
            
            # Only include jobs above minimum relevance threshold
            if relevance_score >= 5.5:
                processed.append(result)
        
        # Sort by relevance score
        processed.sort(key=lambda x: x['relevance_score'], reverse=True)
        
        return processed

    def _calculate_indeed_relevance(self, job: Dict[str, Any]) -> float:
        """Calculate Indeed-specific relevance score"""
        score = 5.0  # Base score
        
        title = job.get('title', '').lower()
        description = job.get('description', '').lower()
        employment_type = job.get('employment_type', '').lower()
        
        # Drupal relevance
        if 'drupal' in title:
            score += 3.5
        elif 'drupal' in description:
            score += 2.0
        
        # Experience level bonuses
        if any(level in title for level in ['senior', 'lead', 'principal']):
            score += 1.5
        elif any(level in description for level in ['senior', 'lead', 'principal']):
            score += 1.0
        
        # Contract/freelance preference
        if any(term in employment_type for term in ['contract', 'freelance']):
            score += 2.0
        
        # Remote work bonus
        location = job.get('location', '').lower()
        if any(term in location for term in self.location_modifiers):
            score += 1.5
        
        # Indeed-specific bonuses
        if job.get('indeed_apply'):
            score += 0.5
            
        # Company rating bonus
        rating = job.get('company_rating')
        if rating:
            try:
                rating_float = float(rating)
                if rating_float >= 4.0:
                    score += 0.5
                elif rating_float >= 3.5:
                    score += 0.3
            except (ValueError, TypeError):
                pass
        
        # Salary information bonus
        if job.get('salary_estimate'):
            score += 0.5
        
        return min(score, 10.0)

    @tool
    def search_platform(self, query: str) -> str:
        """Indeed-specific search implementation for CrewAI tool"""
        try:
            # Parse query if it's JSON
            if query.startswith('{'):
                query_data = json.loads(query)
                search_query = query_data.get('query', query)
                location = query_data.get('location', 'Remote')
            else:
                search_query = query
                location = 'Remote'
            
            # Generate Indeed queries
            indeed_queries = self._generate_indeed_queries(search_query, location)
            
            return json.dumps({
                "platform": "indeed",
                "queries_generated": len(indeed_queries),
                "queries": indeed_queries[:3],  # Return first 3 for tool response
                "status": "queries_ready",
                "search_tips": [
                    "Use Indeed's 'Remote' location filter",
                    "Look for 'Indeed Apply' jobs for faster applications",
                    "Check company ratings for better opportunities"
                ]
            })
        except Exception as e:
            return json.dumps({"error": str(e), "platform": "indeed"})

    @tool
    def validate_search_results(self, results: str) -> str:
        """Indeed-specific result validation"""
        try:
            data = json.loads(results)
            results_list = data.get('results', [])
            
            validated = []
            for result in results_list:
                if self._is_valid_indeed_result(result):
                    validated.append(result)
            
            return json.dumps({
                "platform": "indeed",
                "total_input": len(results_list),
                "validated_results": len(validated),
                "results": validated[:10],  # Return top 10
                "validation_rate": len(validated) / len(results_list) if results_list else 0,
                "indeed_apply_count": sum(1 for r in validated if r.get('indeed_apply'))
            })
        except Exception as e:
            return json.dumps({"error": str(e), "validated_results": 0})

    def _is_valid_indeed_result(self, result: Dict[str, Any]) -> bool:
        """Check if result is valid for Indeed"""
        required_fields = ['title', 'company', 'url']
        
        # Check required fields
        if not all(result.get(field) for field in required_fields):
            return False
        
        # Check if URL is Indeed
        url = result.get('url', '')
        if not any(domain in url for domain in self.indeed_domains):
            return False
        
        # Check for Drupal relevance
        text = f"{result.get('title', '')} {result.get('description', '')}".lower()
        if 'drupal' not in text and 'cms' not in text:
            return False
        
        return True

if __name__ == "__main__":
    # Test the Indeed search agent
    async def test_indeed_agent():
        print("🧪 Testing Indeed Search Agent...")
        
        agent = IndeedSearchAgent()
        
        # Create test task
        test_task = Task(
            type=TaskType.SEARCH_INDEED,
            data={
                "query": "Drupal Developer Contract",
                "location": "Remote"
            }
        )
        
        # Execute task
        result = await agent.execute_task(test_task)
        
        print(f"📊 Indeed Search Results:")
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
            print(f"  - Indeed Apply: {top_job.get('indeed_apply', 'N/A')}")
        
        print(f"\n📈 Agent Status: {json.dumps(agent.get_status(), indent=2)}")
        print("✅ Indeed Search Agent test completed!")
    
    asyncio.run(test_indeed_agent())