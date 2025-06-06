#!/usr/bin/env python3
"""
Task Manager for Asynchronous Multi-Agent Job Search System
Handles job queue management, agent coordination, and result aggregation
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Callable, Any
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from collections import defaultdict
import uuid

logger = logging.getLogger(__name__)

class TaskType(Enum):
    # Search Agent Tasks
    SEARCH_LINKEDIN = "search_linkedin"
    SEARCH_INDEED = "search_indeed" 
    SEARCH_DICE = "search_dice"
    SEARCH_FREELANCE = "search_freelance"
    SEARCH_NICHE = "search_niche"
    SEARCH_STACKOVERFLOW = "search_stackoverflow"
    SEARCH_ANGELLIST = "search_angellist"
    SEARCH_REMOTEOK = "search_remoteok"
    
    # Extraction Agent Tasks
    EXTRACT_LINKEDIN = "extract_linkedin"
    EXTRACT_INDEED = "extract_indeed"
    EXTRACT_DICE = "extract_dice"
    EXTRACT_GENERIC = "extract_generic"
    VALIDATE_URL = "validate_url"
    
    # Analysis Agent Tasks
    ANALYZE_JOB = "analyze_job"
    ANALYZE_MARKET = "analyze_market"
    DETECT_DUPLICATE = "detect_duplicate"
    CALCULATE_RELEVANCE = "calculate_relevance"
    
    # Reporting Agent Tasks
    GENERATE_REPORT = "generate_report"
    SEND_NOTIFICATION = "send_notification"

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"

class TaskPriority(Enum):
    LOW = 1
    MEDIUM = 2
    HIGH = 3
    URGENT = 4

@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType = TaskType.SEARCH_LINKEDIN
    priority: TaskPriority = TaskPriority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    data: Dict[str, Any] = field(default_factory=dict)
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    dependencies: List[str] = field(default_factory=list)  # Task IDs this task depends on
    assigned_agent: Optional[str] = None

    def duration(self) -> Optional[float]:
        """Calculate task duration in seconds"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None

@dataclass
class AgentStats:
    agent_id: str
    total_tasks: int = 0
    completed_tasks: int = 0
    failed_tasks: int = 0
    avg_duration: float = 0.0
    last_activity: Optional[datetime] = None
    current_load: int = 0
    max_concurrent: int = 5

class TaskManager:
    def __init__(self, max_concurrent_tasks: int = 50):
        self.max_concurrent_tasks = max_concurrent_tasks
        self.task_queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self.active_tasks: Dict[str, Task] = {}
        self.completed_tasks: Dict[str, Task] = {}
        self.failed_tasks: Dict[str, Task] = {}
        self.agent_stats: Dict[str, AgentStats] = {}
        self.agent_pools: Dict[str, List[Callable]] = defaultdict(list)
        self.result_callbacks: List[Callable] = []
        self.running = False
        self.worker_tasks: List[asyncio.Task] = []
        
        # Performance metrics
        self.metrics = {
            'total_tasks_processed': 0,
            'tasks_per_second': 0.0,
            'avg_queue_time': 0.0,
            'error_rate': 0.0,
            'start_time': datetime.now()
        }

    async def start(self):
        """Start the task manager and worker tasks"""
        logger.info("🚀 Starting Task Manager...")
        self.running = True
        
        # Start worker tasks
        for i in range(self.max_concurrent_tasks):
            worker_task = asyncio.create_task(self._worker(f"worker-{i}"))
            self.worker_tasks.append(worker_task)
        
        # Start monitoring task
        monitor_task = asyncio.create_task(self._monitor())
        self.worker_tasks.append(monitor_task)
        
        logger.info(f"✅ Task Manager started with {self.max_concurrent_tasks} workers")

    async def stop(self):
        """Stop the task manager and all workers"""
        logger.info("🛑 Stopping Task Manager...")
        self.running = False
        
        # Cancel all worker tasks
        for task in self.worker_tasks:
            task.cancel()
        
        # Wait for all tasks to complete
        await asyncio.gather(*self.worker_tasks, return_exceptions=True)
        
        logger.info("✅ Task Manager stopped")

    async def submit_task(self, task: Task) -> str:
        """Submit a task to the queue"""
        # Check dependencies
        if task.dependencies:
            for dep_id in task.dependencies:
                if dep_id not in self.completed_tasks:
                    logger.warning(f"Task {task.id} has unmet dependency: {dep_id}")
        
        # Add to queue with priority
        priority_value = -task.priority.value  # Negative for high priority first
        await self.task_queue.put((priority_value, task.created_at.timestamp(), task))
        
        logger.debug(f"📋 Task {task.id} ({task.type.value}) submitted to queue")
        return task.id

    async def submit_search_tasks(self, search_queries: List[str]) -> List[str]:
        """Submit multiple search tasks for different platforms"""
        task_ids = []
        
        for query in search_queries:
            # Create tasks for each platform
            platforms = [
                (TaskType.SEARCH_LINKEDIN, TaskPriority.HIGH),
                (TaskType.SEARCH_INDEED, TaskPriority.HIGH), 
                (TaskType.SEARCH_DICE, TaskPriority.MEDIUM),
                (TaskType.SEARCH_FREELANCE, TaskPriority.MEDIUM),
                (TaskType.SEARCH_NICHE, TaskPriority.LOW)
            ]
            
            for task_type, priority in platforms:
                task = Task(
                    type=task_type,
                    priority=priority,
                    data={'query': query}
                )
                task_id = await self.submit_task(task)
                task_ids.append(task_id)
        
        logger.info(f"📤 Submitted {len(task_ids)} search tasks for {len(search_queries)} queries")
        return task_ids

    async def submit_extraction_tasks(self, job_urls: List[str], dependencies: List[str] = None) -> List[str]:
        """Submit extraction tasks for job URLs"""
        task_ids = []
        
        for url in job_urls:
            task = Task(
                type=TaskType.EXTRACT_JOB,
                priority=TaskPriority.HIGH,
                data={'url': url},
                dependencies=dependencies or []
            )
            task_id = await self.submit_task(task)
            task_ids.append(task_id)
        
        logger.info(f"📤 Submitted {len(task_ids)} extraction tasks")
        return task_ids

    async def get_task_status(self, task_id: str) -> Optional[TaskStatus]:
        """Get the status of a specific task"""
        if task_id in self.active_tasks:
            return self.active_tasks[task_id].status
        elif task_id in self.completed_tasks:
            return TaskStatus.COMPLETED
        elif task_id in self.failed_tasks:
            return TaskStatus.FAILED
        return None

    async def get_results(self, task_ids: List[str]) -> Dict[str, Any]:
        """Get results for completed tasks"""
        results = {}
        
        for task_id in task_ids:
            if task_id in self.completed_tasks:
                task = self.completed_tasks[task_id]
                results[task_id] = {
                    'status': 'completed',
                    'result': task.result,
                    'duration': task.duration()
                }
            elif task_id in self.failed_tasks:
                task = self.failed_tasks[task_id]
                results[task_id] = {
                    'status': 'failed',
                    'error': task.error,
                    'retry_count': task.retry_count
                }
            elif task_id in self.active_tasks:
                results[task_id] = {
                    'status': 'in_progress'
                }
            else:
                results[task_id] = {
                    'status': 'not_found'
                }
        
        return results

    def register_agent_pool(self, pool_name: str, agents: List[Callable]):
        """Register a pool of agents for specific task types"""
        self.agent_pools[pool_name] = agents
        logger.info(f"📝 Registered agent pool '{pool_name}' with {len(agents)} agents")

    def register_result_callback(self, callback: Callable):
        """Register a callback to be called when tasks complete"""
        self.result_callbacks.append(callback)

    async def _worker(self, worker_id: str):
        """Worker task that processes jobs from the queue"""
        logger.debug(f"👷 Worker {worker_id} started")
        
        while self.running:
            try:
                # Get task from queue with timeout
                try:
                    priority, timestamp, task = await asyncio.wait_for(
                        self.task_queue.get(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    continue
                
                # Process the task
                await self._process_task(task, worker_id)
                
            except Exception as e:
                logger.error(f"❌ Worker {worker_id} error: {e}")
                await asyncio.sleep(1)
        
        logger.debug(f"👷 Worker {worker_id} stopped")

    async def _process_task(self, task: Task, worker_id: str):
        """Process a single task"""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now()
        task.assigned_agent = worker_id
        self.active_tasks[task.id] = task
        
        logger.debug(f"🔄 Processing task {task.id} ({task.type.value}) with {worker_id}")
        
        try:
            # Simulate task processing (replace with actual agent calls)
            result = await self._execute_task(task)
            
            # Task completed successfully
            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now()
            task.result = result
            
            # Move to completed tasks
            self.completed_tasks[task.id] = task
            del self.active_tasks[task.id]
            
            # Update metrics
            self._update_metrics(task, success=True)
            
            # Call result callbacks
            for callback in self.result_callbacks:
                try:
                    await callback(task)
                except Exception as e:
                    logger.error(f"❌ Result callback error: {e}")
            
            logger.debug(f"✅ Task {task.id} completed in {task.duration():.2f}s")
            
        except Exception as e:
            # Task failed
            task.error = str(e)
            task.retry_count += 1
            
            if task.retry_count <= task.max_retries:
                # Retry the task
                task.status = TaskStatus.RETRYING
                await asyncio.sleep(2 ** task.retry_count)  # Exponential backoff
                await self.task_queue.put((-task.priority.value, time.time(), task))
                logger.warning(f"🔄 Retrying task {task.id} (attempt {task.retry_count}/{task.max_retries})")
            else:
                # Max retries exceeded
                task.status = TaskStatus.FAILED
                task.completed_at = datetime.now()
                self.failed_tasks[task.id] = task
                self._update_metrics(task, success=False)
                logger.error(f"❌ Task {task.id} failed permanently: {e}")
            
            if task.id in self.active_tasks:
                del self.active_tasks[task.id]

    async def _execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a specific task based on its type"""
        # This is a placeholder - will be replaced with actual agent calls
        await asyncio.sleep(0.1)  # Simulate work
        
        if task.type == TaskType.SEARCH_LINKEDIN:
            return {'search_results': [], 'urls_found': 0, 'platform': 'linkedin'}
        elif task.type == TaskType.EXTRACT_JOB:
            return {'job_data': {}, 'extracted': True, 'url': task.data.get('url')}
        elif task.type == TaskType.ANALYZE_JOB:
            return {'relevance_score': 5.0, 'analysis': 'placeholder'}
        else:
            return {'status': 'processed', 'type': task.type.value}

    def _update_metrics(self, task: Task, success: bool):
        """Update performance metrics"""
        self.metrics['total_tasks_processed'] += 1
        
        if success:
            if task.duration():
                # Update average duration (simple moving average)
                current_avg = self.metrics.get('avg_task_duration', 0.0)
                total_tasks = self.metrics['total_tasks_processed']
                self.metrics['avg_task_duration'] = (
                    (current_avg * (total_tasks - 1) + task.duration()) / total_tasks
                )
        
        # Calculate error rate
        total_failed = len(self.failed_tasks)
        total_processed = self.metrics['total_tasks_processed']
        self.metrics['error_rate'] = total_failed / total_processed if total_processed > 0 else 0.0
        
        # Calculate tasks per second
        runtime = (datetime.now() - self.metrics['start_time']).total_seconds()
        self.metrics['tasks_per_second'] = total_processed / runtime if runtime > 0 else 0.0

    async def _monitor(self):
        """Background monitoring task"""
        while self.running:
            await asyncio.sleep(30)  # Monitor every 30 seconds
            
            queue_size = self.task_queue.qsize()
            active_count = len(self.active_tasks)
            completed_count = len(self.completed_tasks)
            failed_count = len(self.failed_tasks)
            
            logger.info(
                f"📊 Task Manager Status: "
                f"Queue={queue_size}, Active={active_count}, "
                f"Completed={completed_count}, Failed={failed_count}, "
                f"Rate={self.metrics['tasks_per_second']:.2f}/s, "
                f"Error Rate={self.metrics['error_rate']:.1%}"
            )

    def get_status(self) -> Dict[str, Any]:
        """Get current task manager status"""
        return {
            'running': self.running,
            'queue_size': self.task_queue.qsize(),
            'active_tasks': len(self.active_tasks),
            'completed_tasks': len(self.completed_tasks),
            'failed_tasks': len(self.failed_tasks),
            'metrics': self.metrics,
            'agent_pools': {name: len(agents) for name, agents in self.agent_pools.items()}
        }

# Global task manager instance
_task_manager_instance = None

async def get_task_manager() -> TaskManager:
    """Get or create the global task manager instance"""
    global _task_manager_instance
    if _task_manager_instance is None:
        _task_manager_instance = TaskManager()
        await _task_manager_instance.start()
    return _task_manager_instance

if __name__ == "__main__":
    # Test the task manager
    async def test_task_manager():
        print("🧪 Testing Task Manager...")
        
        tm = TaskManager(max_concurrent_tasks=5)
        await tm.start()
        
        # Submit some test tasks
        task_ids = await tm.submit_search_tasks(['Drupal Developer', 'Senior PHP'])
        
        # Wait for completion
        await asyncio.sleep(2)
        
        # Get results
        results = await tm.get_results(task_ids)
        print(f"📊 Results: {json.dumps(results, indent=2)}")
        
        # Show status
        status = tm.get_status()
        print(f"📈 Status: {json.dumps(status, indent=2)}")
        
        await tm.stop()
        print("✅ Test completed!")
    
    asyncio.run(test_task_manager())