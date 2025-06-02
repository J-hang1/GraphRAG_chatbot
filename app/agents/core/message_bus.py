from typing import Dict, Any, List, Optional
import asyncio
import logging
from datetime import datetime
import json

from .config import agent_config
from .utils import AsyncCache, AsyncRateLimiter, async_retry, async_timeout

class MessageBus:
    def __init__(self):
        self._queues: Dict[str, asyncio.Queue] = {}
        self._subscribers: Dict[str, List[str]] = {}
        self._cache = AsyncCache(ttl=agent_config.get('message_bus.cache_ttl', 3600))
        self._logger = logging.getLogger('message_bus')
        self._lock = asyncio.Lock()
        self._rate_limiter = AsyncRateLimiter(
            max_calls=100,  # 100 calls per second
            time_window=1.0
        )
        
    async def setup(self):
        """Initialize message bus"""
        # Create queues for each priority
        for priority in agent_config.get('message_bus.priorities', ['default', 'high_priority']):
            self._queues[priority] = asyncio.Queue(
                maxsize=agent_config.get('message_bus.max_queue_size', 1000)
            )
            
    @async_retry(max_retries=3)
    @async_timeout(seconds=5.0)
    async def publish(self, message: Dict[str, Any], priority: str = 'default'):
        """Publish message to bus"""
        try:
            await self._rate_limiter.acquire()
            
            message_id = f"{datetime.now().timestamp()}_{id(message)}"
            message['id'] = message_id
            message['timestamp'] = datetime.now().isoformat()
            
            # Cache message
            await self._cache.set(message_id, message)
            
            # Get target queue
            queue = self._queues.get(priority, self._queues['default'])
            
            # Add to queue
            await queue.put(message)
            
            # Notify subscribers
            if message.get('target_agent'):
                await self._notify_subscribers(message)
                
            return message_id
            
        except Exception as e:
            self._logger.error(f"Error publishing message: {str(e)}")
            raise
        finally:
            await self._rate_limiter.release()
            
    async def subscribe(self, agent_id: str, priority: str = 'default') -> asyncio.Queue:
        """Subscribe agent to message bus"""
        async with self._lock:
            if agent_id not in self._subscribers:
                self._subscribers[agent_id] = []
            if priority not in self._subscribers[agent_id]:
                self._subscribers[agent_id].append(priority)
                
        return self._queues.get(priority, self._queues['default'])
        
    async def _notify_subscribers(self, message: Dict[str, Any]):
        """Notify relevant subscribers about new message"""
        target_agent = message.get('target_agent')
        if target_agent in self._subscribers:
            for priority in self._subscribers[target_agent]:
                queue = self._queues.get(priority)
                if queue:
                    await queue.put(message)
                    
    async def get_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Get message from cache"""
        return await self._cache.get(message_id)
        
    async def cleanup(self):
        """Cleanup message bus resources"""
        async with self._lock:
            self._queues.clear()
            self._subscribers.clear()
            await self._cache.clear()
            
    async def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        stats = {}
        for queue_name, queue in self._queues.items():
            stats[queue_name] = queue.qsize()
        return stats 

# Create message bus instance
message_bus = MessageBus()

# Message types enum
class MessageTypes:
    ROUTING = "routing"
    RECOMMENDATION = "recommendation" 
    CUSTOMER = "customer"
    ORDER = "order"
    SYSTEM = "system"

async def publish_message(message: Dict[str, Any], priority: str = 'default') -> str:
    """Helper function to publish message to bus"""
    return await message_bus.publish(message, priority) 