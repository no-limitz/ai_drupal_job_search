#!/usr/bin/env python3
"""
Database Connection Pool for Multi-Agent Job Search System
Provides thread-safe, concurrent database access with connection pooling
"""

import asyncio
import sqlite3
import logging
import time
import threading
from typing import Dict, List, Optional, Any, ContextManager
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from contextlib import asynccontextmanager, contextmanager
from queue import Queue, Empty
import json
import hashlib

logger = logging.getLogger(__name__)

@dataclass
class ConnectionStats:
    total_connections: int = 0
    active_connections: int = 0
    available_connections: int = 0
    total_queries: int = 0
    failed_queries: int = 0
    avg_query_time: float = 0.0
    peak_connections: int = 0
    last_activity: Optional[datetime] = None

class DatabaseConnection:
    """Wrapper for database connection with metadata"""
    
    def __init__(self, connection: sqlite3.Connection, pool_id: str):
        self.connection = connection
        self.pool_id = pool_id
        self.created_at = datetime.now()
        self.last_used = datetime.now()
        self.query_count = 0
        self.in_use = False
        self.connection_id = id(connection)
        
        # Configure connection for concurrent access
        self.connection.execute("PRAGMA journal_mode=WAL")
        self.connection.execute("PRAGMA synchronous=NORMAL")
        self.connection.execute("PRAGMA cache_size=10000")
        self.connection.execute("PRAGMA temp_store=memory")
        self.connection.commit()

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query and update stats"""
        self.last_used = datetime.now()
        self.query_count += 1
        return self.connection.execute(query, params)

    def executemany(self, query: str, params_list: List[tuple]) -> sqlite3.Cursor:
        """Execute many queries and update stats"""
        self.last_used = datetime.now()
        self.query_count += len(params_list)
        return self.connection.executemany(query, params_list)

    def commit(self):
        """Commit transaction"""
        self.connection.commit()

    def rollback(self):
        """Rollback transaction"""
        self.connection.rollback()

    def close(self):
        """Close the connection"""
        if self.connection:
            self.connection.close()

    def is_expired(self, max_age_seconds: int = 3600) -> bool:
        """Check if connection is expired"""
        age = (datetime.now() - self.created_at).total_seconds()
        return age > max_age_seconds

    def is_idle(self, max_idle_seconds: int = 300) -> bool:
        """Check if connection has been idle too long"""
        idle_time = (datetime.now() - self.last_used).total_seconds()
        return idle_time > max_idle_seconds

class DatabaseConnectionPool:
    """Thread-safe connection pool for SQLite database"""
    
    def __init__(self, 
                 db_path: str = 'drupal_jobs.db',
                 min_connections: int = 2,
                 max_connections: int = 20,
                 connection_timeout: int = 30,
                 max_connection_age: int = 3600):
        
        self.db_path = db_path
        self.min_connections = min_connections
        self.max_connections = max_connections
        self.connection_timeout = connection_timeout
        self.max_connection_age = max_connection_age
        
        self.pool: Queue = Queue(maxsize=max_connections)
        self.all_connections: Dict[int, DatabaseConnection] = {}
        self.stats = ConnectionStats()
        self.lock = threading.Lock()
        self.running = False
        self.cleanup_task: Optional[asyncio.Task] = None
        
        logger.info(f"🏊 Initialized database connection pool: {db_path}")

    async def start(self):
        """Start the connection pool"""
        logger.info("🚀 Starting database connection pool...")
        self.running = True
        
        # Initialize database schema
        await self._initialize_database()
        
        # Create initial connections
        await self._create_initial_connections()
        
        # Start cleanup task
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info(f"✅ Database connection pool started with {self.stats.total_connections} connections")

    async def stop(self):
        """Stop the connection pool and close all connections"""
        logger.info("🛑 Stopping database connection pool...")
        self.running = False
        
        # Cancel cleanup task
        if self.cleanup_task:
            self.cleanup_task.cancel()
        
        # Close all connections
        with self.lock:
            for conn in self.all_connections.values():
                conn.close()
            self.all_connections.clear()
            
            # Clear the pool
            while not self.pool.empty():
                try:
                    self.pool.get_nowait()
                except Empty:
                    break
        
        logger.info("✅ Database connection pool stopped")

    @asynccontextmanager
    async def get_connection(self):
        """Get a connection from the pool (async context manager)"""
        connection = await self._acquire_connection()
        try:
            yield connection
        finally:
            await self._release_connection(connection)

    @contextmanager
    def get_connection_sync(self):
        """Get a connection from the pool (sync context manager)"""
        connection = self._acquire_connection_sync()
        try:
            yield connection
        finally:
            self._release_connection_sync(connection)

    async def _acquire_connection(self) -> DatabaseConnection:
        """Acquire a connection from the pool"""
        start_time = time.time()
        
        while time.time() - start_time < self.connection_timeout:
            try:
                # Try to get existing connection
                connection = self.pool.get_nowait()
                
                with self.lock:
                    if connection.connection_id in self.all_connections:
                        connection.in_use = True
                        self.stats.active_connections += 1
                        self.stats.available_connections -= 1
                        self.stats.last_activity = datetime.now()
                        return connection
                    
            except Empty:
                # No available connections, try to create new one
                if self.stats.total_connections < self.max_connections:
                    connection = await self._create_connection()
                    if connection:
                        return connection
                
                # Wait a bit and try again
                await asyncio.sleep(0.1)
        
        raise TimeoutError(f"Could not acquire database connection within {self.connection_timeout} seconds")

    def _acquire_connection_sync(self) -> DatabaseConnection:
        """Synchronous version of acquire_connection"""
        start_time = time.time()
        
        while time.time() - start_time < self.connection_timeout:
            try:
                connection = self.pool.get_nowait()
                
                with self.lock:
                    if connection.connection_id in self.all_connections:
                        connection.in_use = True
                        self.stats.active_connections += 1
                        self.stats.available_connections -= 1
                        self.stats.last_activity = datetime.now()
                        return connection
                    
            except Empty:
                if self.stats.total_connections < self.max_connections:
                    connection = self._create_connection_sync()
                    if connection:
                        return connection
                
                time.sleep(0.1)
        
        raise TimeoutError(f"Could not acquire database connection within {self.connection_timeout} seconds")

    async def _release_connection(self, connection: DatabaseConnection):
        """Release a connection back to the pool"""
        with self.lock:
            if connection.connection_id in self.all_connections:
                connection.in_use = False
                self.stats.active_connections -= 1
                self.stats.available_connections += 1
                
                # Return to pool if not expired
                if not connection.is_expired(self.max_connection_age):
                    try:
                        self.pool.put_nowait(connection)
                    except:
                        # Pool is full, close the connection
                        await self._remove_connection(connection)
                else:
                    # Connection expired, remove it
                    await self._remove_connection(connection)

    def _release_connection_sync(self, connection: DatabaseConnection):
        """Synchronous version of release_connection"""
        with self.lock:
            if connection.connection_id in self.all_connections:
                connection.in_use = False
                self.stats.active_connections -= 1
                self.stats.available_connections += 1
                
                if not connection.is_expired(self.max_connection_age):
                    try:
                        self.pool.put_nowait(connection)
                    except:
                        self._remove_connection_sync(connection)
                else:
                    self._remove_connection_sync(connection)

    async def _create_connection(self) -> Optional[DatabaseConnection]:
        """Create a new database connection"""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            db_conn = DatabaseConnection(conn, f"pool-{id(self)}")
            
            with self.lock:
                self.all_connections[db_conn.connection_id] = db_conn
                self.stats.total_connections += 1
                self.stats.active_connections += 1
                self.stats.peak_connections = max(self.stats.peak_connections, self.stats.total_connections)
                db_conn.in_use = True
            
            logger.debug(f"➕ Created new database connection {db_conn.connection_id}")
            return db_conn
            
        except Exception as e:
            logger.error(f"❌ Failed to create database connection: {e}")
            return None

    def _create_connection_sync(self) -> Optional[DatabaseConnection]:
        """Synchronous version of create_connection"""
        try:
            conn = sqlite3.connect(self.db_path, check_same_thread=False)
            db_conn = DatabaseConnection(conn, f"pool-{id(self)}")
            
            with self.lock:
                self.all_connections[db_conn.connection_id] = db_conn
                self.stats.total_connections += 1
                self.stats.active_connections += 1
                self.stats.peak_connections = max(self.stats.peak_connections, self.stats.total_connections)
                db_conn.in_use = True
            
            logger.debug(f"➕ Created new database connection {db_conn.connection_id}")
            return db_conn
            
        except Exception as e:
            logger.error(f"❌ Failed to create database connection: {e}")
            return None

    async def _remove_connection(self, connection: DatabaseConnection):
        """Remove a connection from the pool"""
        with self.lock:
            if connection.connection_id in self.all_connections:
                del self.all_connections[connection.connection_id]
                self.stats.total_connections -= 1
                if connection.in_use:
                    self.stats.active_connections -= 1
                else:
                    self.stats.available_connections -= 1
        
        connection.close()
        logger.debug(f"➖ Removed database connection {connection.connection_id}")

    def _remove_connection_sync(self, connection: DatabaseConnection):
        """Synchronous version of remove_connection"""
        with self.lock:
            if connection.connection_id in self.all_connections:
                del self.all_connections[connection.connection_id]
                self.stats.total_connections -= 1
                if connection.in_use:
                    self.stats.active_connections -= 1
                else:
                    self.stats.available_connections -= 1
        
        connection.close()
        logger.debug(f"➖ Removed database connection {connection.connection_id}")

    async def _create_initial_connections(self):
        """Create initial pool of connections"""
        for i in range(self.min_connections):
            connection = await self._create_connection()
            if connection:
                await self._release_connection(connection)

    async def _cleanup_loop(self):
        """Background cleanup of expired and idle connections"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Cleanup every minute
                await self._cleanup_connections()
                
            except Exception as e:
                logger.error(f"❌ Connection cleanup error: {e}")

    async def _cleanup_connections(self):
        """Clean up expired and idle connections"""
        connections_to_remove = []
        
        with self.lock:
            for conn in self.all_connections.values():
                if not conn.in_use and (conn.is_expired(self.max_connection_age) or conn.is_idle()):
                    connections_to_remove.append(conn)
        
        # Remove expired/idle connections
        for conn in connections_to_remove:
            await self._remove_connection(conn)
        
        # Ensure minimum connections
        current_available = self.stats.total_connections - self.stats.active_connections
        if current_available < self.min_connections:
            needed = self.min_connections - current_available
            for i in range(needed):
                connection = await self._create_connection()
                if connection:
                    await self._release_connection(connection)

    async def _initialize_database(self):
        """Initialize database schema"""
        async with self.get_connection() as conn:
            # Jobs table (enhanced version of existing schema)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS jobs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_hash TEXT UNIQUE NOT NULL,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    url TEXT,
                    description TEXT,
                    salary_range TEXT,
                    posted_date TEXT,
                    source TEXT,
                    relevance_score REAL,
                    first_seen DATE DEFAULT CURRENT_DATE,
                    last_seen DATE DEFAULT CURRENT_DATE,
                    is_active BOOLEAN DEFAULT 1,
                    applied BOOLEAN DEFAULT 0,
                    application_date DATE,
                    notes TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    
                    -- New fields for async system
                    processing_status TEXT DEFAULT 'pending',
                    agent_id TEXT,
                    extraction_metadata TEXT,
                    analysis_metadata TEXT
                )
            ''')
            
            # Task tracking table for distributed processing
            conn.execute('''
                CREATE TABLE IF NOT EXISTS task_tracking (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    task_type TEXT NOT NULL,
                    status TEXT NOT NULL,
                    agent_id TEXT,
                    data TEXT,
                    result TEXT,
                    error TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    started_at TIMESTAMP,
                    completed_at TIMESTAMP,
                    retry_count INTEGER DEFAULT 0
                )
            ''')
            
            # Agent performance tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS agent_performance (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    agent_id TEXT NOT NULL,
                    task_count INTEGER DEFAULT 0,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    avg_duration REAL DEFAULT 0.0,
                    last_activity TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create indexes for better performance
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_hash ON jobs(job_hash)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_relevance ON jobs(relevance_score)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_task_tracking_status ON task_tracking(status)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_task_tracking_type ON task_tracking(task_type)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_agent_performance_id ON agent_performance(agent_id)')
            
            conn.commit()

    async def execute_query(self, query: str, params: tuple = (), fetch: str = None) -> Any:
        """Execute a query with automatic connection handling"""
        start_time = time.time()
        
        try:
            async with self.get_connection() as conn:
                cursor = conn.execute(query, params)
                
                if fetch == 'one':
                    result = cursor.fetchone()
                elif fetch == 'all':
                    result = cursor.fetchall()
                elif query.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')):
                    conn.commit()
                    result = cursor.rowcount
                else:
                    result = cursor
                
                # Update stats
                duration = time.time() - start_time
                self.stats.total_queries += 1
                self.stats.avg_query_time = (
                    (self.stats.avg_query_time * (self.stats.total_queries - 1) + duration) / 
                    self.stats.total_queries
                )
                
                return result
                
        except Exception as e:
            self.stats.failed_queries += 1
            logger.error(f"❌ Database query failed: {e}")
            raise

    def get_status(self) -> Dict[str, Any]:
        """Get connection pool status"""
        with self.lock:
            return {
                'db_path': self.db_path,
                'running': self.running,
                'connections': {
                    'total': self.stats.total_connections,
                    'active': self.stats.active_connections,
                    'available': self.stats.available_connections,
                    'peak': self.stats.peak_connections,
                    'min_configured': self.min_connections,
                    'max_configured': self.max_connections
                },
                'queries': {
                    'total': self.stats.total_queries,
                    'failed': self.stats.failed_queries,
                    'success_rate': (self.stats.total_queries - self.stats.failed_queries) / self.stats.total_queries if self.stats.total_queries > 0 else 0.0,
                    'avg_time': self.stats.avg_query_time
                },
                'last_activity': self.stats.last_activity.isoformat() if self.stats.last_activity else None
            }

# Global connection pool instance
_connection_pool_instance = None

async def get_connection_pool() -> DatabaseConnectionPool:
    """Get or create the global connection pool instance"""
    global _connection_pool_instance
    if _connection_pool_instance is None:
        _connection_pool_instance = DatabaseConnectionPool()
        await _connection_pool_instance.start()
    return _connection_pool_instance

# Convenience functions for database operations
async def add_job_async(job_data: Dict[str, Any]) -> bool:
    """Add a job to the database (async)"""
    pool = await get_connection_pool()
    
    # Create job hash for duplicate detection
    job_key = f"{job_data.get('title', '')}-{job_data.get('company', '')}-{job_data.get('url', '')}"
    job_hash = hashlib.sha256(job_key.encode()).hexdigest()
    
    try:
        await pool.execute_query('''
            INSERT INTO jobs (
                job_hash, title, company, location, url, description, 
                salary_range, posted_date, source, relevance_score
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            job_hash,
            job_data.get('title', ''),
            job_data.get('company', ''),
            job_data.get('location', ''),
            job_data.get('url', ''),
            job_data.get('description', ''),
            job_data.get('salary_range', ''),
            job_data.get('posted_date', ''),
            job_data.get('source', ''),
            job_data.get('relevance_score', 0.0)
        ))
        
        logger.debug(f"✅ Added job: {job_data.get('title')} at {job_data.get('company')}")
        return True
        
    except sqlite3.IntegrityError:
        # Job already exists
        logger.debug(f"📄 Duplicate job: {job_data.get('title')} at {job_data.get('company')}")
        return False

async def get_jobs_async(days: int = 7, min_relevance: float = 0.0) -> List[Dict]:
    """Get jobs from database (async)"""
    pool = await get_connection_pool()
    
    rows = await pool.execute_query('''
        SELECT * FROM jobs 
        WHERE first_seen >= date('now', '-{} days') 
        AND relevance_score >= ?
        ORDER BY relevance_score DESC, posted_date DESC
    '''.format(days), (min_relevance,), fetch='all')
    
    columns = ['id', 'job_hash', 'title', 'company', 'location', 'url', 'description',
               'salary_range', 'posted_date', 'source', 'relevance_score', 'first_seen',
               'last_seen', 'is_active', 'applied', 'application_date', 'notes',
               'created_at', 'updated_at']
    
    return [dict(zip(columns, row)) for row in rows]

if __name__ == "__main__":
    # Test the connection pool
    async def test_connection_pool():
        print("🧪 Testing Database Connection Pool...")
        
        pool = DatabaseConnectionPool(max_connections=5)
        await pool.start()
        
        # Test multiple concurrent connections
        async def worker(worker_id: int):
            for i in range(5):
                async with pool.get_connection() as conn:
                    cursor = conn.execute("SELECT datetime('now')")
                    result = cursor.fetchone()
                    print(f"Worker {worker_id}, Query {i}: {result[0]}")
                    await asyncio.sleep(0.1)
        
        # Run multiple workers concurrently
        tasks = [worker(i) for i in range(3)]
        await asyncio.gather(*tasks)
        
        # Show status
        status = pool.get_status()
        print(f"📊 Pool Status: {json.dumps(status, indent=2)}")
        
        await pool.stop()
        print("✅ Test completed!")
    
    asyncio.run(test_connection_pool())