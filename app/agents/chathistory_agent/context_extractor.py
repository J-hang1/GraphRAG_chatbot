"""
Module for extracting context from chat history
"""
from typing import Dict, Any, List
import json
import re
from ...utils.logger import log_info, log_error
from ...llm_clients.gemini_client import gemini_client
from .history_analyzer import analyze_chat_history
from .formatter import chat_history_formatter

def extract_context_from_history(chat_history: List[Dict[str, Any]], current_query: str) -> Dict[str, Any]:
    """
    Sử dụng LLM để phân tích lịch sử chat và trích xuất thông tin hữu ích làm ngữ cảnh

    Args:
        chat_history (List[Dict[str, Any]]): Lịch sử chat cần phân tích
        current_query (str): Câu truy vấn hiện tại của người dùng

    Returns:
        Dict[str, Any]: Thông tin ngữ cảnh trích xuất từ lịch sử chat
    """
    try:
        if not chat_history:
            return {}

        # Chuyển đổi lịch sử chat thành chuỗi để đưa vào prompt
        history_text = chat_history_formatter.format_for_llm(chat_history)

        # Tạo prompt để phân tích lịch sử chat
        prompt = create_context_extraction_prompt(history_text, current_query)

        # Gọi LLM để phân tích
        response = gemini_client.generate_text(prompt)

        # Trích xuất JSON từ phản hồi
        try:
            # Tìm JSON trong phản hồi
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = response

            # Làm sạch chuỗi
            json_str = re.sub(r'```.*?```', '', json_str, flags=re.DOTALL)

            # Parse JSON
            context = json.loads(json_str)
            log_info(f"Đã trích xuất ngữ cảnh từ lịch sử chat: {str(context)[:200]}...")
            return context
        except Exception as e:
            log_error(f"Lỗi khi parse JSON từ phản hồi LLM: {str(e)}")
            # Fallback: Sử dụng phân tích đơn giản
            return analyze_chat_history(chat_history)

    except Exception as e:
        log_error(f"Lỗi khi trích xuất ngữ cảnh từ lịch sử chat: {str(e)}")
        return {}

from .formatter import chat_history_formatter

def create_context_extraction_prompt(history_text: str, current_query: str) -> str:
    """
    Tạo prompt để trích xuất ngữ cảnh từ lịch sử chat

    Args:
        history_text (str): Chuỗi lịch sử chat đã định dạng
        current_query (str): Câu truy vấn hiện tại của người dùng

    Returns:
        str: Prompt để trích xuất ngữ cảnh
    """
    prompt = f"""Bạn là một trợ lý AI chuyên nghiệp, nhiệm vụ của bạn là phân tích lịch sử trò chuyện và trích xuất thông tin hữu ích để hiểu ngữ cảnh cho câu hỏi hiện tại.

LỊCH SỬ TRÒ CHUYỆN:
{history_text}

CÂU HỎI HIỆN TẠI:
{current_query}

HƯỚNG DẪN PHÂN TÍCH:
1. Đọc kỹ lịch sử trò chuyện và câu hỏi hiện tại
2. Xác định mối liên hệ giữa câu hỏi hiện tại và các tin nhắn trước đó
3. Đặc biệt chú ý đến các từ tham chiếu như "này", "đó", "kia", "loại đó", "sản phẩm đó", v.v.
4. Nếu câu hỏi hiện tại có chứa từ "loại nào", "loại nào rẻ nhất", "loại nào đắt nhất", v.v., hãy xác định rõ "loại" đang đề cập đến sản phẩm hoặc danh mục nào
5. Nếu câu hỏi hiện tại có chứa từ "trong đó", hãy xác định rõ "đó" đang đề cập đến sản phẩm hoặc danh mục nào

THÔNG TIN CẦN TRÍCH XUẤT:
1. Các sản phẩm cụ thể được nhắc đến (ví dụ: "Brewed Coffee", "Cappuccino", v.v.)
2. Các danh mục sản phẩm được nhắc đến (ví dụ: "cà phê", "trà", "đồ uống đá xay", v.v.)
3. Các sở thích được thể hiện (ví dụ: "không đường", "ít đá", "nhiều sữa", v.v.)
4. Các yêu cầu về giá cả (ví dụ: "rẻ", "dưới 50.000 đồng", v.v.)
5. Các yêu cầu về kích thước (ví dụ: "size lớn", "Tall", "Grande", v.v.)
6. Các yêu cầu về dinh dưỡng (ví dụ: "ít calo", "nhiều protein", v.v.)
7. Ý định tìm kiếm gần đây (ví dụ: "tìm cà phê", "so sánh giá", v.v.)
8. Phân tích các tham chiếu trong câu hỏi hiện tại (ví dụ: "loại đó" đề cập đến "Brewed Coffee")

PHÂN TÍCH ĐẶC BIỆT CHO CÂU HỎI HIỆN TẠI:
- Nếu câu hỏi hiện tại là "loại nào trong đó là rẻ nhất" và trước đó đã nhắc đến "cà phê không đường", thì "loại" đang đề cập đến các biến thể (size) của "cà phê không đường"
- Nếu câu hỏi hiện tại là "loại nào trong đó là rẻ nhất" và trước đó đã nhắc đến danh mục "cà phê", thì "loại" đang đề cập đến các sản phẩm trong danh mục "cà phê"
- Nếu câu hỏi hiện tại có chứa "có bao nhiêu loại" và trước đó đã nhắc đến một sản phẩm, thì câu hỏi đang hỏi về số lượng biến thể của sản phẩm đó

Trả về kết quả dưới dạng JSON với các trường sau:
{
  "mentioned_products": ["Sản phẩm 1", "Sản phẩm 2", ...],
  "mentioned_categories": ["Danh mục 1", "Danh mục 2", ...],
  "preferences": ["Sở thích 1", "Sở thích 2", ...],
  "price_requirements": "Yêu cầu về giá cả",
  "size_requirements": "Yêu cầu về kích thước",
  "nutrition_requirements": "Yêu cầu về dinh dưỡng",
  "last_intent": "Ý định tìm kiếm gần đây",
  "recent_references": "Phân tích các tham chiếu",
  "context_summary": "Tóm tắt ngắn gọn ngữ cảnh cuộc trò chuyện liên quan đến câu hỏi hiện tại"
}

Chỉ trả về JSON, không thêm giải thích hoặc văn bản khác.
"""

    return prompt

def enhance_query_with_context(query: str, context: Dict[str, Any]) -> str:
    """
    Bổ sung ngữ cảnh vào câu truy vấn

    Args:
        query (str): Câu truy vấn gốc
        context (Dict[str, Any]): Ngữ cảnh trích xuất từ lịch sử chat

    Returns:
        str: Câu truy vấn đã được bổ sung ngữ cảnh
    """
    if not context:
        return query

    # Tạo phần bổ sung ngữ cảnh
    context_parts = []

    # Thêm sản phẩm được nhắc đến
    if 'mentioned_products' in context and context['mentioned_products']:
        products = ', '.join(context['mentioned_products'])
        context_parts.append(f"sản phẩm: {products}")

    # Thêm danh mục được nhắc đến
    if 'mentioned_categories' in context and context['mentioned_categories']:
        categories = ', '.join(context['mentioned_categories'])
        context_parts.append(f"danh mục: {categories}")

    # Thêm sở thích
    if 'preferences' in context and context['preferences']:
        preferences = ', '.join(context['preferences'])
        context_parts.append(f"sở thích: {preferences}")

    # Thêm yêu cầu về giá
    if 'price_requirements' in context and context['price_requirements']:
        context_parts.append(f"yêu cầu giá: {context['price_requirements']}")

    # Thêm tham chiếu gần đây
    if 'recent_references' in context and context['recent_references']:
        context_parts.append(f"tham chiếu gần đây: {context['recent_references']}")

    # Tạo câu hỏi mở rộng với ngữ cảnh
    if context_parts:
        context_str = '; '.join(context_parts)
        enhanced_query = f"{query} (Ngữ cảnh từ cuộc trò chuyện trước: {context_str})"
        log_info(f"Đã bổ sung ngữ cảnh vào câu truy vấn: {enhanced_query}")
        return enhanced_query

    return query
