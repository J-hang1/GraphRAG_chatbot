"""
Cache manager for GraphRAG agent
"""
from typing import Dict, Any, List, Optional, Union
import json
import time
import logging
from ...utils.logger import log_info, log_error
from ..core.constants import CACHE_SETTINGS

class CacheManager:
    """Cache manager for GraphRAG agent"""
    
    def __init__(self):
        self._logger = logging.getLogger('agent.graphrag.cache')
        self._cache = {}
        self._last_cleanup = time.time()
        
    def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        try:
            # Check if key exists
            if key not in self._cache:
                return None
                
            # Get cache entry
            entry = self._cache[key]
            
            # Check if entry is expired
            if time.time() - entry["timestamp"] > CACHE_SETTINGS["ttl"]:
                log_info(f"Cache entry expired: {key}")
                del self._cache[key]
                return None
                
            log_info(f"Cache hit: {key}")
            return entry["value"]
            
        except Exception as e:
            log_error(f"❌ Lỗi khi lấy giá trị từ cache: {str(e)}")
            return None
            
    def set(self, key: str, value: Any) -> bool:
        """Set value in cache"""
        try:
            # Check cache size
            if len(self._cache) >= CACHE_SETTINGS["max_size"]:
                self._cleanup()
                
            # Set cache entry
            self._cache[key] = {
                "value": value,
                "timestamp": time.time()
            }
            
            log_info(f"Cache set: {key}")
            return True
            
        except Exception as e:
            log_error(f"❌ Lỗi khi set giá trị vào cache: {str(e)}")
            return False
            
    def delete(self, key: str) -> bool:
        """Delete value from cache"""
        try:
            # Check if key exists
            if key not in self._cache:
                return False
                
            # Delete cache entry
            del self._cache[key]
            
            log_info(f"Cache delete: {key}")
            return True
            
        except Exception as e:
            log_error(f"❌ Lỗi khi xóa giá trị từ cache: {str(e)}")
            return False
            
    def clear(self) -> bool:
        """Clear all cache entries"""
        try:
            # Clear cache
            self._cache.clear()
            
            log_info("Cache cleared")
            return True
            
        except Exception as e:
            log_error(f"❌ Lỗi khi xóa cache: {str(e)}")
            return False
            
    def _cleanup(self) -> None:
        """Clean up expired cache entries"""
        try:
            # Get current time
            current_time = time.time()
            
            # Check if cleanup is needed
            if current_time - self._last_cleanup < CACHE_SETTINGS["ttl"]:
                return
                
            # Clean up expired entries
            expired_keys = []
            for key, entry in self._cache.items():
                if current_time - entry["timestamp"] > CACHE_SETTINGS["ttl"]:
                    expired_keys.append(key)
                    
            # Delete expired entries
            for key in expired_keys:
                del self._cache[key]
                
            # Update last cleanup time
            self._last_cleanup = current_time
            
            log_info(f"Cache cleanup: {len(expired_keys)} entries removed")
            
        except Exception as e:
            log_error(f"❌ Lỗi khi cleanup cache: {str(e)}")
            
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics"""
        try:
            # Calculate statistics
            stats = {
                "size": len(self._cache),
                "max_size": CACHE_SETTINGS["max_size"],
                "ttl": CACHE_SETTINGS["ttl"],
                "last_cleanup": self._last_cleanup
            }
            
            log_info(f"Cache stats: {json.dumps(stats, ensure_ascii=False)}")
            return stats
            
        except Exception as e:
            log_error(f"❌ Lỗi khi lấy thống kê cache: {str(e)}")
            return {} 