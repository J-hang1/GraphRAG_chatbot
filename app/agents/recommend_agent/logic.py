"""
Recommendation agent for product recommendations
Đã được cải tiến để xử lý nhiều loại truy vấn khác nhau và dịch tên sản phẩm
Tối ưu hóa để sử dụng AgentManager và standardized context
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, List, Optional
from ...utils.logger import log_info, log_error
from ...utils.performance import PerformanceContext, performance_timer
from ...models.context import AgentContext
from ..core.agent_manager import agent_manager
from ..core.message_bus import publish_message, MessageTypes
from .entity_extraction import extract_entities
from .result_processor import process_results
from ..core.base_agent import BaseAgent
from ..core.message_bus import MessageBus
from ..core.config import agent_config
from ..core.utils import AsyncCache, async_retry, async_timeout
from .result_processor import ResultProcessor
from .prompt_templates_updated import PromptTemplates
from .entity_extraction import EntityExtraction
from .enhanced_intent_inference import EnhancedIntentInference
from .database_validator import DatabaseValidator
from .product_name_translator import ProductNameTranslator

class RecommendAgent(BaseAgent):
    """Recommend Agent for handling user recommendations"""

    def __init__(self, agent_id: str = 'recommend'):
        """Initialize Recommend agent"""
        super().__init__(agent_id)
        self._logger = logging.getLogger('agent.recommend')
        self._cache = AsyncCache(ttl=agent_config.get('agents.recommend.cache_ttl', 1800))
        self._timeout = agent_config.get('agents.recommend.timeout', 15)
        
        # Initialize components
        self._result_processor = ResultProcessor()
        self._prompt_templates = PromptTemplates()
        self._entity_extraction = EntityExtraction()
        self._intent_inference = EnhancedIntentInference()
        self._db_validator = DatabaseValidator()
        self._product_translator = ProductNameTranslator()
        
        log_info("🔄 Initializing Recommend agent...")
        # Không khởi tạo GraphRAG agent ngay, sẽ lazy load khi cần
        self.graphrag_agent = None
        log_info("✅ Recommend agent initialized")

    async def setup(self, message_bus: MessageBus, context: AgentContext):
        """Initialize Recommend agent"""
        await super().setup(message_bus, context)
        
    @async_retry(max_retries=3)
    @async_timeout(seconds=15)
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming message"""
        try:
            # Check cache first
            message_id = message.get('id')
            if message_id:
                cached_result = await self._cache.get(message_id)
                if cached_result:
                    return cached_result
            
            # Extract message content
            content = message.get('content', '')
            user_id = message.get('user_id')
            
            # Get user preferences from context
            preferences = await self.get_context(f'preferences_{user_id}', {})
            
            # Extract entities
            entities = await self._entity_extraction.extract(content)
            
            # Infer intent
            intent = await self._intent_inference.infer(content, preferences, entities)
            
            # Validate against database
            await self._db_validator.validate(intent)
            
            # Translate product names if needed
            intent = await self._product_translator.translate(intent)
            
            # Send to GraphRAG for data retrieval
            graphrag_response = await self.send_message(
                'graphrag',
                {
                    'query_type': intent['type'],
                    'intent_data': intent['data']
                }
            )
            
            # Process results
            results = await self._result_processor.process(graphrag_response, preferences)
            
            # Update user preferences
            await self._update_preferences(user_id, content, results)
            
            response = {
                'status': 'success',
                'recommendations': results,
                'timestamp': datetime.now().isoformat()
            }
            
            # Cache results
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
            
    @async_timeout(seconds=5)
    async def _update_preferences(self, user_id: str, content: str, results: List[Dict[str, Any]]):
        """Update user preferences based on interaction"""
        if not user_id:
            return
            
        current_preferences = await self.get_context(f'preferences_{user_id}', {})
        
        # Update preferences based on results
        updated_preferences = await self._result_processor.update_preferences(
            current_preferences,
            content,
            results
        )
        
        # Save updated preferences
        await self.set_context(f'preferences_{user_id}', updated_preferences)
        
    def _extract_products_from_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Trích xuất thông tin sản phẩm từ kết quả truy vấn"""
        try:
            products = []
            for result in results:
                if 'product_id' in result:
                    product = {
                        'id': result.get('product_id'),
                        'name': result.get('name_product', result.get('name', 'Unknown')),
                        'category': result.get('category', 'Unknown')
                    }
                    if product not in products:
                        products.append(product)
            return products
        except Exception as e:
            log_error(f"Error extracting products from results: {str(e)}")
            return []

    def _extract_filters_from_intent(self, intent_result: str) -> Dict[str, Any]:
        """
        Trích xuất các bộ lọc từ ý định
        Phiên bản cải tiến để xử lý nhiều loại truy vấn và dịch tên sản phẩm
        """
        try:
            # Khởi tạo structured_query
            structured_query = {
                "intent": "Tìm đồ uống",
                "filters": {},
                "product_type": "",
                "sort_by": "",
                "sort_order": ""
            }

            # Trích xuất thực thể từ intent_result
            entities = extract_entities(intent_result)

            # Xác định loại intent dựa trên thực thể
            if entities.get("store_info", False):
                structured_query["intent"] = "Tìm cửa hàng"
            elif entities.get("order_info", False):
                structured_query["intent"] = "Xem đơn hàng"
            else:
                # Mặc định là tìm đồ uống
                structured_query["intent"] = "Tìm đồ uống"

            # Xác định loại sản phẩm từ thực thể
            product_names = entities.get("entities", [])

            if product_names:
                # Xác định loại sản phẩm dựa trên tên sản phẩm
                for product_name in product_names:
                    if "cà phê" in product_name.lower() or "coffee" in product_name.lower():
                        structured_query["product_type"] = "Cà phê"
                        break
                    elif "trà" in product_name.lower() or "tea" in product_name.lower():
                        structured_query["product_type"] = "Trà"
                        break
                    elif "sinh tố" in product_name.lower() or "smoothie" in product_name.lower():
                        structured_query["product_type"] = "Sinh tố"
                        break
                    elif "nước ép" in product_name.lower() or "juice" in product_name.lower():
                        structured_query["product_type"] = "Nước ép"
                        break
                    elif "đá xay" in product_name.lower() or "frappe" in product_name.lower() or "frappuccino" in product_name.lower():
                        structured_query["product_type"] = "Đá xay"
                        break
            else:
                # Nếu không có tên sản phẩm, xác định loại sản phẩm từ intent_result
                if "cà phê" in intent_result.lower() or "coffee" in intent_result.lower():
                    structured_query["product_type"] = "Cà phê"
                elif "trà" in intent_result.lower() or "tea" in intent_result.lower():
                    structured_query["product_type"] = "Trà"
                elif "sinh tố" in intent_result.lower() or "smoothie" in intent_result.lower():
                    structured_query["product_type"] = "Sinh tố"
                elif "nước ép" in intent_result.lower() or "juice" in intent_result.lower():
                    structured_query["product_type"] = "Nước ép"
                elif "đá xay" in intent_result.lower() or "frappe" in intent_result.lower() or "frappuccino" in intent_result.lower():
                    structured_query["product_type"] = "Đá xay"
                elif "bánh" in intent_result.lower():
                    structured_query["product_type"] = "Bánh"

            # Lấy các bộ lọc từ thực thể
            filters = {}

            # Thêm các thuộc tính sản phẩm vào filters
            if entities.get("product_attributes", {}):
                filters.update(entities["product_attributes"])

            # Thêm các giới hạn vào filters
            if entities.get("constraints", {}):
                filters.update(entities["constraints"])

            # Chuyển đổi định dạng bộ lọc
            converted_filters = {}

            # Lọc theo giá
            if "max_price" in filters:
                if filters["max_price"] <= 30000:
                    converted_filters["price"] = "low"
                elif filters["max_price"] >= 60000:
                    converted_filters["price"] = "high"
                else:
                    converted_filters["price"] = "medium"

            # Lọc theo đường
            if "low_sugar" in filters and filters["low_sugar"]:
                converted_filters["sugar"] = "low"

            # Lọc theo caffeine
            if "low_caffeine" in filters and filters["low_caffeine"]:
                converted_filters["caffeine"] = "low"
            elif "high_caffeine" in filters and filters["high_caffeine"]:
                converted_filters["caffeine"] = "high"

            # Thêm filters vào structured_query
            structured_query['filters'] = converted_filters

            return structured_query
        except Exception as e:
            log_error(f"Error extracting filters from intent: {str(e)}")
            return {
                "intent": "Tìm đồ uống",
                "filters": {},
                "product_type": "",
                "sort_by": "",
                "sort_order": ""
            }

    def get_recommendations(self, context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Lấy gợi ý sản phẩm dựa trên context"""
        try:
            # Tạo intent dựa trên context
            intent = "Gợi ý các sản phẩm phổ biến"

            if context:
                if context.get('category'):
                    intent += f" trong danh mục {context.get('category')}"
                if context.get('price_range'):
                    intent += f" với giá {context.get('price_range')}"

            # Cập nhật context nếu có
            if context:
                context.from_agent = 'recommend'

            # Lấy GraphRAG agent từ AgentManager
            if self.graphrag_agent is None:
                log_info("🔄 Getting GraphRAG agent from AgentManager...")
                # Await can only be used inside async functions, so we need to make this function async or handle differently
                # Since this is a synchronous function, we will get the agent synchronously by running the coroutine
                import asyncio
                loop = asyncio.get_event_loop()
                self.graphrag_agent = loop.run_until_complete(agent_manager.get_agent('graphrag'))

            # Gọi GraphRAG agent để lấy kết quả truy vấn
            query_results = self.graphrag_agent.execute_query(intent, context)

            return query_results
        except Exception as e:
            log_error(f"Lỗi khi lấy gợi ý sản phẩm: {str(e)}")
            return []

    async def cleanup(self):
        """Cleanup Recommend agent resources"""
        await super().cleanup()
        await self._cache.clear()
        if hasattr(self, 'graphrag_agent'):
            self.graphrag_agent = None
        log_info("🧹 Recommend agent cleaned up")
