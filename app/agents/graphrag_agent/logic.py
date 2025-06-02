"""
GraphRAG Agent - Xử lý truy vấn Neo4j database sử dụng Hybrid Search

Processing steps:
1. Nhận intent và structure từ Recommend Agent
2. Điều chỉnh intent nếu cần
3. Tạo Cypher query dựa trên loại query (store, order, product)
4. Thực thi query và xử lý kết quả
"""
from typing import Dict, Any, List, Optional
import json
import asyncio
import logging
from datetime import datetime

from ..core.base_agent import BaseAgent
from ..core.message_bus import MessageBus
from ..core.context import AgentContext
from ..core.utils import AsyncCache, async_retry, async_timeout
from ..core.config import config

from .core import GraphRAGCore

class GraphRAGAgent(BaseAgent):
    """GraphRAG Agent for handling Neo4j database queries"""
    
    def __init__(self, agent_id: str = 'graphrag'):
        """Initialize GraphRAG agent"""
        super().__init__(agent_id)
        self._logger = logging.getLogger('agent.graphrag')
        self._cache = AsyncCache(ttl=config.get('agents.graphrag.cache_ttl', 300))
        self._core = GraphRAGCore()
        self._timeout = config.get('agents.graphrag.timeout', 30)
        
    async def setup(self, message_bus: MessageBus, context: AgentContext):
        """Initialize agent"""
        await super().setup(message_bus, context)
        self._logger.info("GraphRAG agent initialized")
        
    @async_retry(max_retries=3)
    @async_timeout(seconds=30)
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message"""
        try:
            # Check cache first
            message_id = message.get('id')
            if message_id and (cached_result := await self._cache.get(message_id)):
                return cached_result
                
            # Extract query info
            intent_text = message.get('intent_text', '')
            original_query = message.get('original_query', '')
            
            # Extract intent data
            intent_data = self._core.extract_intent_data(intent_text, original_query)
            
            # Generate and execute query
            query = self._core.generate_query(intent_data)
            results = self._core.execute_query(query)
            processed_results = self._core.process_results(results, intent_data)
            
            # Prepare response
            response = {
                'status': 'success',
                'data': processed_results,
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache result
            if message_id:
                await self._cache.set(message_id, response)
                
            return response
            
        except Exception as e:
            self._logger.error(f"Error processing message: {str(e)}")
            return {
                'status': 'error',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
            
    async def cleanup(self):
        """Cleanup resources"""
        await self._cache.clear()
        await super().cleanup()


