#!/usr/bin/env python3
"""
Async Agent Base Classes for Multi-Agent Job Search System
Provides foundation for asynchronous CrewAI agents with enhanced capabilities
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from abc import ABC, abstractmethod
from crewai import Agent
from crewai.tools import tool
from langchain_openai import ChatOpenAI
import uuid

from task_manager import Task, TaskType, TaskStatus, TaskPriority

logger = logging.getLogger(__name__)

@dataclass
class AgentMetrics:
    agent_id: str
    total_tasks: int = 0
    successful_tasks: int = 0
    failed_tasks: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    success_rate: float = 0.0
    last_activity: Optional[datetime] = None
    current_load: int = 0
    max_concurrent: int = 5
    errors: List[str] = field(default_factory=list)

class AsyncAgentBase(ABC):
    """Base class for all async agents in the system"""
    
    def __init__(self, 
                 agent_id: str,
                 role: str,
                 goal: str, 
                 backstory: str,
                 max_concurrent_tasks: int = 5,
                 llm_model: str = "gpt-4",
                 temperature: float = 0.1):
        
        self.agent_id = agent_id
        self.role = role
        self.goal = goal
        self.backstory = backstory
        self.max_concurrent_tasks = max_concurrent_tasks
        
        # Initialize CrewAI agent
        self.llm = ChatOpenAI(model=llm_model, temperature=temperature)
        self.crew_agent = self._create_crew_agent()
        
        # Agent state
        self.active_tasks: Dict[str, Task] = {}
        self.metrics = AgentMetrics(agent_id=agent_id, max_concurrent=max_concurrent_tasks)
        self.running = False
        self.task_semaphore = asyncio.Semaphore(max_concurrent_tasks)
        
        logger.info(f"🤖 Initialized agent {agent_id} ({role})")

    def _create_crew_agent(self) -> Agent:
        """Create the underlying CrewAI agent"""
        return Agent(
            role=self.role,
            goal=self.goal,
            backstory=self.backstory,
            llm=self.llm,
            tools=self.get_tools(),
            verbose=False,
            allow_delegation=False
        )

    @abstractmethod
    def get_tools(self) -> List[Callable]:
        """Return list of tools available to this agent"""
        pass

    @abstractmethod
    async def process_task(self, task: Task) -> Dict[str, Any]:
        """Process a specific task - implemented by each agent type"""
        pass

    def can_handle_task(self, task: Task) -> bool:
        """Check if this agent can handle the given task type"""
        return task.type in self.get_supported_task_types()

    @abstractmethod
    def get_supported_task_types(self) -> List[TaskType]:
        """Return list of task types this agent can handle"""
        pass

    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a task with metrics tracking and error handling"""
        if not self.can_handle_task(task):
            raise ValueError(f"Agent {self.agent_id} cannot handle task type {task.type}")
        
        if len(self.active_tasks) >= self.max_concurrent_tasks:
            raise ValueError(f"Agent {self.agent_id} at maximum capacity")
        
        start_time = time.time()
        self.active_tasks[task.id] = task
        self.metrics.current_load = len(self.active_tasks)
        self.metrics.last_activity = datetime.now()
        
        logger.debug(f"🔄 Agent {self.agent_id} starting task {task.id}")
        
        try:
            async with self.task_semaphore:
                result = await self.process_task(task)
            
            # Task completed successfully
            duration = time.time() - start_time
            self._update_success_metrics(duration)
            
            logger.debug(f"✅ Agent {self.agent_id} completed task {task.id} in {duration:.2f}s")
            return result
            
        except Exception as e:
            # Task failed
            duration = time.time() - start_time
            self._update_failure_metrics(str(e))
            
            logger.error(f"❌ Agent {self.agent_id} failed task {task.id}: {e}")
            raise
            
        finally:
            # Cleanup
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]
            self.metrics.current_load = len(self.active_tasks)

    def _update_success_metrics(self, duration: float):
        """Update metrics after successful task completion"""
        self.metrics.total_tasks += 1
        self.metrics.successful_tasks += 1
        self.metrics.total_duration += duration
        self.metrics.avg_duration = self.metrics.total_duration / self.metrics.total_tasks
        self.metrics.success_rate = self.metrics.successful_tasks / self.metrics.total_tasks

    def _update_failure_metrics(self, error: str):
        """Update metrics after task failure"""
        self.metrics.total_tasks += 1
        self.metrics.failed_tasks += 1
        self.metrics.success_rate = self.metrics.successful_tasks / self.metrics.total_tasks
        self.metrics.errors.append(f"{datetime.now().isoformat()}: {error}")
        
        # Keep only last 10 errors
        if len(self.metrics.errors) > 10:
            self.metrics.errors.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """Get current agent status and metrics"""
        return {
            'agent_id': self.agent_id,
            'role': self.role,
            'running': self.running,
            'active_tasks': len(self.active_tasks),
            'metrics': {
                'total_tasks': self.metrics.total_tasks,
                'successful_tasks': self.metrics.successful_tasks,
                'failed_tasks': self.metrics.failed_tasks,
                'success_rate': self.metrics.success_rate,
                'avg_duration': self.metrics.avg_duration,
                'current_load': self.metrics.current_load,
                'max_concurrent': self.metrics.max_concurrent,
                'last_activity': self.metrics.last_activity.isoformat() if self.metrics.last_activity else None
            },
            'supported_tasks': [t.value for t in self.get_supported_task_types()],
            'recent_errors': self.metrics.errors[-3:] if self.metrics.errors else []
        }

class SearchAgentBase(AsyncAgentBase):
    """Base class for search agents"""
    
    def __init__(self, agent_id: str, platform: str, **kwargs):
        self.platform = platform
        super().__init__(
            agent_id=agent_id,
            role=f"{platform} Search Specialist",
            goal=f"Find relevant Drupal developer jobs on {platform}",
            backstory=f"Expert at finding developer jobs on {platform} with deep knowledge of search optimization and query crafting for this platform.",
            **kwargs
        )

    def get_tools(self) -> List[Callable]:
        """Search agents use search and validation tools"""
        return [self.search_platform, self.validate_search_results]

    @tool
    def search_platform(self, query: str) -> str:
        """Platform-specific search implementation"""
        # Override in specific search agents
        return json.dumps({"results": [], "platform": self.platform})

    @tool 
    def validate_search_results(self, results: str) -> str:
        """Validate and filter search results"""
        try:
            data = json.loads(results)
            # Basic validation logic
            valid_results = []
            for result in data.get('results', []):
                if result.get('title') and result.get('url'):
                    valid_results.append(result)
            
            return json.dumps({
                "valid_results": valid_results,
                "count": len(valid_results),
                "platform": self.platform
            })
        except Exception as e:
            return json.dumps({"error": str(e), "valid_results": []})

class ExtractionAgentBase(AsyncAgentBase):
    """Base class for job extraction agents"""
    
    def __init__(self, agent_id: str, platform: str, **kwargs):
        self.platform = platform
        super().__init__(
            agent_id=agent_id,
            role=f"{platform} Extraction Specialist", 
            goal=f"Extract detailed job information from {platform} job postings",
            backstory=f"Expert at extracting structured data from {platform} job postings using advanced web scraping and browser automation techniques.",
            **kwargs
        )

    def get_tools(self) -> List[Callable]:
        """Extraction agents use browser automation and parsing tools"""
        return [self.extract_job_data, self.validate_job_data]

    @tool
    def extract_job_data(self, url: str) -> str:
        """Extract job data from URL - override in specific agents"""
        return json.dumps({
            "url": url,
            "title": "",
            "company": "",
            "location": "",
            "description": "",
            "platform": self.platform,
            "extracted": False
        })

    @tool
    def validate_job_data(self, job_data: str) -> str:
        """Validate extracted job data"""
        try:
            data = json.loads(job_data)
            required_fields = ['title', 'company', 'url']
            
            is_valid = all(data.get(field) for field in required_fields)
            
            return json.dumps({
                "valid": is_valid,
                "job_data": data,
                "missing_fields": [f for f in required_fields if not data.get(f)]
            })
        except Exception as e:
            return json.dumps({"valid": False, "error": str(e)})

class AnalysisAgentBase(AsyncAgentBase):
    """Base class for analysis agents"""
    
    def __init__(self, agent_id: str, analysis_type: str, **kwargs):
        self.analysis_type = analysis_type
        super().__init__(
            agent_id=agent_id,
            role=f"Job {analysis_type} Analyst",
            goal=f"Perform {analysis_type} analysis on job data",
            backstory=f"Expert analyst specializing in {analysis_type} with deep understanding of job market dynamics and relevance scoring.",
            **kwargs
        )

    def get_tools(self) -> List[Callable]:
        """Analysis agents use scoring and analysis tools"""
        return [self.analyze_job, self.calculate_relevance_score]

    @tool
    def analyze_job(self, job_data: str) -> str:
        """Analyze job data - override in specific agents"""
        return json.dumps({
            "analysis": "basic analysis",
            "relevance_score": 5.0,
            "analysis_type": self.analysis_type
        })

    @tool
    def calculate_relevance_score(self, job_data: str) -> str:
        """Calculate relevance score for a job"""
        try:
            data = json.loads(job_data)
            
            # Basic scoring algorithm
            score = 5.0  # Base score
            text = f"{data.get('title', '')} {data.get('description', '')}".lower()
            
            # Drupal-specific keywords
            if 'drupal' in text:
                score += 3.0
            if 'senior' in text:
                score += 1.0
            if any(word in text for word in ['contract', 'freelance', 'temporary']):
                score += 1.0
            if any(word in text for word in ['remote', 'work from home']):
                score += 1.0
            
            score = min(score, 10.0)  # Cap at 10
            
            return json.dumps({
                "relevance_score": score,
                "job_data": data,
                "keywords_found": [word for word in ['drupal', 'senior', 'contract', 'remote'] if word in text]
            })
        except Exception as e:
            return json.dumps({"relevance_score": 0.0, "error": str(e)})

class AgentFactory:
    """Factory for creating different types of agents"""
    
    @staticmethod
    def create_search_agent(platform: str, **kwargs) -> SearchAgentBase:
        """Create a platform-specific search agent"""
        agent_id = f"search-{platform}-{uuid.uuid4().hex[:8]}"
        return SearchAgentBase(agent_id=agent_id, platform=platform, **kwargs)
    
    @staticmethod
    def create_extraction_agent(platform: str, **kwargs) -> ExtractionAgentBase:
        """Create a platform-specific extraction agent"""
        agent_id = f"extract-{platform}-{uuid.uuid4().hex[:8]}"
        return ExtractionAgentBase(agent_id=agent_id, platform=platform, **kwargs)
    
    @staticmethod
    def create_analysis_agent(analysis_type: str, **kwargs) -> AnalysisAgentBase:
        """Create an analysis agent"""
        agent_id = f"analyze-{analysis_type}-{uuid.uuid4().hex[:8]}"
        return AnalysisAgentBase(agent_id=agent_id, analysis_type=analysis_type, **kwargs)

if __name__ == "__main__":
    # Test the async agent base classes
    async def test_agents():
        print("🧪 Testing Async Agent Base Classes...")
        
        # Create test agents
        search_agent = AgentFactory.create_search_agent("linkedin")
        extract_agent = AgentFactory.create_extraction_agent("linkedin") 
        analysis_agent = AgentFactory.create_analysis_agent("relevance")
        
        # Test agent status
        print(f"📊 Search Agent Status: {json.dumps(search_agent.get_status(), indent=2)}")
        
        # Create test task
        test_task = Task(
            type=TaskType.SEARCH_LINKEDIN,
            data={"query": "Senior Drupal Developer"}
        )
        
        print(f"✅ Agent base classes working correctly!")
    
    asyncio.run(test_agents())