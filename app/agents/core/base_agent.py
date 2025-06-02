from typing import Dict, Any, Optional
import asyncio
import logging
from datetime import datetime

from .message_bus import MessageBus
from .context import AgentContext

class BaseAgent:
    def __init__(self, agent_id: str):
        self.agent_id = agent_id
        self._logger = logging.getLogger(f'agent.{agent_id}')
        self._message_bus: Optional[MessageBus] = None
        self._context: Optional[AgentContext] = None
        self._queue: Optional[asyncio.Queue] = None
        
    async def setup(self, message_bus: MessageBus, context: AgentContext):
        """Initialize agent with message bus and context"""
        self._message_bus = message_bus
        self._context = context
        self._queue = await message_bus.subscribe(self.agent_id)
        
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message"""
        raise NotImplementedError("Subclasses must implement process_message")
        
    async def send_message(self, target_agent: str, message: Dict[str, Any], priority: str = 'default'):
        """Send message to another agent"""
        if not self._message_bus:
            raise RuntimeError("MessageBus not initialized")
            
        message['source_agent'] = self.agent_id
        message['target_agent'] = target_agent
        message['timestamp'] = datetime.now().isoformat()
        
        return await self._message_bus.publish(message, priority)
        
    async def get_context(self, key: str, default: Any = None) -> Any:
        """Get value from context"""
        if not self._context:
            raise RuntimeError("Context not initialized")
        return await self._context.get(key, default)
        
    async def set_context(self, key: str, value: Any, ttl: Optional[int] = None):
        """Set value in context"""
        if not self._context:
            raise RuntimeError("Context not initialized")
        await self._context.set(key, value, ttl)
        
    async def start(self):
        """Start agent message processing loop"""
        if not self._queue:
            raise RuntimeError("Message queue not initialized")
            
        self._logger.info(f"Starting agent {self.agent_id}")
        while True:
            try:
                message = await self._queue.get()
                response = await self.process_message(message)
                
                if response and message.get('source_agent'):
                    await self.send_message(
                        message['source_agent'],
                        response
                    )
                    
            except Exception as e:
                self._logger.error(f"Error processing message: {str(e)}")
                
    async def cleanup(self):
        """Cleanup agent resources"""
        self._logger.info(f"Cleaning up agent {self.agent_id}")
        # Override in subclasses if needed 