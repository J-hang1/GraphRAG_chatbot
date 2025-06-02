from typing import Dict, Any, Optional
import asyncio
from functools import lru_cache
import logging
from datetime import datetime

class AgentManager:
    _instance = None
    _lock = asyncio.Lock()
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if self._initialized:
            return
            
        self._agents: Dict[str, Any] = {}
        self._message_bus = None  # Will be initialized in setup()
        self._context = None      # Will be initialized in setup()
        self._logger = logging.getLogger('agent_manager')
        self._initialized = True
        
    async def setup(self):
        """Initialize core components"""
        from .message_bus import MessageBus
        from .context import AgentContext
        
        self._message_bus = MessageBus()
        self._context = AgentContext()
        await self._message_bus.setup()
        
    async def get_agent(self, agent_id: str) -> Any:
        """Get agent instance with caching"""
        if agent_id not in self._agents:
            async with self._lock:
                if agent_id not in self._agents:
                    self._agents[agent_id] = await self._create_agent(agent_id)
        return self._agents[agent_id]
    
    async def _create_agent(self, agent_id: str) -> Any:
        """Create new agent instance"""
        try:
            if agent_id == 'graphrag':
                from ..graphrag_agent.logic import GraphRAGAgent
                return GraphRAGAgent()
            elif agent_id == 'recommend':
                from ..recommend_agent.logic import RecommendAgent
                return RecommendAgent()
            elif agent_id == 'router':
                from ..routing_agent.logic import RouterAgent
                return RouterAgent(agent_id)
            elif agent_id == 'customer':
                from ..customer_agent.logic import CustomerAgent
                return CustomerAgent()
            # Add other agents here
            else:
                raise ValueError(f"Unknown agent type: {agent_id}")
        except Exception as e:
            self._logger.error(f"Error creating agent {agent_id}: {str(e)}")
            raise
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all agents"""
        if not self._message_bus:
            raise RuntimeError("MessageBus not initialized")
        await self._message_bus.publish(message)
    
    async def cleanup(self):
        """Cleanup resources"""
        for agent in self._agents.values():
            if hasattr(agent, 'cleanup'):
                await agent.cleanup()
        self._agents.clear()
        if self._message_bus:
            await self._message_bus.cleanup()

# Global instance
agent_manager = AgentManager() 