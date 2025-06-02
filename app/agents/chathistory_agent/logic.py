"""
Chat history agent for analyzing chat history and managing chat sessions
"""
from typing import Dict, Any, List, Optional
from ...utils.logger import log_info, log_error

# Import components
from .storage import chat_history_storage
from .formatter import chat_history_formatter
from .query_enhancer import query_enhancer
from .context_extractor import extract_context_from_history
from .history_analyzer import analyze_chat_history

class ChatHistoryAgent:
    """Agent phân tích lịch sử chat và quản lý phiên chat"""

    def __init__(self):
        """Khởi tạo Chat History Agent"""
        log_info("🔄 Khởi tạo Chat History Agent...")
        self.storage = chat_history_storage
        self.formatter = chat_history_formatter
        self.query_enhancer = query_enhancer
        log_info("✅ Chat History Agent đã được khởi tạo")

    def get_session(self, session_id: str) -> Dict[str, Any]:
        """
        Lấy phiên chat cho session_id, tạo mới nếu chưa tồn tại

        Args:
            session_id (str): ID của phiên

        Returns:
            Dict[str, Any]: Thông tin phiên chat
        """
        return self.storage.get_session(session_id)

    def reset_session(self, session_id: str) -> None:
        """
        Reset phiên chat

        Args:
            session_id (str): ID của phiên
        """
        try:
            # Reset phiên trong storage
            self.storage.reset_session(session_id)
            log_info(f"Đã reset phiên chat {session_id}")

            # Không cần xóa memory_service nữa vì đã loại bỏ module này
            pass

        except Exception as e:
            log_error(f"Lỗi khi reset phiên chat {session_id}: {str(e)}")

    def add_message(self, session_id: str, user_message: str, bot_response: str = None, query_details: dict = None) -> None:
        """
        Thêm tin nhắn vào phiên chat

        Args:
            session_id (str): ID của phiên
            user_message (str): Tin nhắn của người dùng
            bot_response (str, optional): Phản hồi của bot
            query_details (dict, optional): Chi tiết về truy vấn (intent, cypher, kết quả, sản phẩm được chọn)
        """
        self.storage.add_message(session_id, user_message, bot_response, query_details)

    def update_bot_response(self, session_id: str, bot_response: str) -> None:
        """
        Cập nhật phản hồi của bot cho tin nhắn gần nhất

        Args:
            session_id (str): ID của phiên
            bot_response (str): Phản hồi của bot
        """
        self.storage.update_bot_response(session_id, bot_response)

    def get_chat_history(self, session_id: str) -> List[Dict[str, Any]]:
        """
        Lấy lịch sử chat cho session_id

        Args:
            session_id (str): ID của phiên

        Returns:
            List[Dict[str, Any]]: Danh sách các tin nhắn
        """
        return self.storage.get_chat_history(session_id)

    def extract_context_from_history(self, session_id: str, current_query: str) -> Dict[str, Any]:
        """
        Sử dụng LLM để phân tích lịch sử chat và trích xuất thông tin hữu ích làm ngữ cảnh

        Args:
            session_id (str): ID của phiên
            current_query (str): Câu truy vấn hiện tại của người dùng

        Returns:
            Dict[str, Any]: Thông tin ngữ cảnh trích xuất từ lịch sử chat
        """
        chat_history = self.get_chat_history(session_id)
        return extract_context_from_history(chat_history, current_query)

    def process_message(self, message: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Xử lý tin nhắn liên quan đến lịch sử chat

        Args:
            message (str): Tin nhắn cần xử lý
            context (Dict[str, Any], optional): Ngữ cảnh

        Returns:
            str: Phản hồi
        """
        try:
            # Lấy session_id từ context hoặc sử dụng default
            session_id = context.get('session_id', 'default') if context else 'default'

            # Lấy lịch sử chat
            chat_history = self.get_chat_history(session_id)

            if not chat_history:
                return "Chưa có lịch sử chat nào để phân tích."

            # Phân tích lịch sử chat
            analysis = analyze_chat_history(chat_history)

            # Tạo phản hồi
            return self.formatter.format_analysis_response(analysis)

        except Exception as e:
            log_error(f"Lỗi khi xử lý tin nhắn về lịch sử chat: {str(e)}")
            return f"Xin lỗi, đã xảy ra lỗi khi phân tích lịch sử chat: {str(e)}"

    def enhance_query_with_context(self, query: str, context: Dict[str, Any]) -> str:
        """
        Bổ sung ngữ cảnh vào câu truy vấn

        Args:
            query (str): Câu truy vấn gốc
            context (Dict[str, Any]): Ngữ cảnh trích xuất từ lịch sử chat

        Returns:
            str: Câu truy vấn đã được bổ sung ngữ cảnh
        """
        return self.query_enhancer.enhance_query(query, context)

    def detect_references_in_query(self, query: str) -> bool:
        """
        Phát hiện tham chiếu trong câu truy vấn

        Args:
            query (str): Câu truy vấn cần kiểm tra

        Returns:
            bool: True nếu có tham chiếu, False nếu không
        """
        return self.query_enhancer.detect_references(query)

    def format_chat_history_for_llm(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Định dạng lịch sử chat cho LLM

        Args:
            chat_history (List[Dict[str, Any]]): Lịch sử chat

        Returns:
            str: Lịch sử chat đã định dạng
        """
        return self.formatter.format_for_llm(chat_history)

    def format_chat_history_for_display(self, chat_history: List[Dict[str, Any]]) -> str:
        """
        Định dạng lịch sử chat để hiển thị

        Args:
            chat_history (List[Dict[str, Any]]): Lịch sử chat

        Returns:
            str: Lịch sử chat đã định dạng
        """
        return self.formatter.format_for_display(chat_history)

    def extract_filters_from_intent(self, intent: str) -> Dict[str, Any]:
        """
        Trích xuất các bộ lọc và tạo cấu trúc structured_query từ intent

        Args:
            intent (str): Intent được suy luận

        Returns:
            Dict[str, Any]: Cấu trúc structured_query
        """
        structured_query = {
            "intent": "",
            "filters": {},
            "product_type": "",
            "sort_by": "",
            "sort_order": ""
        }

        try:
            # Xác định intent chính
            if "tìm" in intent.lower():
                if "sản phẩm" in intent.lower() or "đồ uống" in intent.lower():
                    structured_query["intent"] = "Tìm đồ uống"
                elif "danh mục" in intent.lower() or "loại" in intent.lower():
                    structured_query["intent"] = "Tìm danh mục"
                else:
                    structured_query["intent"] = "Tìm kiếm"
            elif "thông tin" in intent.lower() or "chi tiết" in intent.lower():
                structured_query["intent"] = "Xem thông tin chi tiết"
            elif "so sánh" in intent.lower():
                structured_query["intent"] = "So sánh sản phẩm"
            elif "gợi ý" in intent.lower() or "đề xuất" in intent.lower() or "recommend" in intent.lower():
                structured_query["intent"] = "Gợi ý sản phẩm"
            else:
                # Intent mặc định
                structured_query["intent"] = "Tìm đồ uống"

            # Xác định loại sản phẩm
            product_types = {
                "cà phê": ["cà phê", "coffee", "espresso", "latte", "cappuccino", "americano", "mocha"],
                "trà": ["trà", "tea", "matcha", "chai"],
                "đá xay": ["đá xay", "frappuccino", "blended"],
                "sinh tố": ["sinh tố", "smoothie"],
                "nước trái cây": ["nước trái cây", "juice", "nước ép"]
            }

            for product_type, keywords in product_types.items():
                if any(keyword in intent.lower() for keyword in keywords):
                    structured_query["product_type"] = product_type
                    break

            # Phân tích intent để tìm các bộ lọc
            filters = {}

            # Kiểm tra các từ khóa liên quan đến lượng đường
            sugar_keywords = ['đường', 'sugar', 'ngọt']
            for keyword in sugar_keywords:
                if keyword in intent.lower():
                    # Tìm các con số gần từ khóa
                    import re
                    numbers = re.findall(r'\d+', intent)
                    if numbers:
                        # Giả định số đầu tiên là giá trị đường
                        sugar_value = numbers[0]

                        # Kiểm tra xem có phải là "dưới X" hay "trên X"
                        if any(word in intent.lower() for word in ['dưới', 'ít hơn', 'nhỏ hơn', 'less than']):
                            filters['sugars_g'] = f"< {sugar_value}"
                        elif any(word in intent.lower() for word in ['trên', 'nhiều hơn', 'lớn hơn', 'more than']):
                            filters['sugars_g'] = f"> {sugar_value}"
                        else:
                            filters['sugars_g'] = f"= {sugar_value}"

            # Kiểm tra các từ khóa liên quan đến giá
            price_keywords = ['giá', 'price', 'cost', 'đắt', 'rẻ', 'mắc', 'tiền']
            for keyword in price_keywords:
                if keyword in intent.lower():
                    # Tìm các con số gần từ khóa
                    import re
                    numbers = re.findall(r'\d+', intent)
                    if numbers:
                        # Giả định số đầu tiên là giá trị
                        price_value = numbers[0]
                        # Chuyển đổi thành giá tiền (nếu < 1000 thì nhân với 1000)
                        if int(price_value) < 1000:
                            price_value = str(int(price_value) * 1000)

                        # Kiểm tra xem có phải là "dưới X" hay "trên X"
                        if any(word in intent.lower() for word in ['dưới', 'ít hơn', 'nhỏ hơn', 'less than', 'rẻ']):
                            filters['price'] = f"< {price_value}"
                        elif any(word in intent.lower() for word in ['trên', 'nhiều hơn', 'lớn hơn', 'more than', 'đắt']):
                            filters['price'] = f"> {price_value}"
                        else:
                            filters['price'] = f"= {price_value}"

            # Kiểm tra các từ khóa liên quan đến caffeine
            caffeine_keywords = ['caffeine', 'cafein', 'cà phê in', 'tỉnh táo']
            for keyword in caffeine_keywords:
                if keyword in intent.lower():
                    # Tìm các con số gần từ khóa
                    import re
                    numbers = re.findall(r'\d+', intent)
                    if numbers:
                        # Giả định số đầu tiên là giá trị caffeine
                        caffeine_value = numbers[0]

                        # Kiểm tra xem có phải là "dưới X" hay "trên X"
                        if any(word in intent.lower() for word in ['dưới', 'ít hơn', 'nhỏ hơn', 'less than']):
                            filters['caffeine_mg'] = f"< {caffeine_value}"
                        elif any(word in intent.lower() for word in ['trên', 'nhiều hơn', 'lớn hơn', 'more than']):
                            filters['caffeine_mg'] = f"> {caffeine_value}"
                        else:
                            filters['caffeine_mg'] = f"= {caffeine_value}"
                    else:
                        # Nếu không có số cụ thể, kiểm tra các từ khóa chung
                        if any(word in intent.lower() for word in ['nhiều', 'cao', 'mạnh', 'high']):
                            filters['caffeine_mg'] = "> 100"
                        elif any(word in intent.lower() for word in ['ít', 'thấp', 'nhẹ', 'low']):
                            filters['caffeine_mg'] = "< 50"

            # Kiểm tra các từ khóa liên quan đến calories
            calorie_keywords = ['calories', 'calo', 'năng lượng', 'energy']
            for keyword in calorie_keywords:
                if keyword in intent.lower():
                    # Tìm các con số gần từ khóa
                    import re
                    numbers = re.findall(r'\d+', intent)
                    if numbers:
                        # Giả định số đầu tiên là giá trị calories
                        calorie_value = numbers[0]

                        # Kiểm tra xem có phải là "dưới X" hay "trên X"
                        if any(word in intent.lower() for word in ['dưới', 'ít hơn', 'nhỏ hơn', 'less than']):
                            filters['calories'] = f"< {calorie_value}"
                        elif any(word in intent.lower() for word in ['trên', 'nhiều hơn', 'lớn hơn', 'more than']):
                            filters['calories'] = f"> {calorie_value}"
                        else:
                            filters['calories'] = f"= {calorie_value}"
                    else:
                        # Nếu không có số cụ thể, kiểm tra các từ khóa chung
                        if any(word in intent.lower() for word in ['nhiều', 'cao', 'mạnh', 'high']):
                            filters['calories'] = "> 200"
                        elif any(word in intent.lower() for word in ['ít', 'thấp', 'nhẹ', 'low']):
                            filters['calories'] = "< 100"

            # Kiểm tra các từ khóa liên quan đến kích cỡ
            size_keywords = {
                'Tall': ['nhỏ', 'small', 'tall'],
                'Grande': ['vừa', 'medium', 'grande'],
                'Venti': ['lớn', 'large', 'venti']
            }

            for size, keywords in size_keywords.items():
                if any(keyword in intent.lower() for keyword in keywords):
                    filters['Beverage_Option'] = size
                    break

            # Kiểm tra các từ khóa liên quan đến đối tượng sử dụng
            target_keywords = {
                'trẻ em': ['trẻ em', 'trẻ con', 'children', 'kids'],
                'người lớn': ['người lớn', 'adults'],
                'người già': ['người già', 'elderly']
            }

            for target, keywords in target_keywords.items():
                if any(keyword in intent.lower() for keyword in keywords):
                    filters['ExtractedEntity'] = {
                        'type': 'Đối tượng sử dụng',
                        'name': target
                    }

            # Kiểm tra các từ khóa liên quan đến đặc điểm
            characteristic_keywords = {
                'mát lạnh': ['mát lạnh', 'refreshing', 'cool', 'mát', 'lạnh'],
                'ngọt ngào': ['ngọt ngào', 'sweet', 'ngọt'],
                'đắng': ['đắng', 'bitter'],
                'chua': ['chua', 'sour', 'acid'],
                'béo ngậy': ['béo ngậy', 'creamy', 'béo', 'ngậy'],
                'thơm': ['thơm', 'aromatic', 'fragrant']
            }

            for characteristic, keywords in characteristic_keywords.items():
                if any(keyword in intent.lower() for keyword in keywords):
                    if 'ExtractedEntity' not in filters:
                        filters['ExtractedEntity'] = {}

                    filters['ExtractedEntity'] = {
                        'type': 'Đặc điểm',
                        'name': characteristic
                    }

            # Kiểm tra các từ khóa liên quan đến nguyên liệu
            ingredient_keywords = {
                'sữa': ['sữa', 'milk'],
                'đá': ['đá', 'ice'],
                'chocolate': ['chocolate', 'sô cô la'],
                'caramel': ['caramel', 'ca ra men'],
                'vanilla': ['vanilla', 'va ni'],
                'matcha': ['matcha', 'trà xanh'],
                'trái cây': ['trái cây', 'fruit']
            }

            for ingredient, keywords in ingredient_keywords.items():
                if any(keyword in intent.lower() for keyword in keywords):
                    if 'ExtractedEntity' not in filters:
                        filters['ExtractedEntity'] = {}

                    filters['ExtractedEntity'] = {
                        'type': 'Nguyên liệu',
                        'name': ingredient
                    }

            # Phát hiện và xử lý hướng dẫn sắp xếp
            if "sắp xếp" in intent.lower() or "sort" in intent.lower() or "order" in intent.lower():
                # Kiểm tra sắp xếp theo giá
                if any(keyword in intent.lower() for keyword in ["giá", "price", "cost"]):
                    structured_query["sort_by"] = "price"

                    # Kiểm tra hướng sắp xếp
                    if any(phrase in intent.lower() for phrase in ["từ thấp đến cao", "tăng dần", "ascending", "asc"]):
                        structured_query["sort_order"] = "ASC"
                    elif any(phrase in intent.lower() for phrase in ["từ cao xuống thấp", "giảm dần", "descending", "desc"]):
                        structured_query["sort_order"] = "DESC"

                # Kiểm tra sắp xếp theo caffeine
                elif any(keyword in intent.lower() for keyword in ["caffeine", "cafein"]):
                    structured_query["sort_by"] = "caffeine_mg"

                    # Kiểm tra hướng sắp xếp
                    if any(phrase in intent.lower() for phrase in ["từ thấp đến cao", "tăng dần", "ascending", "asc"]):
                        structured_query["sort_order"] = "ASC"
                    elif any(phrase in intent.lower() for phrase in ["từ cao xuống thấp", "giảm dần", "descending", "desc"]):
                        structured_query["sort_order"] = "DESC"
                    else:
                        # Mặc định sắp xếp caffeine từ cao xuống thấp
                        structured_query["sort_order"] = "DESC"

                # Kiểm tra sắp xếp theo đường
                elif any(keyword in intent.lower() for keyword in ["đường", "sugar", "ngọt", "sweet"]):
                    structured_query["sort_by"] = "sugars_g"

                    # Kiểm tra hướng sắp xếp
                    if any(phrase in intent.lower() for phrase in ["từ thấp đến cao", "tăng dần", "ascending", "asc", "ít ngọt"]):
                        structured_query["sort_order"] = "ASC"
                    elif any(phrase in intent.lower() for phrase in ["từ cao xuống thấp", "giảm dần", "descending", "desc", "ngọt nhất"]):
                        structured_query["sort_order"] = "DESC"
                    else:
                        # Mặc định sắp xếp đường từ thấp đến cao
                        structured_query["sort_order"] = "ASC"

                # Kiểm tra sắp xếp theo calories
                elif any(keyword in intent.lower() for keyword in ["calories", "calo"]):
                    structured_query["sort_by"] = "calories"

                    # Kiểm tra hướng sắp xếp
                    if any(phrase in intent.lower() for phrase in ["từ thấp đến cao", "tăng dần", "ascending", "asc", "ít calo"]):
                        structured_query["sort_order"] = "ASC"
                    elif any(phrase in intent.lower() for phrase in ["từ cao xuống thấp", "giảm dần", "descending", "desc"]):
                        structured_query["sort_order"] = "DESC"
                    else:
                        # Mặc định sắp xếp calories từ thấp đến cao
                        structured_query["sort_order"] = "ASC"

                # Kiểm tra sắp xếp theo độ phổ biến
                elif any(keyword in intent.lower() for keyword in ["phổ biến", "popular", "bán chạy", "best seller"]):
                    structured_query["sort_by"] = "sales_rank"
                    structured_query["sort_order"] = "ASC"  # sales_rank thấp = phổ biến hơn

            # Kiểm tra các từ khóa đặc biệt cho sắp xếp
            if "rẻ nhất" in intent.lower() or "giá thấp nhất" in intent.lower() or "cheapest" in intent.lower():
                structured_query["sort_by"] = "price"
                structured_query["sort_order"] = "ASC"

            if "đắt nhất" in intent.lower() or "giá cao nhất" in intent.lower() or "most expensive" in intent.lower():
                structured_query["sort_by"] = "price"
                structured_query["sort_order"] = "DESC"

            if "phổ biến nhất" in intent.lower() or "bán chạy nhất" in intent.lower() or "most popular" in intent.lower():
                structured_query["sort_by"] = "sales_rank"
                structured_query["sort_order"] = "ASC"

            if "ít đường nhất" in intent.lower() or "ít ngọt nhất" in intent.lower() or "least sweet" in intent.lower():
                structured_query["sort_by"] = "sugars_g"
                structured_query["sort_order"] = "ASC"

            if "nhiều đường nhất" in intent.lower() or "ngọt nhất" in intent.lower() or "sweetest" in intent.lower():
                structured_query["sort_by"] = "sugars_g"
                structured_query["sort_order"] = "DESC"

            if "nhiều caffeine nhất" in intent.lower() or "tỉnh táo nhất" in intent.lower() or "most caffeine" in intent.lower():
                structured_query["sort_by"] = "caffeine_mg"
                structured_query["sort_order"] = "DESC"

            # Xác định cách sắp xếp từ filters nếu chưa có
            if not structured_query["sort_by"]:
                if 'price' in filters:
                    if filters['price'].startswith('<'):
                        structured_query['sort_by'] = 'price'
                        structured_query['sort_order'] = 'ASC'
                    elif filters['price'].startswith('>'):
                        structured_query['sort_by'] = 'price'
                        structured_query['sort_order'] = 'DESC'

                if 'sugars_g' in filters:
                    if filters['sugars_g'].startswith('<'):
                        structured_query['sort_by'] = 'sugars_g'
                        structured_query['sort_order'] = 'ASC'

                if 'caffeine_mg' in filters:
                    if filters['caffeine_mg'].startswith('>'):
                        structured_query['sort_by'] = 'caffeine_mg'
                        structured_query['sort_order'] = 'DESC'

            # Thêm filters vào structured_query
            structured_query['filters'] = filters

            return structured_query
        except Exception as e:
            log_error(f"Lỗi khi trích xuất filters từ intent: {str(e)}")
            return {
                "intent": "Tìm đồ uống",
                "filters": {},
                "product_type": "",
                "sort_by": "",
                "sort_order": ""
            }
