#!/usr/bin/env python3
"""
Agent Pool Manager for Multi-Agent Job Search System
Manages creation, monitoring, health checks, and cleanup of agent pools
"""

import asyncio
import logging
import time
import json
from typing import Dict, List, Optional, Type, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import uuid

from async_agent_base import AsyncAgentBase, AgentFactory, SearchAgentBase, ExtractionAgentBase, AnalysisAgentBase
from task_manager import Task, TaskType, TaskStatus, get_task_manager

logger = logging.getLogger(__name__)

class PoolStatus(Enum):
    INITIALIZING = "initializing"
    RUNNING = "running" 
    SCALING = "scaling"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"

@dataclass
class PoolConfig:
    name: str
    min_agents: int = 2
    max_agents: int = 10
    agent_type: str = "search"  # search, extraction, analysis
    platform: str = "generic"
    auto_scale: bool = True
    scale_up_threshold: float = 0.8  # Scale up when 80% loaded
    scale_down_threshold: float = 0.3  # Scale down when 30% loaded
    health_check_interval: int = 30  # seconds
    max_idle_time: int = 300  # seconds before considering agent idle

@dataclass 
class PoolMetrics:
    total_agents: int = 0
    active_agents: int = 0
    idle_agents: int = 0
    failed_agents: int = 0
    total_tasks_processed: int = 0
    avg_response_time: float = 0.0
    current_load: float = 0.0  # 0.0 to 1.0
    last_scale_action: Optional[datetime] = None
    errors: List[str] = field(default_factory=list)

class AgentPool:
    """Manages a pool of homogeneous agents"""
    
    def __init__(self, config: PoolConfig):
        self.config = config
        self.pool_id = f"{config.name}-{uuid.uuid4().hex[:8]}"
        self.agents: Dict[str, AsyncAgentBase] = {}
        self.status = PoolStatus.INITIALIZING
        self.metrics = PoolMetrics()
        self.health_check_task: Optional[asyncio.Task] = None
        self.auto_scale_task: Optional[asyncio.Task] = None
        self.last_activity = datetime.now()
        
        logger.info(f"🏊 Created agent pool {self.pool_id} ({config.name})")

    async def start(self):
        """Start the agent pool"""
        logger.info(f"🚀 Starting agent pool {self.pool_id}...")
        self.status = PoolStatus.RUNNING
        
        # Create initial agents
        await self._scale_to(self.config.min_agents)
        
        # Start background tasks
        if self.config.auto_scale:
            self.auto_scale_task = asyncio.create_task(self._auto_scale_loop())
        
        self.health_check_task = asyncio.create_task(self._health_check_loop())
        
        logger.info(f"✅ Agent pool {self.pool_id} started with {len(self.agents)} agents")

    async def stop(self):
        """Stop the agent pool and cleanup all agents"""
        logger.info(f"🛑 Stopping agent pool {self.pool_id}...")
        self.status = PoolStatus.STOPPING
        
        # Cancel background tasks
        if self.auto_scale_task:
            self.auto_scale_task.cancel()
        if self.health_check_task:
            self.health_check_task.cancel()
        
        # Stop all agents
        await self._scale_to(0)
        
        self.status = PoolStatus.STOPPED
        logger.info(f"✅ Agent pool {self.pool_id} stopped")

    async def get_available_agent(self, task: Task) -> Optional[AsyncAgentBase]:
        """Get an available agent that can handle the task"""
        suitable_agents = [
            agent for agent in self.agents.values()
            if agent.can_handle_task(task) and len(agent.active_tasks) < agent.max_concurrent_tasks
        ]
        
        if not suitable_agents:
            return None
        
        # Return agent with lowest current load
        return min(suitable_agents, key=lambda a: len(a.active_tasks))

    async def execute_task(self, task: Task) -> Dict[str, Any]:
        """Execute a task using an available agent from the pool"""
        agent = await self.get_available_agent(task)
        
        if not agent:
            raise ValueError(f"No available agent in pool {self.pool_id} for task {task.type}")
        
        self.last_activity = datetime.now()
        
        try:
            result = await agent.execute_task(task)
            self._update_success_metrics()
            return result
        except Exception as e:
            self._update_failure_metrics(str(e))
            raise

    async def _scale_to(self, target_count: int):
        """Scale the pool to target number of agents"""
        current_count = len(self.agents)
        
        if target_count == current_count:
            return
        
        logger.info(f"🔄 Scaling pool {self.pool_id} from {current_count} to {target_count} agents")
        self.status = PoolStatus.SCALING
        
        if target_count > current_count:
            # Scale up - create new agents
            for i in range(target_count - current_count):
                await self._create_agent()
        else:
            # Scale down - remove agents
            agents_to_remove = list(self.agents.values())[:current_count - target_count]
            for agent in agents_to_remove:
                await self._remove_agent(agent.agent_id)
        
        self.status = PoolStatus.RUNNING
        self.metrics.last_scale_action = datetime.now()
        self._update_metrics()

    async def _create_agent(self) -> AsyncAgentBase:
        """Create and add a new agent to the pool"""
        try:
            if self.config.agent_type == "search":
                agent = AgentFactory.create_search_agent(self.config.platform)
            elif self.config.agent_type == "extraction":
                agent = AgentFactory.create_extraction_agent(self.config.platform)
            elif self.config.agent_type == "analysis":
                agent = AgentFactory.create_analysis_agent(self.config.platform)
            else:
                raise ValueError(f"Unknown agent type: {self.config.agent_type}")
            
            self.agents[agent.agent_id] = agent
            logger.debug(f"➕ Created agent {agent.agent_id} in pool {self.pool_id}")
            return agent
            
        except Exception as e:
            logger.error(f"❌ Failed to create agent in pool {self.pool_id}: {e}")
            self.metrics.errors.append(f"{datetime.now().isoformat()}: {str(e)}")
            raise

    async def _remove_agent(self, agent_id: str):
        """Remove an agent from the pool"""
        if agent_id not in self.agents:
            return
        
        agent = self.agents[agent_id]
        
        # Wait for agent to finish current tasks
        max_wait = 30  # seconds
        start_time = time.time()
        
        while agent.active_tasks and (time.time() - start_time) < max_wait:
            await asyncio.sleep(1)
        
        # Force cleanup if still has active tasks
        if agent.active_tasks:
            logger.warning(f"⚠️ Force removing agent {agent_id} with {len(agent.active_tasks)} active tasks")
        
        del self.agents[agent_id]
        logger.debug(f"➖ Removed agent {agent_id} from pool {self.pool_id}")

    def _calculate_load(self) -> float:
        """Calculate current pool load (0.0 to 1.0)"""
        if not self.agents:
            return 0.0
        
        total_capacity = sum(agent.max_concurrent_tasks for agent in self.agents.values())
        current_load = sum(len(agent.active_tasks) for agent in self.agents.values())
        
        return current_load / total_capacity if total_capacity > 0 else 0.0

    async def _auto_scale_loop(self):
        """Background task for automatic scaling"""
        while self.status == PoolStatus.RUNNING:
            try:
                await asyncio.sleep(10)  # Check every 10 seconds
                
                current_load = self._calculate_load()
                current_count = len(self.agents)
                
                # Scale up if load is high
                if (current_load > self.config.scale_up_threshold and 
                    current_count < self.config.max_agents):
                    
                    new_count = min(current_count + 1, self.config.max_agents)
                    logger.info(f"📈 Auto-scaling UP pool {self.pool_id}: load={current_load:.2f}")
                    await self._scale_to(new_count)
                
                # Scale down if load is low
                elif (current_load < self.config.scale_down_threshold and 
                      current_count > self.config.min_agents):
                    
                    # Only scale down if agents have been idle for a while
                    idle_time = (datetime.now() - self.last_activity).total_seconds()
                    if idle_time > 60:  # 1 minute idle
                        new_count = max(current_count - 1, self.config.min_agents)
                        logger.info(f"📉 Auto-scaling DOWN pool {self.pool_id}: load={current_load:.2f}")
                        await self._scale_to(new_count)
                
            except Exception as e:
                logger.error(f"❌ Auto-scale error in pool {self.pool_id}: {e}")
                await asyncio.sleep(30)

    async def _health_check_loop(self):
        """Background task for health monitoring"""
        while self.status == PoolStatus.RUNNING:
            try:
                await asyncio.sleep(self.config.health_check_interval)
                await self._perform_health_check()
                
            except Exception as e:
                logger.error(f"❌ Health check error in pool {self.pool_id}: {e}")
                await asyncio.sleep(60)

    async def _perform_health_check(self):
        """Perform health check on all agents"""
        failed_agents = []
        
        for agent_id, agent in self.agents.items():
            # Check if agent is responsive
            if self._is_agent_healthy(agent):
                continue
            else:
                logger.warning(f"🏥 Agent {agent_id} failed health check")
                failed_agents.append(agent_id)
        
        # Replace failed agents
        for agent_id in failed_agents:
            await self._remove_agent(agent_id)
            await self._create_agent()
        
        self._update_metrics()

    def _is_agent_healthy(self, agent: AsyncAgentBase) -> bool:
        """Check if an agent is healthy"""
        # Check if agent has been active recently
        if agent.metrics.last_activity:
            idle_time = (datetime.now() - agent.metrics.last_activity).total_seconds()
            if idle_time > self.config.max_idle_time and agent.active_tasks:
                return False
        
        # Check success rate
        if agent.metrics.total_tasks > 10 and agent.metrics.success_rate < 0.5:
            return False
        
        return True

    def _update_metrics(self):
        """Update pool metrics"""
        self.metrics.total_agents = len(self.agents)
        self.metrics.active_agents = sum(1 for agent in self.agents.values() if agent.active_tasks)
        self.metrics.idle_agents = self.metrics.total_agents - self.metrics.active_agents
        self.metrics.current_load = self._calculate_load()
        
        if self.agents:
            total_tasks = sum(agent.metrics.total_tasks for agent in self.agents.values())
            total_duration = sum(agent.metrics.total_duration for agent in self.agents.values())
            self.metrics.total_tasks_processed = total_tasks
            self.metrics.avg_response_time = total_duration / total_tasks if total_tasks > 0 else 0.0

    def _update_success_metrics(self):
        """Update metrics after successful task"""
        pass  # Metrics are tracked at agent level

    def _update_failure_metrics(self, error: str):
        """Update metrics after failed task"""
        self.metrics.errors.append(f"{datetime.now().isoformat()}: {error}")
        
        # Keep only last 20 errors
        if len(self.metrics.errors) > 20:
            self.metrics.errors.pop(0)

    def get_status(self) -> Dict[str, Any]:
        """Get current pool status"""
        return {
            'pool_id': self.pool_id,
            'name': self.config.name,
            'status': self.status.value,
            'config': {
                'min_agents': self.config.min_agents,
                'max_agents': self.config.max_agents,
                'agent_type': self.config.agent_type,
                'platform': self.config.platform,
                'auto_scale': self.config.auto_scale
            },
            'metrics': {
                'total_agents': self.metrics.total_agents,
                'active_agents': self.metrics.active_agents,
                'idle_agents': self.metrics.idle_agents,
                'current_load': self.metrics.current_load,
                'total_tasks_processed': self.metrics.total_tasks_processed,
                'avg_response_time': self.metrics.avg_response_time,
                'last_scale_action': self.metrics.last_scale_action.isoformat() if self.metrics.last_scale_action else None
            },
            'agents': {agent_id: agent.get_status() for agent_id, agent in self.agents.items()}
        }

class AgentPoolManager:
    """Manages multiple agent pools"""
    
    def __init__(self):
        self.pools: Dict[str, AgentPool] = {}
        self.running = False
        self.monitor_task: Optional[asyncio.Task] = None
        
        logger.info("🏊‍♀️ Initialized Agent Pool Manager")

    async def start(self):
        """Start the pool manager"""
        logger.info("🚀 Starting Agent Pool Manager...")
        self.running = True
        
        # Start monitoring task
        self.monitor_task = asyncio.create_task(self._monitor_pools())
        
        logger.info("✅ Agent Pool Manager started")

    async def stop(self):
        """Stop all pools and cleanup"""
        logger.info("🛑 Stopping Agent Pool Manager...")
        self.running = False
        
        # Cancel monitoring
        if self.monitor_task:
            self.monitor_task.cancel()
        
        # Stop all pools
        stop_tasks = [pool.stop() for pool in self.pools.values()]
        await asyncio.gather(*stop_tasks, return_exceptions=True)
        
        self.pools.clear()
        logger.info("✅ Agent Pool Manager stopped")

    async def create_pool(self, config: PoolConfig) -> str:
        """Create and start a new agent pool"""
        pool = AgentPool(config)
        await pool.start()
        
        self.pools[pool.pool_id] = pool
        logger.info(f"✅ Created and started pool {pool.pool_id} ({config.name})")
        
        return pool.pool_id

    async def remove_pool(self, pool_id: str):
        """Stop and remove a pool"""
        if pool_id not in self.pools:
            logger.warning(f"⚠️ Pool {pool_id} not found")
            return
        
        pool = self.pools[pool_id]
        await pool.stop()
        del self.pools[pool_id]
        
        logger.info(f"✅ Removed pool {pool_id}")

    async def execute_task(self, task: Task, preferred_pool: Optional[str] = None) -> Dict[str, Any]:
        """Execute a task using the best available pool"""
        # Try preferred pool first
        if preferred_pool and preferred_pool in self.pools:
            try:
                return await self.pools[preferred_pool].execute_task(task)
            except ValueError:
                pass  # Fall back to other pools
        
        # Find a suitable pool
        suitable_pools = [
            pool for pool in self.pools.values()
            if await pool.get_available_agent(task) is not None
        ]
        
        if not suitable_pools:
            raise ValueError(f"No available agents for task {task.type}")
        
        # Use pool with lowest load
        best_pool = min(suitable_pools, key=lambda p: p._calculate_load())
        return await best_pool.execute_task(task)

    async def _monitor_pools(self):
        """Background monitoring of all pools"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Monitor every minute
                
                total_agents = sum(len(pool.agents) for pool in self.pools.values())
                active_pools = sum(1 for pool in self.pools.values() if pool.status == PoolStatus.RUNNING)
                
                logger.info(
                    f"🏊‍♀️ Pool Manager Status: "
                    f"{active_pools}/{len(self.pools)} pools running, "
                    f"{total_agents} total agents"
                )
                
            except Exception as e:
                logger.error(f"❌ Pool monitoring error: {e}")

    def get_status(self) -> Dict[str, Any]:
        """Get status of all pools"""
        return {
            'running': self.running,
            'total_pools': len(self.pools),
            'pools': {pool_id: pool.get_status() for pool_id, pool in self.pools.items()}
        }

# Global pool manager instance
_pool_manager_instance = None

async def get_pool_manager() -> AgentPoolManager:
    """Get or create the global pool manager instance"""
    global _pool_manager_instance
    if _pool_manager_instance is None:
        _pool_manager_instance = AgentPoolManager()
        await _pool_manager_instance.start()
    return _pool_manager_instance

if __name__ == "__main__":
    # Test the agent pool manager
    async def test_pool_manager():
        print("🧪 Testing Agent Pool Manager...")
        
        pm = AgentPoolManager()
        await pm.start()
        
        # Create test pools
        search_config = PoolConfig(
            name="linkedin-search",
            min_agents=2,
            max_agents=5,
            agent_type="search",
            platform="linkedin"
        )
        
        extract_config = PoolConfig(
            name="linkedin-extract", 
            min_agents=3,
            max_agents=8,
            agent_type="extraction",
            platform="linkedin"
        )
        
        pool1_id = await pm.create_pool(search_config)
        pool2_id = await pm.create_pool(extract_config)
        
        # Wait for pools to initialize
        await asyncio.sleep(2)
        
        # Show status
        status = pm.get_status()
        print(f"📊 Pool Manager Status: {json.dumps(status, indent=2)}")
        
        await pm.stop()
        print("✅ Test completed!")
    
    asyncio.run(test_pool_manager())