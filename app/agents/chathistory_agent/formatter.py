"""
Module for formatting chat history
"""
from typing import Dict, Any, List
from datetime import datetime
from abc import ABC, abstractmethod
from ...utils.logger import log_info, log_error

class ChatHistoryFormatter(ABC):
    """Abstract class for chat history formatter"""
    
    @abstractmethod
    def format_for_llm(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Format chat history for LLM
        
        Args:
            chat_history (List[Dict[str, Any]]): Chat history
            
        Returns:
            str: Formatted chat history
        """
        pass
    
    @abstractmethod
    def format_for_display(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Format chat history for display
        
        Args:
            chat_history (List[Dict[str, Any]]): Chat history
            
        Returns:
            str: Formatted chat history
        """
        pass
    
    @abstractmethod
    def format_analysis_response(self, analysis: Dict[str, Any]) -> str:
        """
        Format analysis response
        
        Args:
            analysis (Dict[str, Any]): Analysis result
            
        Returns:
            str: Formatted analysis response
        """
        pass

class DefaultChatHistoryFormatter(ChatHistoryFormatter):
    """Default implementation of chat history formatter"""
    
    def format_for_llm(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Format chat history for LLM
        
        Args:
            chat_history (List[Dict[str, Any]]): Chat history
            
        Returns:
            str: Formatted chat history
        """
        history_text = ""
        for i, message in enumerate(chat_history):
            user_msg = message.get('user_message', '')
            bot_msg = message.get('bot_response', '') if 'bot_response' in message else ''
            timestamp = message.get('timestamp', '')
            
            # Format timestamp for readability
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S")
            except:
                formatted_time = timestamp
            
            history_text += f"[{formatted_time}] Người dùng: {user_msg}\n"
            if bot_msg:
                history_text += f"[{formatted_time}] Bot: {bot_msg}\n"
            history_text += "\n"
        
        return history_text
    
    def format_for_display(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Format chat history for display
        
        Args:
            chat_history (List[Dict[str, Any]]): Chat history
            
        Returns:
            str: Formatted chat history
        """
        display_text = "Lịch sử trò chuyện:\n\n"
        for i, message in enumerate(chat_history):
            user_msg = message.get('user_message', '')
            bot_msg = message.get('bot_response', '') if 'bot_response' in message else ''
            timestamp = message.get('timestamp', '')
            
            # Format timestamp for readability
            try:
                dt = datetime.fromisoformat(timestamp)
                formatted_time = dt.strftime("%H:%M:%S")
            except:
                formatted_time = timestamp
            
            display_text += f"[{formatted_time}] Bạn: {user_msg}\n"
            if bot_msg:
                display_text += f"[{formatted_time}] Bot: {bot_msg}\n"
            display_text += "\n"
        
        return display_text
    
    def format_analysis_response(self, analysis: Dict[str, Any]) -> str:
        """
        Format analysis response
        
        Args:
            analysis (Dict[str, Any]): Analysis result
            
        Returns:
            str: Formatted analysis response
        """
        try:
            # Create response
            response = "Dựa trên lịch sử trò chuyện của chúng ta, tôi thấy rằng:\n\n"
            
            if analysis.get('mentioned_products'):
                response += f"- Bạn đã nhắc đến các sản phẩm: {', '.join(analysis['mentioned_products'])}\n"
            
            if analysis.get('mentioned_categories'):
                response += f"- Bạn đã nhắc đến các danh mục: {', '.join(analysis['mentioned_categories'])}\n"
            
            if analysis.get('question_count'):
                response += f"- Bạn đã đặt {analysis['question_count']} câu hỏi\n"
            
            if analysis.get('sentiment') != 'neutral':
                sentiment_text = "tích cực" if analysis['sentiment'] == 'positive' else "tiêu cực"
                response += f"- Cảm xúc của bạn trong cuộc trò chuyện có vẻ {sentiment_text}\n"
            
            if analysis.get('recent_focus'):
                focus_type, focus_value = analysis['recent_focus'].split(':')
                response += f"- Gần đây bạn đang quan tâm đến {focus_value} (thuộc loại {focus_type})\n"
            
            if not any([analysis.get('mentioned_products'), analysis.get('mentioned_categories'),
                       analysis.get('question_count'), analysis.get('sentiment') != 'neutral',
                       analysis.get('recent_focus')]):
                response = "Tôi chưa có đủ thông tin để phân tích lịch sử trò chuyện của chúng ta. Hãy tiếp tục trò chuyện để tôi hiểu bạn hơn."
            
            return response
            
        except Exception as e:
            log_error(f"Error formatting analysis response: {str(e)}")
            return "Xin lỗi, đã xảy ra lỗi khi phân tích lịch sử chat."

# Default formatter implementation
chat_history_formatter = DefaultChatHistoryFormatter()
