"""
Module for analyzing chat history
"""
from typing import Dict, Any, List
from datetime import datetime
from ...utils.logger import log_info, log_error

def analyze_chat_history(chat_history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Phân tích lịch sử chat để tìm thông tin hữu ích
    
    Args:
        chat_history (List[Dict[str, Any]]): Lịch sử chat cần phân tích
        
    Returns:
        Dict[str, Any]: Kết quả phân tích
    """
    try:
        if not chat_history:
            return {}
        
        # Danh sách từ khóa cần tìm
        keywords = {
            'products': ['coffee', 'cà phê', 'tea', 'trà', 'chocolate', 'sô cô la', 
                       'caramel', 'vanilla', 'vani', 'mocha', 'latte', 'cappuccino',
                       'espresso', 'americano', 'frappuccino'],
            'categories': ['coffee', 'cà phê', 'tea', 'trà', 'chocolate', 'sô cô la',
                         'smoothie', 'sinh tố', 'frappuccino'],
            'preferences': ['thích', 'yêu thích', 'ưa thích', 'prefer', 'like', 'love', 'favorite'],
            'price': ['giá', 'price', 'cost', 'expensive', 'cheap', 'đắt', 'rẻ', 'mắc', 'tiền'],
            'size': ['size', 'cỡ', 'kích thước', 'nhỏ', 'vừa', 'lớn', 'small', 'medium', 'large']
        }
        
        # Kết quả phân tích
        analysis = {
            'mentioned_products': set(),
            'mentioned_categories': set(),
            'mentioned_preferences': set(),
            'price_mentions': [],
            'size_mentions': [],
            'question_count': 0,
            'sentiment': 'neutral',
            'recent_focus': None  # Chủ đề gần đây nhất
        }
        
        # Phân tích từng tin nhắn
        for message in chat_history:
            user_message = message.get('user_message', '').lower()
            bot_response = message.get('bot_response', '').lower() if 'bot_response' in message else ''
            
            # Đếm số câu hỏi
            if '?' in user_message:
                analysis['question_count'] += 1
            
            # Tìm từ khóa trong tin nhắn người dùng
            for category, terms in keywords.items():
                for term in terms:
                    if term.lower() in user_message:
                        if category == 'products':
                            analysis['mentioned_products'].add(term)
                        elif category == 'categories':
                            analysis['mentioned_categories'].add(term)
                        elif category == 'preferences':
                            analysis['mentioned_preferences'].add(term)
                        elif category == 'price':
                            analysis['price_mentions'].append(user_message)
                        elif category == 'size':
                            analysis['size_mentions'].append(user_message)
            
            # Phân tích cảm xúc (đơn giản)
            positive_words = ['thích', 'tốt', 'ngon', 'tuyệt', 'good', 'great', 'delicious', 'excellent']
            negative_words = ['không thích', 'tệ', 'dở', 'bad', 'terrible', 'awful']
            
            positive_count = sum(1 for word in positive_words if word in user_message)
            negative_count = sum(1 for word in negative_words if word in user_message)
            
            if positive_count > negative_count:
                analysis['sentiment'] = 'positive'
            elif negative_count > positive_count:
                analysis['sentiment'] = 'negative'
        
        # Chuyển đổi set thành list để dễ sử dụng
        analysis['mentioned_products'] = list(analysis['mentioned_products'])
        analysis['mentioned_categories'] = list(analysis['mentioned_categories'])
        analysis['mentioned_preferences'] = list(analysis['mentioned_preferences'])
        
        # Xác định chủ đề gần đây nhất
        if chat_history and len(chat_history) > 0:
            latest_message = chat_history[-1].get('user_message', '').lower()
            
            # Kiểm tra chủ đề trong tin nhắn gần nhất
            for category, terms in keywords.items():
                for term in terms:
                    if term.lower() in latest_message:
                        if category == 'products':
                            analysis['recent_focus'] = f"product:{term}"
                            break
                        elif category == 'categories':
                            analysis['recent_focus'] = f"category:{term}"
                            break
        
        return analysis
    
    except Exception as e:
        log_error(f"Lỗi khi phân tích lịch sử chat: {str(e)}")
        return {}

def format_analysis_response(analysis: Dict[str, Any]) -> str:
    """
    Tạo phản hồi từ kết quả phân tích lịch sử chat
    
    Args:
        analysis (Dict[str, Any]): Kết quả phân tích
        
    Returns:
        str: Phản hồi định dạng
    """
    try:
        # Tạo phản hồi
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
        log_error(f"Lỗi khi tạo phản hồi từ phân tích lịch sử chat: {str(e)}")
        return "Xin lỗi, đã xảy ra lỗi khi phân tích lịch sử chat."


