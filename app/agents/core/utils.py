from typing import Dict, Any, List, Optional, Callable
import asyncio
import logging
import time
import gc
import psutil
from functools import wraps
from datetime import datetime

from .config import agent_config

def async_retry(max_retries: int = 3, delay: float = 1.0):
    """Decorator for retrying async functions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            last_error = None
            for i in range(max_retries):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    if i < max_retries - 1:
                        await asyncio.sleep(delay * (i + 1))
            raise last_error
        return wrapper
    return decorator

def async_timeout(seconds: float):
    """Decorator for adding timeout to async functions"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=seconds)
            except asyncio.TimeoutError:
                raise TimeoutError(f"Function {func.__name__} timed out after {seconds} seconds")
        return wrapper
    return decorator

class AsyncCache:
    """Async cache with TTL"""
    def __init__(self, ttl: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl
        self._lock = asyncio.Lock()
        
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache if not expired"""
        async with self._lock:
            if key not in self._cache:
                return None
                
            item = self._cache[key]
            if time.time() - item['timestamp'] > self._ttl:
                del self._cache[key]
                return None
                
            return item['value']
            
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in cache with optional TTL"""
        async with self._lock:
            self._cache[key] = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl or self._ttl
            }
            
    async def delete(self, key: str):
        """Delete value from cache"""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                
    async def clear(self):
        """Clear all cache"""
        async with self._lock:
            self._cache.clear()
            
    async def cleanup(self):
        """Remove expired items"""
        async with self._lock:
            now = time.time()
            expired_keys = [
                key for key, item in self._cache.items()
                if now - item['timestamp'] > item['ttl']
            ]
            for key in expired_keys:
                del self._cache[key]

class AsyncRateLimiter:
    """Rate limiter for async functions"""
    def __init__(self, max_calls: int, time_window: float):
        self._max_calls = max_calls
        self._time_window = time_window
        self._calls: List[float] = []
        self._lock = asyncio.Lock()
        
    async def acquire(self):
        """Acquire rate limit token"""
        async with self._lock:
            now = time.time()
            
            # Remove old calls
            self._calls = [t for t in self._calls if now - t < self._time_window]
            
            if len(self._calls) >= self._max_calls:
                # Wait until oldest call expires
                wait_time = self._calls[0] + self._time_window - now
                if wait_time > 0:
                    await asyncio.sleep(wait_time)
                    
            self._calls.append(now)
            
    async def release(self):
        """Release rate limit token"""
        async with self._lock:
            if self._calls:
                self._calls.pop(0)

class MemoryManager:
    """Memory management utility"""
    def __init__(self, memory_limit_mb: int = 1024):
        self._memory_limit = memory_limit_mb * 1024 * 1024  # Convert to bytes
        self._process = psutil.Process()
        
    def check_memory_usage(self) -> bool:
        """Check if memory usage is within limit"""
        memory_info = self._process.memory_info()
        return memory_info.rss <= self._memory_limit
        
    def get_memory_usage(self) -> float:
        """Get current memory usage in MB"""
        memory_info = self._process.memory_info()
        return memory_info.rss / (1024 * 1024)
        
    def cleanup_memory(self):
        """Cleanup memory"""
        gc.collect()

def setup_logging():
    """Setup logging configuration"""
    log_config = agent_config.get('logging', {})
    
    # Create formatter
    formatter = logging.Formatter(log_config.get('format'))
    
    # Create handlers
    handlers = []
    if 'console' in log_config.get('handlers', []):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        handlers.append(console_handler)
        
    if 'file' in log_config.get('handlers', []):
        file_handler = logging.handlers.RotatingFileHandler(
            log_config.get('log_file', 'agent.log'),
            maxBytes=log_config.get('max_file_size', 10485760),
            backupCount=log_config.get('backup_count', 5)
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)
    
    # Setup root logger
    logging.basicConfig(
        level=log_config.get('level', 'INFO'),
        handlers=handlers
    ) 