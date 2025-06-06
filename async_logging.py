#!/usr/bin/env python3
"""
Enhanced Async Logging System for Multi-Agent Job Search
Provides structured logging, metrics collection, and error tracking
"""

import asyncio
import logging
import json
import time
import traceback
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
import threading
from queue import Queue, Empty
import sys

class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"

class ComponentType(Enum):
    TASK_MANAGER = "task_manager"
    AGENT_POOL = "agent_pool"
    SEARCH_AGENT = "search_agent"
    EXTRACTION_AGENT = "extraction_agent"
    ANALYSIS_AGENT = "analysis_agent"
    DATABASE = "database"
    BROWSER = "browser"
    SYSTEM = "system"

@dataclass
class LogEntry:
    timestamp: datetime
    level: LogLevel
    component: ComponentType
    message: str
    component_id: Optional[str] = None
    task_id: Optional[str] = None
    agent_id: Optional[str] = None
    duration: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    stack_trace: Optional[str] = None

@dataclass
class ErrorMetrics:
    total_errors: int = 0
    errors_by_component: Dict[str, int] = field(default_factory=dict)
    errors_by_level: Dict[str, int] = field(default_factory=dict)
    recent_errors: List[LogEntry] = field(default_factory=list)
    error_rate: float = 0.0
    last_error: Optional[datetime] = None

@dataclass
class PerformanceMetrics:
    total_operations: int = 0
    avg_operation_time: float = 0.0
    operations_by_component: Dict[str, int] = field(default_factory=dict)
    performance_by_component: Dict[str, float] = field(default_factory=dict)
    slow_operations: List[LogEntry] = field(default_factory=list)

class AsyncLogger:
    """High-performance async logger with structured logging and metrics"""
    
    def __init__(self, 
                 name: str = "async_job_search",
                 log_level: LogLevel = LogLevel.INFO,
                 log_file: Optional[str] = None,
                 max_log_entries: int = 10000,
                 enable_console: bool = True,
                 enable_metrics: bool = True):
        
        self.name = name
        self.log_level = log_level
        self.log_file = log_file
        self.max_log_entries = max_log_entries
        self.enable_console = enable_console
        self.enable_metrics = enable_metrics
        
        # Log storage
        self.log_entries: List[LogEntry] = []
        self.log_queue: Queue = Queue()
        
        # Metrics
        self.error_metrics = ErrorMetrics()
        self.performance_metrics = PerformanceMetrics()
        
        # Threading
        self.running = False
        self.log_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        # Standard logger setup
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.value))
        
        # Setup handlers
        self._setup_handlers()
        
        # Error callback functions
        self.error_callbacks: List[Callable] = []

    def _setup_handlers(self):
        """Setup logging handlers"""
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Custom formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        
        # Console handler
        if self.enable_console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)
        
        # File handler
        if self.log_file:
            file_handler = logging.FileHandler(self.log_file)
            file_handler.setFormatter(formatter)
            self.logger.addHandler(file_handler)

    def start(self):
        """Start the async logging system"""
        if self.running:
            return
        
        self.running = True
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()
        
        self.info(ComponentType.SYSTEM, "Async logging system started", system_id="main")

    def stop(self):
        """Stop the async logging system"""
        if not self.running:
            return
        
        self.info(ComponentType.SYSTEM, "Stopping async logging system", system_id="main")
        
        self.running = False
        
        # Process remaining log entries
        self._process_queue()
        
        if self.log_thread:
            self.log_thread.join(timeout=5)

    def _log_worker(self):
        """Background thread for processing log entries"""
        while self.running or not self.log_queue.empty():
            try:
                self._process_queue()
                time.sleep(0.1)
            except Exception as e:
                # Fallback logging to prevent infinite loops
                print(f"ERROR in log worker: {e}")

    def _process_queue(self):
        """Process queued log entries"""
        processed = 0
        while processed < 100:  # Process in batches
            try:
                entry = self.log_queue.get_nowait()
                self._write_log_entry(entry)
                processed += 1
            except Empty:
                break

    def _write_log_entry(self, entry: LogEntry):
        """Write a log entry to storage and update metrics"""
        with self.lock:
            # Add to storage
            self.log_entries.append(entry)
            
            # Trim if too many entries
            if len(self.log_entries) > self.max_log_entries:
                self.log_entries.pop(0)
            
            # Update metrics
            if self.enable_metrics:
                self._update_metrics(entry)
            
            # Log to standard logger
            self._log_to_standard_logger(entry)

    def _update_metrics(self, entry: LogEntry):
        """Update logging metrics"""
        component_name = entry.component.value
        
        # Performance metrics
        if entry.duration is not None:
            self.performance_metrics.total_operations += 1
            
            # Update average
            current_avg = self.performance_metrics.avg_operation_time
            total_ops = self.performance_metrics.total_operations
            self.performance_metrics.avg_operation_time = (
                (current_avg * (total_ops - 1) + entry.duration) / total_ops
            )
            
            # Update by component
            if component_name not in self.performance_metrics.operations_by_component:
                self.performance_metrics.operations_by_component[component_name] = 0
                self.performance_metrics.performance_by_component[component_name] = 0.0
            
            comp_ops = self.performance_metrics.operations_by_component[component_name]
            comp_avg = self.performance_metrics.performance_by_component[component_name]
            
            self.performance_metrics.operations_by_component[component_name] += 1
            self.performance_metrics.performance_by_component[component_name] = (
                (comp_avg * comp_ops + entry.duration) / (comp_ops + 1)
            )
            
            # Track slow operations (> 5 seconds)
            if entry.duration > 5.0:
                self.performance_metrics.slow_operations.append(entry)
                if len(self.performance_metrics.slow_operations) > 50:
                    self.performance_metrics.slow_operations.pop(0)
        
        # Error metrics
        if entry.level in [LogLevel.ERROR, LogLevel.CRITICAL]:
            self.error_metrics.total_errors += 1
            self.error_metrics.last_error = entry.timestamp
            
            # By component
            if component_name not in self.error_metrics.errors_by_component:
                self.error_metrics.errors_by_component[component_name] = 0
            self.error_metrics.errors_by_component[component_name] += 1
            
            # By level
            level_name = entry.level.value
            if level_name not in self.error_metrics.errors_by_level:
                self.error_metrics.errors_by_level[level_name] = 0
            self.error_metrics.errors_by_level[level_name] += 1
            
            # Recent errors
            self.error_metrics.recent_errors.append(entry)
            if len(self.error_metrics.recent_errors) > 100:
                self.error_metrics.recent_errors.pop(0)
            
            # Calculate error rate (errors per hour)
            hour_ago = datetime.now() - timedelta(hours=1)
            recent_error_count = sum(
                1 for err in self.error_metrics.recent_errors 
                if err.timestamp >= hour_ago
            )
            self.error_metrics.error_rate = recent_error_count
            
            # Call error callbacks
            for callback in self.error_callbacks:
                try:
                    callback(entry)
                except Exception as e:
                    print(f"Error callback failed: {e}")

    def _log_to_standard_logger(self, entry: LogEntry):
        """Log to standard Python logger"""
        message = self._format_message(entry)
        level = getattr(logging, entry.level.value)
        self.logger.log(level, message)

    def _format_message(self, entry: LogEntry) -> str:
        """Format log message for output"""
        parts = [entry.message]
        
        if entry.component_id:
            parts.append(f"[{entry.component.value}:{entry.component_id}]")
        else:
            parts.append(f"[{entry.component.value}]")
        
        if entry.task_id:
            parts.append(f"[task:{entry.task_id}]")
        
        if entry.agent_id:
            parts.append(f"[agent:{entry.agent_id}]")
        
        if entry.duration is not None:
            parts.append(f"[{entry.duration:.3f}s]")
        
        if entry.metadata:
            parts.append(f"[metadata:{json.dumps(entry.metadata)}]")
        
        return " ".join(parts)

    def _should_log(self, level: LogLevel) -> bool:
        """Check if message should be logged based on level"""
        level_values = {
            LogLevel.DEBUG: 10,
            LogLevel.INFO: 20,
            LogLevel.WARNING: 30,
            LogLevel.ERROR: 40,
            LogLevel.CRITICAL: 50
        }
        return level_values[level] >= level_values[self.log_level]

    def _log(self, 
             level: LogLevel,
             component: ComponentType,
             message: str,
             component_id: Optional[str] = None,
             task_id: Optional[str] = None,
             agent_id: Optional[str] = None,
             duration: Optional[float] = None,
             metadata: Optional[Dict[str, Any]] = None,
             exception: Optional[Exception] = None):
        """Internal logging method"""
        
        if not self._should_log(level):
            return
        
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level,
            component=component,
            message=message,
            component_id=component_id,
            task_id=task_id,
            agent_id=agent_id,
            duration=duration,
            metadata=metadata or {},
            exception=str(exception) if exception else None,
            stack_trace=traceback.format_exc() if exception else None
        )
        
        if self.running:
            self.log_queue.put(entry)
        else:
            # If not running, write directly
            self._write_log_entry(entry)

    # Public logging methods
    def debug(self, component: ComponentType, message: str, **kwargs):
        """Log debug message"""
        self._log(LogLevel.DEBUG, component, message, **kwargs)

    def info(self, component: ComponentType, message: str, **kwargs):
        """Log info message"""
        self._log(LogLevel.INFO, component, message, **kwargs)

    def warning(self, component: ComponentType, message: str, **kwargs):
        """Log warning message"""
        self._log(LogLevel.WARNING, component, message, **kwargs)

    def error(self, component: ComponentType, message: str, **kwargs):
        """Log error message"""
        self._log(LogLevel.ERROR, component, message, **kwargs)

    def critical(self, component: ComponentType, message: str, **kwargs):
        """Log critical message"""
        self._log(LogLevel.CRITICAL, component, message, **kwargs)

    def log_operation(self, 
                     component: ComponentType,
                     operation: str,
                     start_time: float,
                     success: bool = True,
                     **kwargs):
        """Log an operation with duration"""
        duration = time.time() - start_time
        
        if success:
            self.info(
                component,
                f"Operation '{operation}' completed successfully",
                duration=duration,
                **kwargs
            )
        else:
            self.error(
                component,
                f"Operation '{operation}' failed",
                duration=duration,
                **kwargs
            )

    def register_error_callback(self, callback: Callable[[LogEntry], None]):
        """Register callback for error events"""
        self.error_callbacks.append(callback)

    def get_metrics(self) -> Dict[str, Any]:
        """Get current logging metrics"""
        with self.lock:
            return {
                'error_metrics': {
                    'total_errors': self.error_metrics.total_errors,
                    'errors_by_component': dict(self.error_metrics.errors_by_component),
                    'errors_by_level': dict(self.error_metrics.errors_by_level),
                    'error_rate_per_hour': self.error_metrics.error_rate,
                    'last_error': self.error_metrics.last_error.isoformat() if self.error_metrics.last_error else None
                },
                'performance_metrics': {
                    'total_operations': self.performance_metrics.total_operations,
                    'avg_operation_time': self.performance_metrics.avg_operation_time,
                    'operations_by_component': dict(self.performance_metrics.operations_by_component),
                    'performance_by_component': dict(self.performance_metrics.performance_by_component),
                    'slow_operations_count': len(self.performance_metrics.slow_operations)
                },
                'log_stats': {
                    'total_entries': len(self.log_entries),
                    'queue_size': self.log_queue.qsize(),
                    'running': self.running
                }
            }

    def get_recent_logs(self, 
                       component: Optional[ComponentType] = None,
                       level: Optional[LogLevel] = None,
                       limit: int = 100) -> List[Dict[str, Any]]:
        """Get recent log entries"""
        with self.lock:
            entries = self.log_entries[-limit:]
            
            # Filter by component
            if component:
                entries = [e for e in entries if e.component == component]
            
            # Filter by level
            if level:
                entries = [e for e in entries if e.level == level]
            
            # Convert to dict format
            return [
                {
                    'timestamp': entry.timestamp.isoformat(),
                    'level': entry.level.value,
                    'component': entry.component.value,
                    'message': entry.message,
                    'component_id': entry.component_id,
                    'task_id': entry.task_id,
                    'agent_id': entry.agent_id,
                    'duration': entry.duration,
                    'metadata': entry.metadata,
                    'exception': entry.exception
                }
                for entry in entries
            ]

    def get_recent_errors(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent error entries"""
        with self.lock:
            recent_errors = self.error_metrics.recent_errors[-limit:]
            return [
                {
                    'timestamp': entry.timestamp.isoformat(),
                    'level': entry.level.value,
                    'component': entry.component.value,
                    'message': entry.message,
                    'component_id': entry.component_id,
                    'task_id': entry.task_id,
                    'agent_id': entry.agent_id,
                    'exception': entry.exception,
                    'stack_trace': entry.stack_trace
                }
                for entry in recent_errors
            ]

# Global logger instance
_async_logger_instance = None

def get_async_logger() -> AsyncLogger:
    """Get or create the global async logger instance"""
    global _async_logger_instance
    if _async_logger_instance is None:
        _async_logger_instance = AsyncLogger(
            log_file="async_job_search.log",
            enable_metrics=True
        )
        _async_logger_instance.start()
    return _async_logger_instance

# Context manager for operation logging
class LoggedOperation:
    """Context manager for logging operations with duration"""
    
    def __init__(self, 
                 component: ComponentType,
                 operation: str,
                 logger: Optional[AsyncLogger] = None,
                 **kwargs):
        self.component = component
        self.operation = operation
        self.logger = logger or get_async_logger()
        self.kwargs = kwargs
        self.start_time = None

    def __enter__(self):
        self.start_time = time.time()
        self.logger.debug(
            self.component,
            f"Starting operation '{self.operation}'",
            **self.kwargs
        )
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        success = exc_type is None
        
        if success:
            self.logger.log_operation(
                self.component,
                self.operation,
                self.start_time,
                success=True,
                **self.kwargs
            )
        else:
            self.logger.log_operation(
                self.component,
                self.operation,
                self.start_time,
                success=False,
                exception=exc_val,
                **self.kwargs
            )

if __name__ == "__main__":
    # Test the async logging system
    def test_async_logging():
        print("🧪 Testing Async Logging System...")
        
        logger = AsyncLogger(enable_console=True, enable_metrics=True)
        logger.start()
        
        # Test different log levels
        logger.debug(ComponentType.SYSTEM, "Debug message", system_id="test")
        logger.info(ComponentType.TASK_MANAGER, "Task manager started", component_id="tm-001")
        logger.warning(ComponentType.AGENT_POOL, "Pool at capacity", component_id="pool-search")
        logger.error(ComponentType.EXTRACTION_AGENT, "Failed to extract job", agent_id="extract-001", 
                    metadata={"url": "https://example.com/job"})
        
        # Test operation logging
        with LoggedOperation(ComponentType.DATABASE, "test_query", component_id="db-001"):
            time.sleep(0.1)  # Simulate work
        
        # Test error logging
        try:
            raise ValueError("Test error")
        except Exception as e:
            logger.error(ComponentType.BROWSER, "Browser automation failed", 
                        exception=e, component_id="browser-001")
        
        time.sleep(1)  # Let processing finish
        
        # Show metrics
        metrics = logger.get_metrics()
        print(f"📊 Metrics: {json.dumps(metrics, indent=2)}")
        
        # Show recent logs
        recent = logger.get_recent_logs(limit=5)
        print(f"📋 Recent logs: {json.dumps(recent, indent=2)}")
        
        logger.stop()
        print("✅ Test completed!")
    
    test_async_logging()