from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime
import json

class AgentContext:
    def __init__(self):
        self._context: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
        self._logger = logging.getLogger('agent_context')
        self._ttl = 3600  # 1 hour TTL for context items
        
    async def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set context value with optional TTL"""
        async with self._lock:
            self._context[key] = {
                'value': value,
                'timestamp': datetime.now().timestamp(),
                'ttl': ttl or self._ttl
            }
            
    async def get(self, key: str, default: Any = None) -> Any:
        """Get context value if not expired"""
        async with self._lock:
            if key not in self._context:
                return default
                
            item = self._context[key]
            if self._is_expired(item):
                del self._context[key]
                return default
                
            return item['value']
            
    def _is_expired(self, item: Dict[str, Any]) -> bool:
        """Check if context item is expired"""
        now = datetime.now().timestamp()
        return (now - item['timestamp']) > item['ttl']
        
    async def delete(self, key: str):
        """Delete context value"""
        async with self._lock:
            if key in self._context:
                del self._context[key]
                
    async def clear(self):
        """Clear all context"""
        async with self._lock:
            self._context.clear()
            
    async def get_all(self) -> Dict[str, Any]:
        """Get all non-expired context values"""
        async with self._lock:
            result = {}
            for key, item in self._context.items():
                if not self._is_expired(item):
                    result[key] = item['value']
            return result
            
    async def cleanup(self):
        """Cleanup expired context items"""
        async with self._lock:
            expired_keys = [
                key for key, item in self._context.items()
                if self._is_expired(item)
            ]
            for key in expired_keys:
                del self._context[key]
                
    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary"""
        return {
            key: item['value']
            for key, item in self._context.items()
            if not self._is_expired(item)
        }
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentContext':
        """Create context from dictionary"""
        context = cls()
        for key, value in data.items():
            context._context[key] = {
                'value': value,
                'timestamp': datetime.now().timestamp(),
                'ttl': context._ttl
            }
        return context 