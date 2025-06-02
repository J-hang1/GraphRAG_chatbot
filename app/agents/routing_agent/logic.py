"""
Router Agent - Phân loại và điều hướng câu hỏi đến agent phù hợp
Đã được tối ưu hóa để sử dụng AgentManager và MessageBus
"""
import re
import asyncio
from functools import lru_cache
import logging
from flask import session, current_app
from ...utils.logger import log_info, log_error
from ...utils.performance import PerformanceContext, performance_timer
from ...llm_clients.gemini_client import gemini_client
from ...models.customer import Customer
from ...models.chat_history import ChatHistory
from ...models.context import AgentContext, create_context_from_flask_session
from ..core.agent_manager import agent_manager
from ..core.message_bus import message_bus, MessageTypes, publish_message
from ..core.base_agent import BaseAgent
from typing import Dict, Any

class AgentError(Exception):
    """Custom exception cho các lỗi liên quan đến agent"""
    pass

class RouterAgent(BaseAgent):
    """
    Agent phân loại câu hỏi và chuyển đến agent phù hợp
    Sử dụng phương pháp "Rule-first, LLM fallback"

    Luồng xử lý:
    1. Khi người dùng truy cập:
       - Hiển thị giao diện xác thực (face_auth.html)
       - Người dùng có thể chọn xác minh khuôn mặt hoặc tiếp tục với tư cách khách
    2. Nếu xác minh khuôn mặt:
       - Customer agent xử lý xác thực
       - Lưu thông tin khách hàng vào session
    3. Nếu chọn tiếp tục với tư cách khách:
       - Tạo session tạm thời
       - Giới hạn một số tính năng
    4. Recommend agent xử lý các yêu cầu tiếp theo:
       - Phân tích ý định người dùng
       - Xác định các agent cần thiết
       - Format câu trả lời phù hợp
    """
    def __init__(self, agent_id: str = 'router'):
        """Khởi tạo router agent"""
        super().__init__(agent_id)
        self._llm = None
        self.context = None
        self._logger = logging.getLogger('agent.router')

        # Khởi tạo context từ Flask session
        self._load_context()

        # Định nghĩa các pattern regex cho từng loại câu hỏi
        self.patterns = {
            'graph': [
                r'(?i)(danh sách|liệt kê|có bao nhiêu|tìm kiếm|tìm|hiển thị|thống kê|báo cáo|số lượng)',
                r'(?i)(khách hàng|sản phẩm|đơn hàng|hóa đơn|doanh thu|doanh số|nhân viên|chi nhánh)'
            ],
            'product': [
                r'(?i)(thông tin|chi tiết|mô tả|giá|đặc điểm)',
                r'(?i)(sản phẩm|đồ uống|món)'
            ],
            'image': [
                r'(?i)(hình ảnh|ảnh|nhận diện|phát hiện)'
            ],
            'preference': [
                r'(?i)(sở thích|yêu thích|thích|không thích|preference)',
                r'(?i)(cập nhật|thay đổi|điều chỉnh|update|change)'
            ],
            'order': [
                r'(?i)(đặt hàng|mua|order|purchase)',
                r'(?i)(giỏ hàng|cart|checkout|thanh toán)'
            ],
            'auth': [
                r'(?i)(đăng nhập|login|sign in|signin|xác thực|xác minh|verify)',
                r'(?i)(khuôn mặt|face|nhận diện|recognition)'
            ]
        }

    async def setup(self, message_bus, context):
        """Initialize agent with message bus and context"""
        await super().setup(message_bus, context)
        self.context = context
        self._logger.info("Router agent initialized")

    def _load_context(self):
        """Tạo context từ Flask session"""
        try:
            self.context = create_context_from_flask_session()
            log_info(f"✅ Context loaded for session: {self.context.session.session_id}")

            if self.context.is_authenticated():
                log_info(f"👤 Authenticated user: {self.context.customer.name}")
            else:
                log_info("👤 Guest user")

        except Exception as e:
            log_error(f"❌ Error loading context: {str(e)}")
            # Create default context
            from ...models.context import create_context_from_session
            self.context = create_context_from_session('default')
            raise AgentError("Không thể tải context")

    @property
    @lru_cache()
    def llm(self):
        """Lazy load và cache LLM instance"""
        if self._llm is None:
            # Sử dụng gemini_client với temperature mặc định
            self._llm = gemini_client.model
        return self._llm

    def classify_with_rules(self, message):
        """Phân loại tin nhắn dựa trên rules"""
        try:
            # Kiểm tra từng loại pattern
            for agent_type, patterns in self.patterns.items():
                if any(re.search(pattern, message) for pattern in patterns):
                    return agent_type
            return None
        except Exception as e:
            log_error(f"Lỗi khi phân loại bằng rules: {str(e)}")
            return None

    def classify_with_llm(self, message):
        """Phân loại tin nhắn sử dụng LLM"""
        prompt = """Phân loại câu hỏi vào một trong các loại sau:
        - graph: Câu hỏi về số liệu, thống kê, báo cáo, dữ liệu
        - product: Câu hỏi về thông tin sản phẩm, đề xuất
        - image: Câu hỏi liên quan đến hình ảnh
        - preference: Câu hỏi về sở thích, cập nhật thông tin cá nhân
        - order: Câu hỏi về đặt hàng, giỏ hàng, thanh toán
        - auth: Câu hỏi về đăng nhập, xác thực khuôn mặt

        Câu hỏi: "{message}"

        Trả lời chỉ với một từ duy nhất: graph, product, image, preference, order, hoặc auth.
        """

        try:
            response = self.llm.invoke(prompt).content
            response = response.strip().lower()

            # Đảm bảo response là một trong các loại hợp lệ
            if response in ['product', 'image', 'graph', 'preference', 'order', 'auth']:
                return response
            else:
                # Mặc định trả về graph nếu LLM không trả về loại hợp lệ
                return 'graph'
        except Exception as e:
            log_error(f"Lỗi khi phân loại bằng LLM: {str(e)}")
            # Fallback về graph nếu có lỗi
            return 'graph'

    async def get_agent_instance(self, agent_type):
        """Lấy instance của agent theo loại sử dụng AgentManager"""
        try:
            # Map agent types to standard names
            agent_name_map = {
                'product': 'graphrag',
                'graph': 'graphrag',
                'sql': 'graphrag',
                'auth': 'customer',
                'image': 'image',
                'preference': 'preference',
                'recommend': 'recommend',
                'order': 'order'
            }

            agent_name = agent_name_map.get(agent_type, agent_type)

            if agent_name == 'order':
                # TODO: Implement OrderAgent
                raise AgentError("Order agent chưa được triển khai")

            # Use AgentManager to get agent instance
            agent = await agent_manager.get_agent(agent_name)
            if agent is None:
                raise AgentError(f"Không thể lấy agent: {agent_name}")

            return agent

        except Exception as e:
            log_error(f"❌ Lỗi khi lấy agent {agent_type}: {str(e)}")
            raise AgentError(f"Không thể lấy agent {agent_type}")

    @performance_timer('router')
    async def process_message(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Xử lý tin nhắn và điều hướng đến agent phù hợp"""
        try:
            # Extract message text and image path
            message_text = message.get('message', '')
            image_path = message.get('image_path')

            # Cập nhật context với tin nhắn hiện tại
            self.context.current_message = message_text
            if image_path:
                self.context.image_path = image_path

            # Thêm tin nhắn vào lịch sử
            self.context.add_chat_message(message_text, is_user=True)

            # Publish message received event
            publish_message(
                MessageTypes.QUERY_RECEIVED,
                'router',
                {'message': message_text, 'image_path': image_path},
                self.context
            )

            # Phân loại bằng rules trước
            log_info(f"🔍 [STEP 1] Phân loại câu hỏi bằng rules")
            agent_type = self.classify_with_rules(message_text)

            # Nếu rules không chắc chắn, fallback sang LLM
            if agent_type is None:
                log_info(f"🤖 [STEP 1.1] Rules không xác định, sử dụng LLM để phân loại")
                agent_type = self.classify_with_llm(message_text)

            log_info(f"✅ [STEP 1.2] Phân loại câu hỏi: '{message_text}' -> {agent_type}")

            # Cập nhật agent_type vào context
            self.context.agent_type = agent_type
            self.context.from_agent = 'router'

            # Nếu là yêu cầu xác thực, xử lý trực tiếp với Customer agent
            if agent_type == 'auth':
                log_info(f"🔐 [STEP 2] Xử lý yêu cầu xác thực với Customer agent")
                customer_agent = await self.get_agent_instance('auth')
                response = await customer_agent.process_message(message)

                # Add response to chat history
                self.context.add_chat_message(response, is_user=False)
                return response

            # Kiểm tra xác thực cho các yêu cầu cần đăng nhập
            if agent_type in ['preference', 'order'] and not self.context.is_authenticated():
                log_info(f"🚫 [STEP 2] Yêu cầu cần đăng nhập nhưng chưa xác thực")
                response = "Vui lòng đăng nhập để sử dụng tính năng này. Bạn có thể xác minh danh tính bằng khuôn mặt hoặc tiếp tục với tư cách khách."
                self.context.add_chat_message(response, is_user=False)
                return response

            # Lấy Recommend agent để xử lý tin nhắn
            log_info(f"🎯 [STEP 3] Xử lý tin nhắn với Recommend agent")
            recommend_agent = await self.get_agent_instance('recommend')
            response = await recommend_agent.process_message(message)

            # Add response to chat history
            self.context.add_chat_message(response, is_user=False)

            # Publish query processed event
            publish_message(
                MessageTypes.QUERY_PROCESSED,
                'router',
                {'message': message_text, 'response': response, 'agent_type': agent_type},
                self.context
            )

            log_info(f"✅ [STEP 4] Nhận được phản hồi từ Recommend agent")
            return response

        except Exception as e:
            log_error(f"❌ Lỗi khi xử lý tin nhắn: {str(e)}")

            # Publish error event
            publish_message(
                MessageTypes.QUERY_FAILED,
                'router',
                {'message': message_text, 'error': str(e)},
                self.context
            )

            error_response = f"Xin lỗi, có lỗi xảy ra: {str(e)}"
            self.context.add_chat_message(error_response, is_user=False)
            return error_response

    def get_context(self) -> AgentContext:
        """Lấy context hiện tại"""
        return self.context

    async def cleanup(self):
        """Cleanup router agent"""
        try:
            if hasattr(self, 'context'):
                self.context = None
            log_info("🧹 Router agent cleaned up")
        except Exception as e:
            log_error(f"❌ Error during router cleanup: {str(e)}")
