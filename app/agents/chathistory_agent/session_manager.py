"""
Session manager for chat history
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from collections import deque
from flask import session
from ...utils.logger import log_info, log_error

class ChatSessionManager:
    """Quản lý phiên chat cho người dùng"""

    def __init__(self, max_history_length: int = 3, session_timeout: int = 30):
        """
        Khởi tạo Chat Session Manager

        Args:
            max_history_length (int): Số lượng tin nhắn tối đa lưu trữ trong mỗi phiên
            session_timeout (int): Thời gian timeout của phiên (phút)
        """
        self._sessions = {}  # Dict lưu trữ phiên chat cho mỗi session_id
        self._max_history_length = max_history_length
        self._session_timeout = session_timeout
        log_info(f"Khởi tạo ChatSessionManager với max_history_length={max_history_length}, session_timeout={session_timeout} phút")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Lấy phiên chat cho session_id, tạo mới nếu chưa tồn tại

        Args:
            session_id (str): ID của phiên

        Returns:
            Dict[str, Any]: Thông tin phiên chat
        """
        # Kiểm tra và xóa các phiên hết hạn
        self._cleanup_expired_sessions()

        if session_id not in self._sessions:
            # Tạo phiên mới
            self._sessions[session_id] = {
                'created_at': datetime.now(),
                'last_updated': datetime.now(),
                'history': deque(maxlen=self._max_history_length),  # Giới hạn tin nhắn gần nhất
                'is_authenticated': False,
                'customer_id': None
            }
            log_info(f"Đã tạo phiên chat mới cho session {session_id}")
        else:
            # Cập nhật thời gian truy cập
            self._sessions[session_id]['last_updated'] = datetime.now()

        return self._sessions[session_id]

    def reset_session(self, session_id: str) -> None:
        """
        Reset phiên chat

        Args:
            session_id (str): ID của phiên
        """
        if session_id in self._sessions:
            del self._sessions[session_id]
            log_info(f"Đã reset phiên chat cho session {session_id}")

    def add_message(self, session_id: str, user_message: str, bot_response: str = None, query_details: dict = None) -> None:
        """
        Thêm tin nhắn vào phiên chat

        Args:
            session_id (str): ID của phiên
            user_message (str): Tin nhắn của người dùng
            bot_response (str, optional): Phản hồi của bot
            query_details (dict, optional): Chi tiết về truy vấn (intent, cypher, kết quả, sản phẩm được chọn)
        """
        try:
            session_data = self.get_session(session_id)

            # Lấy số thứ tự của tin nhắn trong phiên chat
            chat_turn = len(session_data['history']) + 1

            # Tạo entry mới với timestamp
            entry = {
                'chat_turn': chat_turn,
                'user_message': user_message,
                'timestamp': datetime.now().isoformat(),
            }

            # Nếu có phản hồi của bot, thêm luôn vào entry
            if bot_response:
                entry['bot_response'] = bot_response
                entry['bot_timestamp'] = datetime.now().isoformat()

            # Nếu có chi tiết truy vấn, thêm vào entry
            if query_details:
                # Thêm các thông tin chi tiết về truy vấn
                if 'structured_query' in query_details:
                    entry['structured_query'] = query_details['structured_query']

                if 'cypher_query' in query_details:
                    entry['cypher_query'] = query_details['cypher_query']

                if 'cypher_result' in query_details:
                    entry['cypher_result'] = query_details['cypher_result']

                if 'selected_products' in query_details:
                    entry['selected_product_list'] = query_details['selected_products']

            # Thêm vào deque (tự động loại bỏ tin nhắn cũ nếu vượt quá maxlen)
            session_data['history'].append(entry)
            session_data['last_updated'] = datetime.now()

            log_info(f"Đã thêm tin nhắn mới vào phiên chat {session_id}")
            if bot_response:
                log_info(f"Đã thêm cả phản hồi của bot vào phiên chat {session_id}")
            if query_details:
                log_info(f"Đã thêm chi tiết truy vấn vào phiên chat {session_id}")
        except Exception as e:
            log_error(f"Lỗi khi thêm tin nhắn vào phiên chat: {str(e)}")

    def update_bot_response(self, session_id: str, bot_response: str) -> None:
        """
        Cập nhật phản hồi của bot cho tin nhắn gần nhất

        Args:
            session_id (str): ID của phiên
            bot_response (str): Phản hồi của bot
        """
        try:
            session_data = self.get_session(session_id)

            if not session_data['history']:
                log_error("Không thể cập nhật phản hồi của bot: Không có tin nhắn nào trong lịch sử")
                return

            # Lấy tin nhắn gần nhất
            latest_message = session_data['history'][-1]

            # Cập nhật phản hồi của bot
            latest_message['bot_response'] = bot_response
            latest_message['bot_timestamp'] = datetime.now().isoformat()

            log_info(f"Đã cập nhật phản hồi của bot cho tin nhắn gần nhất trong phiên {session_id}")
        except Exception as e:
            log_error(f"Lỗi khi cập nhật phản hồi của bot: {str(e)}")

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử chat cho session_id

        Args:
            session_id (str): ID của phiên

        Returns:
            List[Dict[str, Any]]: Danh sách các tin nhắn
        """
        try:
            session_data = self.get_session(session_id)
            # Chuyển deque thành list để dễ sử dụng
            return list(session_data['history'])
        except Exception as e:
            log_error(f"Lỗi khi lấy lịch sử chat: {str(e)}")
            return []

    def set_customer_info(self, session_id: str, customer_id: str, is_authenticated: bool = True) -> None:
        """
        Cập nhật thông tin khách hàng cho phiên chat

        Args:
            session_id (str): ID của phiên
            customer_id (str): ID của khách hàng
            is_authenticated (bool): Trạng thái xác thực
        """
        try:
            session_data = self.get_session(session_id)
            session_data['customer_id'] = customer_id
            session_data['is_authenticated'] = is_authenticated
            session_data['last_updated'] = datetime.now()

            log_info(f"Đã cập nhật thông tin khách hàng cho phiên {session_id}: customer_id={customer_id}, is_authenticated={is_authenticated}")
        except Exception as e:
            log_error(f"Lỗi khi cập nhật thông tin khách hàng: {str(e)}")

    def _cleanup_expired_sessions(self) -> None:
        """Xóa các phiên đã hết hạn"""
        try:
            now = datetime.now()
            expired_sessions = []

            for session_id, session_data in self._sessions.items():
                last_updated = session_data['last_updated']
                if now - last_updated > timedelta(minutes=self._session_timeout):
                    expired_sessions.append(session_id)

            for session_id in expired_sessions:
                del self._sessions[session_id]
                log_info(f"Đã xóa phiên chat hết hạn: {session_id}")

            if expired_sessions:
                log_info(f"Đã xóa {len(expired_sessions)} phiên chat hết hạn")
        except Exception as e:
            log_error(f"Lỗi khi dọn dẹp phiên hết hạn: {str(e)}")

    def get_session_count(self) -> int:
        """
        Lấy số lượng phiên hiện tại

        Returns:
            int: Số lượng phiên
        """
        return len(self._sessions)

# Singleton instance
chat_session_manager = ChatSessionManager()
