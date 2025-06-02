"""
Module xử lý nâng cao cho việc suy luận ý định từ câu hỏi người dùng
Hỗ trợ nhiều loại truy vấn khác nhau: sản phẩm, cửa hàng, đơn hàng, danh mục
Đã được cập nhật để xác thực thông tin từ Neo4j
"""
import json
import re
from typing import Dict, List, Any, Optional, Tuple, Union

from ...utils.logger import log_info, log_error
from ...llm_clients.gemini_client import gemini_client
from ...utils.llm_counter import count_llm_call
from .prompt_templates_updated import INTENT_INFERENCE_TEMPLATE
from ...utils.vietnamese_to_english_mapping import translate_vietnamese_to_english, translate_english_to_vietnamese
from .database_validator import DatabaseValidator

# Định nghĩa các loại ý định
INTENT_TYPES = {
    "PRODUCT_SEARCH": "tìm kiếm sản phẩm",
    "PRODUCT_INFO": "thông tin sản phẩm",
    "CATEGORY_SEARCH": "tìm kiếm danh mục",
    "CATEGORY_INFO": "thông tin danh mục",
    "STORE_INFO": "thông tin cửa hàng",
    "ORDER_INFO": "thông tin đơn hàng",
    "ORDER_HISTORY": "lịch sử đơn hàng",
    "RECOMMENDATION": "gợi ý sản phẩm",
    "GREETING": "chào hỏi",
    "GENERAL_QUERY": "câu hỏi chung"
}

# Từ khóa để phân loại ý định
INTENT_KEYWORDS = {
    INTENT_TYPES["PRODUCT_SEARCH"]: [
        "tìm", "kiếm", "có", "bán", "sản phẩm", "đồ uống", "thức uống", "nước", "cà phê", "trà", "trà sữa", "sinh tố"
    ],
    INTENT_TYPES["PRODUCT_INFO"]: [
        "thông tin", "chi tiết", "mô tả", "giá", "calo", "đường", "caffeine", "thành phần"
    ],
    INTENT_TYPES["CATEGORY_SEARCH"]: [
        "danh mục", "loại", "nhóm", "phân loại"
    ],
    INTENT_TYPES["CATEGORY_INFO"]: [
        "danh mục", "loại", "nhóm", "thông tin danh mục"
    ],
    INTENT_TYPES["STORE_INFO"]: [
        "cửa hàng", "chi nhánh", "địa chỉ", "vị trí", "mở cửa", "đóng cửa", "giờ", "địa điểm"
    ],
    INTENT_TYPES["ORDER_INFO"]: [
        "đơn hàng", "đặt hàng", "mua", "thanh toán", "hóa đơn", "đơn", "trạng thái đơn"
    ],
    INTENT_TYPES["ORDER_HISTORY"]: [
        "lịch sử", "đơn hàng cũ", "mua trước đây", "đã mua", "đã đặt"
    ],
    INTENT_TYPES["RECOMMENDATION"]: [
        "gợi ý", "đề xuất", "recommend", "nên uống", "phù hợp", "thích hợp", "nên thử"
    ],
    INTENT_TYPES["GREETING"]: [
        "xin chào", "chào", "hello", "hi", "hey", "tạm biệt", "goodbye"
    ]
}

# Từ khóa tiếng Anh cho các loại đồ uống
ENGLISH_BEVERAGE_KEYWORDS = {
    "coffee": ["coffee", "brewed coffee", "espresso", "latte", "cappuccino", "americano", "mocha", "macchiato", "flat white", "cold brew"],
    "tea": ["tea", "chai", "matcha", "green tea", "black tea", "oolong", "tazo tea", "shaken tea"],
    "milk tea": ["milk tea", "bubble tea", "boba", "pearl milk tea", "chai tea latte", "green tea latte"],
    "smoothie": ["smoothie", "banana chocolate smoothie", "orange mango banana smoothie", "strawberry banana smoothie"],
    "juice": ["juice", "orange juice", "apple juice", "fruit juice", "fresh juice"],
    "frappuccino": ["frappuccino", "frappe", "blended", "iced blended", "coffee frappuccino", "mocha frappuccino", "caramel frappuccino", "java chip frappuccino"],
    "hot chocolate": ["hot chocolate", "chocolate"],
    "other": ["caramel apple spice", "strawberries & crème", "vanilla bean"]
}

# Từ khóa tiếng Việt cho các loại đồ uống
VIETNAMESE_BEVERAGE_KEYWORDS = {
    "cà phê": ["cà phê", "cafe", "cà phê phin", "cà phê espresso", "cà phê sữa", "cà phê cappuccino", "cà phê americano", "cà phê mocha", "cà phê macchiato", "cà phê đá", "cà phê ủ lạnh"],
    "trà": ["trà", "chè", "trà xanh", "trà đen", "trà ô long", "trà hoa lài", "trà earl grey", "trà chai", "trà matcha", "trà thảo mộc", "trà đá lắc", "trà chanh đá lắc"],
    "trà sữa": ["trà sữa", "trà sữa trân châu", "trà chai sữa", "trà xanh sữa", "trà sữa khoai môn", "trà sữa thái"],
    "sinh tố": ["sinh tố", "sinh tố chuối sô cô la", "sinh tố cam xoài chuối", "sinh tố dâu chuối", "sinh tố trái cây", "sinh tố sữa chua"],
    "nước ép": ["nước ép", "nước cam", "nước táo", "nước dưa hấu", "nước dứa", "nước ép cà rốt", "nước ép hỗn hợp", "nước trái cây", "nước ép tươi"],
    "đá xay": ["đá xay", "cà phê đá xay", "mocha đá xay", "caramel đá xay", "java chip đá xay", "đồ uống đá xay"],
    "sô cô la": ["sô cô la nóng", "sô cô la"],
    "khác": ["táo caramel gia vị", "kem dâu", "kem vani", "soda", "nước có ga", "soda chanh", "soda dâu", "soda đào", "soda chanh dây"]
}

# Danh sách các danh mục từ cơ sở dữ liệu
CATEGORIES = {
    1: "Classic Espresso Drinks",
    2: "Coffee",
    3: "Frappuccino Blended Coffee",
    4: "Frappuccino Blended Crème",
    5: "Frappuccino Light Blended Coffee",
    6: "Shaken Iced Beverages",
    7: "Signature Espresso Drinks",
    8: "Smoothies",
    9: "Tazo Tea Drinks"
}

# Danh sách các cộng đồng sản phẩm từ cơ sở dữ liệu
PRODUCT_COMMUNITIES = {
    0: "Product Community 0",
    1: "Product Community 1",
    2: "Product Community 2",
    3: "Product Community 3",  # Chứa các sản phẩm sinh tố
    4: "Product Community 4"   # Chứa sản phẩm Brewed Coffee
}

def infer_enhanced_intent(question: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Suy luận ý định nâng cao của người dùng từ câu hỏi và ngữ cảnh
    Đã được cải tiến để giảm số lần gọi LLM không cần thiết và cải thiện việc trích xuất tên sản phẩm

    Args:
        question (str): Câu hỏi của người dùng
        context (Dict, optional): Ngữ cảnh bổ sung (thông tin khách hàng, lịch sử chat)

    Returns:
        Dict[str, Any]: Ý định được suy luận với các thông tin chi tiết
    """
    log_info("\n1️⃣ Inferring enhanced user intent...")
    log_info(f"📝 Input question: {question}")

    if context:
        log_info(f"📝 Context provided: {str(context)[:200]}...")

    # Tạo intent mặc định
    default_intent = {
        "intent_type": INTENT_TYPES["GENERAL_QUERY"],
        "intent_text": f"Tìm kiếm thông tin về {question}",
        "entities": [],
        "product_names": {
            "vi": [],
            "en": []
        },
        "category_names": [],
        "filters": {},
        "is_store_query": False,
        "is_order_query": False,
        "confidence": 0.5
    }

    try:
        # Kiểm tra câu hỏi trống
        if not question or question.strip() == "":
            log_error("Empty question provided to intent inference")
            return default_intent

        # Bước 1: Phân loại ý định dựa trên từ khóa
        intent_type, confidence = _classify_intent_by_keywords(question)

        # Bước 2: Trích xuất thông tin sản phẩm và danh mục
        product_names = _extract_product_names(question)
        category_names = _extract_category_names(question)

        # Bước 2.1: Xác thực thông tin từ Neo4j
        validated_product_names = DatabaseValidator.validate_product_names(product_names)
        validated_category_names = DatabaseValidator.validate_category_names(category_names)

        # Sử dụng thông tin đã được xác thực nếu có, nếu không thì giữ nguyên
        if validated_product_names["vi"] or validated_product_names["en"]:
            product_names = validated_product_names
            log_info(f"Using validated product names: {json.dumps(product_names, ensure_ascii=False)}")

        if validated_category_names:
            category_names = validated_category_names
            log_info(f"Using validated category names: {category_names}")

        # Bước 3: Trích xuất các bộ lọc (filters)
        filters = _extract_filters(question)

        # Bước 4: Kiểm tra xem có phải là truy vấn về cửa hàng hoặc đơn hàng không
        is_store_query = any(keyword in question.lower() for keyword in INTENT_KEYWORDS[INTENT_TYPES["STORE_INFO"]])
        is_order_query = any(keyword in question.lower() for keyword in INTENT_KEYWORDS[INTENT_TYPES["ORDER_INFO"]]) or \
                         any(keyword in question.lower() for keyword in INTENT_KEYWORDS[INTENT_TYPES["ORDER_HISTORY"]])

        # Bước 5: Tạo intent_text dựa trên thông tin đã trích xuất
        # Nếu có tên sản phẩm hoặc danh mục, tạo intent_text mà không cần gọi LLM
        intent_text = ""
        should_call_llm = True

        # Kiểm tra xem có phải là truy vấn về danh mục không
        is_category_query = False
        if category_names:
            category_keywords = [
                "danh mục", "category", "loại", "nhóm", "type", "group",
                "sản phẩm trong", "products in", "thuộc về", "belongs to",
                "có những gì", "what are", "có những sản phẩm nào", "what products"
            ]
            is_category_query = any(keyword in question.lower() for keyword in category_keywords)
            log_info(f"Is category query: {is_category_query}")

        if is_category_query and category_names:
            # Tạo intent_text cho truy vấn về danh mục
            intent_text = f"Người dùng muốn biết danh mục {category_names[0]} có những sản phẩm gì."
            should_call_llm = False

        elif product_names["vi"] or product_names["en"]:
            # Lấy tên sản phẩm dài nhất (thường là tên đầy đủ nhất)
            all_product_names = product_names["vi"] + product_names["en"]
            if all_product_names:
                longest_product_name = max(all_product_names, key=len)
                intent_text = f"Người dùng muốn biết thông tin về {longest_product_name}."
                should_call_llm = False

        elif category_names and not is_category_query:
            # Lấy tên danh mục đầu tiên
            intent_text = f"Người dùng muốn biết thông tin về danh mục {category_names[0]}."
            should_call_llm = False

        elif is_store_query:
            intent_text = "Người dùng muốn biết thông tin về cửa hàng."
            should_call_llm = False

        elif is_order_query:
            intent_text = "Người dùng muốn biết thông tin về đơn hàng của họ."
            should_call_llm = False

        # Nếu không thể tạo intent_text từ thông tin đã trích xuất, gọi LLM
        if should_call_llm:
            intent_text = _get_intent_text_from_llm(question, context)

        # Tạo kết quả cuối cùng
        result = {
            "intent_type": intent_type,
            "intent_text": intent_text,
            "entities": [],  # Sẽ được cập nhật sau nếu cần
            "product_names": product_names,
            "category_names": category_names,
            "filters": filters,
            "is_store_query": is_store_query,
            "is_order_query": is_order_query,
            "confidence": confidence
        }

        log_info(f"🧠 Enhanced intent inference result: {json.dumps(result, ensure_ascii=False)}")
        return result

    except Exception as e:
        log_error(f"Error in enhanced intent inference: {str(e)}")
        return default_intent

def _classify_intent_by_keywords(question: str) -> Tuple[str, float]:
    """
    Phân loại ý định dựa trên từ khóa trong câu hỏi

    Args:
        question (str): Câu hỏi của người dùng

    Returns:
        Tuple[str, float]: Loại ý định và độ tin cậy
    """
    question_lower = question.lower()

    # Đếm số từ khóa khớp cho mỗi loại ý định
    intent_scores = {}
    for intent_type, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for keyword in keywords if keyword in question_lower)
        intent_scores[intent_type] = score

    # Tìm loại ý định có điểm cao nhất
    max_score = max(intent_scores.values()) if intent_scores else 0
    if max_score == 0:
        return INTENT_TYPES["GENERAL_QUERY"], 0.5

    # Tìm tất cả các loại ý định có điểm cao nhất
    top_intents = [intent for intent, score in intent_scores.items() if score == max_score]

    # Ưu tiên theo thứ tự: sản phẩm > danh mục > cửa hàng > đơn hàng > chung
    priority_order = [
        INTENT_TYPES["PRODUCT_SEARCH"], INTENT_TYPES["PRODUCT_INFO"],
        INTENT_TYPES["CATEGORY_SEARCH"], INTENT_TYPES["CATEGORY_INFO"],
        INTENT_TYPES["RECOMMENDATION"],
        INTENT_TYPES["STORE_INFO"],
        INTENT_TYPES["ORDER_INFO"], INTENT_TYPES["ORDER_HISTORY"],
        INTENT_TYPES["GREETING"],
        INTENT_TYPES["GENERAL_QUERY"]
    ]

    for intent in priority_order:
        if intent in top_intents:
            # Tính độ tin cậy dựa trên số từ khóa khớp
            confidence = min(0.5 + (max_score * 0.1), 0.9)  # Giới hạn trong khoảng 0.5-0.9
            return intent, confidence

    return INTENT_TYPES["GENERAL_QUERY"], 0.5

def _extract_product_names(question: str) -> Dict[str, List[str]]:
    """
    Trích xuất tên sản phẩm từ câu hỏi, bao gồm cả tên tiếng Việt và tiếng Anh
    Đã được cải tiến để trích xuất tên sản phẩm đầy đủ và chính xác hơn

    Args:
        question (str): Câu hỏi của người dùng

    Returns:
        Dict[str, List[str]]: Danh sách tên sản phẩm theo ngôn ngữ
    """
    result = {
        "vi": [],
        "en": []
    }

    # Chuẩn bị câu hỏi để tìm kiếm
    question_lower = question.lower()

    # Bước 0: Trích xuất tên sản phẩm từ các từ khóa chỉ sản phẩm
    product_indicators = ["về", "mô tả", "thông tin", "giới thiệu", "cho tôi biết về", "cho tôi", "tôi muốn"]

    for indicator in product_indicators:
        if indicator in question_lower:
            # Tìm vị trí của từ khóa chỉ sản phẩm
            pos = question_lower.find(indicator) + len(indicator)
            if pos < len(question_lower):
                # Lấy phần còn lại của câu làm tên sản phẩm tiềm năng
                remaining_text = question_lower[pos:].strip()
                if remaining_text:
                    # Kiểm tra xem phần còn lại có phải là tên sản phẩm không
                    # Nếu có từ khóa chỉ sản phẩm khác, cắt tại đó
                    for other_indicator in product_indicators:
                        if other_indicator in remaining_text:
                            remaining_text = remaining_text.split(other_indicator)[0].strip()

                    # Thêm vào danh sách tên sản phẩm tiềm năng
                    potential_product = remaining_text

                    # Xác định ngôn ngữ của tên sản phẩm
                    if any(char in "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ" for char in potential_product):
                        if potential_product not in result["vi"]:
                            result["vi"].append(potential_product)
                    else:
                        if potential_product not in result["en"]:
                            result["en"].append(potential_product)

                    # Nếu đã tìm thấy tên sản phẩm, không cần tìm tiếp
                    if result["vi"] or result["en"]:
                        break

    # Bước 1: Tìm kiếm các cụm từ hoàn chỉnh
    # Danh sách các cụm từ cụ thể để tìm kiếm
    specific_product_patterns = [
        # Cà phê
        (r"cà phê\s+(?:sữa|đen|đá|nóng|phin|espresso|latte|mocha|americano|cappuccino)(?:\s+(?:đá|nóng|ít đường|không đường|ít sữa))*", "vi"),
        (r"(?:brewed|iced)\s+coffee(?:\s+with\s+(?:milk|sugar|cream))?", "en"),
        (r"(?:caffè|caffe)\s+(?:latte|mocha|americano)", "en"),
        (r"(?:vanilla|caramel)\s+latte", "en"),
        (r"(?:cappuccino|espresso|macchiato)", "en"),
        (r"(?:white\s+chocolate\s+mocha)", "en"),

        # Trà
        (r"trà\s+(?:xanh|đen|sữa|đào|vải|chanh|hoa lài|ô long|matcha)(?:\s+(?:đá|nóng|ít đường|không đường))*", "vi"),
        (r"(?:green|black|oolong|jasmine|earl grey|chai)\s+tea", "en"),
        (r"(?:tazo\s+chai|tazo\s+green)\s+tea\s+latte", "en"),
        (r"(?:shaken\s+iced\s+tazo)\s+tea(?:\s+lemonade)?", "en"),
        (r"shaken\s+iced\s+tea", "en"),

        # Sinh tố
        (r"sinh tố\s+(?:xoài|dâu|chuối|bơ|dừa|việt quất|cam)(?:\s+(?:sữa chua|sữa|đá|ít đường))*", "vi"),
        (r"(?:banana\s+chocolate|orange\s+mango\s+banana|strawberry\s+banana)\s+smoothie", "en"),
        (r"(?:mango|strawberry|banana|avocado|coconut|blueberry|orange)\s+smoothie", "en"),

        # Đá xay
        (r"(?:cà phê|mocha|caramel|java chip|trà xanh)\s+đá xay", "vi"),
        (r"(?:coffee|mocha|caramel|java chip)\s+(?:frappuccino|frappe)", "en"),

        # Trà sữa
        (r"trà sữa\s+(?:trân châu|khoai môn|thái|matcha|socola)(?:\s+(?:đá|nóng|ít đường|không đường))*", "vi"),
        (r"(?:bubble|boba|pearl milk|taro milk|thai milk)\s+tea", "en"),

        # Sô cô la
        (r"sô cô la\s+(?:nóng|đá)", "vi"),
        (r"hot\s+chocolate", "en")
    ]

    # Tìm kiếm các cụm từ cụ thể
    for pattern, lang in specific_product_patterns:
        matches = re.findall(pattern, question_lower)
        for match in matches:
            if match and match not in result[lang]:
                result[lang].append(match)

    # Bước 2: Nếu không tìm thấy cụm từ cụ thể, tìm kiếm từ khóa chung
    if not result["vi"] and not result["en"]:
        # Tìm kiếm tên sản phẩm tiếng Việt
        for beverage_type, keywords in VIETNAMESE_BEVERAGE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question_lower and beverage_type not in result["vi"]:
                    result["vi"].append(beverage_type)
                    break

        # Tìm kiếm tên sản phẩm tiếng Anh
        for beverage_type, keywords in ENGLISH_BEVERAGE_KEYWORDS.items():
            for keyword in keywords:
                if keyword in question_lower and beverage_type not in result["en"]:
                    result["en"].append(beverage_type)
                    break

    # Bước 3: Kiểm tra các sản phẩm cụ thể từ cơ sở dữ liệu
    specific_products = {
        "banana chocolate smoothie": "sinh tố chuối sô cô la",
        "orange mango banana smoothie": "sinh tố cam xoài chuối",
        "strawberry banana smoothie": "sinh tố dâu chuối",
        "brewed coffee": "cà phê phin",
        "caffè latte": "cà phê sữa",
        "caffè mocha": "cà phê mocha",
        "vanilla latte": "cà phê sữa vani",
        "caffè americano": "cà phê americano",
        "cappuccino": "cà phê cappuccino",
        "espresso": "cà phê espresso",
        "caramel macchiato": "cà phê caramel macchiato",
        "white chocolate mocha": "cà phê mocha sô cô la trắng",
        "hot chocolate": "sô cô la nóng",
        "tazo chai tea latte": "trà chai sữa",
        "tazo green tea latte": "trà xanh sữa",
        "shaken iced tea": "trà đá lắc"
    }

    for en_name, vi_name in specific_products.items():
        if en_name in question_lower and en_name not in result["en"]:
            result["en"].append(en_name)
        if vi_name in question_lower and vi_name not in result["vi"]:
            result["vi"].append(vi_name)

    # Bước 4: Loại bỏ các tên sản phẩm trùng lặp hoặc là phần con của tên khác
    # Ví dụ: nếu có "cà phê sữa đá" thì không cần "cà phê", "cà phê sữa", "cà phê đá"
    result["vi"] = _remove_redundant_product_names(result["vi"])
    result["en"] = _remove_redundant_product_names(result["en"])

    return result

def _remove_redundant_product_names(product_names: List[str]) -> List[str]:
    """
    Loại bỏ các tên sản phẩm trùng lặp hoặc là phần con của tên khác

    Args:
        product_names (List[str]): Danh sách tên sản phẩm

    Returns:
        List[str]: Danh sách tên sản phẩm đã được lọc
    """
    if not product_names:
        return []

    # Sắp xếp tên sản phẩm theo độ dài giảm dần
    sorted_names = sorted(product_names, key=len, reverse=True)

    # Danh sách kết quả
    result = []

    # Thêm tên sản phẩm dài nhất vào kết quả
    result.append(sorted_names[0])

    # Kiểm tra các tên sản phẩm còn lại
    for name in sorted_names[1:]:
        # Kiểm tra xem tên sản phẩm có là phần con của tên nào đó trong kết quả không
        is_substring = False
        for existing_name in result:
            if name in existing_name:
                is_substring = True
                break

        # Nếu không phải là phần con, thêm vào kết quả
        if not is_substring:
            result.append(name)

    return result

def _extract_category_names(question: str) -> List[str]:
    """
    Trích xuất tên danh mục từ câu hỏi
    Đã được cải tiến để trích xuất tên danh mục chính xác hơn và xác thực với Neo4j

    Args:
        question (str): Câu hỏi của người dùng

    Returns:
        List[str]: Danh sách tên danh mục
    """
    # Chuẩn bị câu hỏi để tìm kiếm
    question_lower = question.lower()

    # Tìm kiếm các mẫu danh mục cụ thể
    category_patterns = [
        r"danh mục\s+(.*?)(?:\s+có|$)",
        r"loại\s+(.*?)(?:\s+có|$)",
        r"nhóm\s+(.*?)(?:\s+có|$)",
        r"category\s+(.*?)(?:\s+has|$)"
    ]

    extracted_categories = []
    for pattern in category_patterns:
        matches = re.findall(pattern, question_lower)
        if matches:
            for match in matches:
                if match.strip() and match.strip() not in extracted_categories:
                    extracted_categories.append(match.strip())

    # Nếu tìm thấy danh mục từ mẫu cụ thể, xác thực và trả về
    if extracted_categories:
        # Xác thực các danh mục đã trích xuất
        validated_categories, confidence = DatabaseValidator.extract_category_from_text(question)
        if validated_categories:
            return validated_categories

    # Nếu không tìm thấy từ mẫu cụ thể, tiếp tục với phương pháp từ khóa
    categories = []

    # Ánh xạ từ khóa tiếng Việt sang danh mục trong cơ sở dữ liệu
    category_keywords = {
        "Classic Espresso Drinks": ["cà phê espresso", "cà phê sữa", "cà phê mocha", "cà phê vani", "cà phê americano", "cappuccino", "espresso", "latte", "mocha"],
        "Coffee": ["cà phê phin", "cà phê đen", "cà phê đá", "brewed coffee"],
        "Frappuccino Blended Coffee": ["cà phê đá xay", "coffee frappuccino", "mocha frappuccino", "caramel frappuccino", "java chip frappuccino"],
        "Frappuccino Blended Crème": ["đá xay kem", "kem đá xay", "strawberries & crème", "vanilla bean"],
        "Frappuccino Light Blended Coffee": ["cà phê đá xay ít béo", "coffee light frappuccino", "mocha light frappuccino", "caramel light frappuccino"],
        "Shaken Iced Beverages": ["đồ uống đá lắc", "trà đá lắc", "trà chanh đá lắc", "shaken iced tazo tea", "shaken iced tazo tea lemonade"],
        "Signature Espresso Drinks": ["cà phê đặc biệt", "cà phê caramel macchiato", "cà phê mocha sô cô la trắng", "caramel macchiato", "white chocolate mocha"],
        "Smoothies": ["sinh tố", "sinh tố chuối sô cô la", "sinh tố cam xoài chuối", "sinh tố dâu chuối", "banana chocolate smoothie", "orange mango banana smoothie", "strawberry banana smoothie"],
        "Tazo Tea Drinks": ["trà", "trà chai sữa", "trà xanh sữa", "trà đào", "trà vải", "trà chanh", "tazo chai tea latte", "tazo green tea latte"]
    }

    # Kiểm tra từng danh mục
    for category_name, keywords in category_keywords.items():
        for keyword in keywords:
            if keyword in question_lower:
                # Thêm tên danh mục tiếng Anh
                if category_name not in categories:
                    categories.append(category_name)

                # Thêm tên danh mục tiếng Việt tương ứng
                vi_category_name = _get_vietnamese_category_name(category_name)
                if vi_category_name and vi_category_name not in categories:
                    categories.append(vi_category_name)

                break

    # Nếu không tìm thấy danh mục cụ thể, kiểm tra các từ khóa chung
    if not categories:
        common_keywords = {
            "cà phê": ["Classic Espresso Drinks", "Coffee", "Đồ uống cà phê"],
            "coffee": ["Classic Espresso Drinks", "Coffee", "Đồ uống cà phê"],
            "trà": ["Tazo Tea Drinks", "Đồ uống trà"],
            "tea": ["Tazo Tea Drinks", "Đồ uống trà"],
            "sinh tố": ["Smoothies", "Sinh tố"],
            "smoothie": ["Smoothies", "Sinh tố"],
            "đá xay": ["Frappuccino Blended Coffee", "Frappuccino Blended Crème", "Đồ uống đá xay"],
            "frappuccino": ["Frappuccino Blended Coffee", "Frappuccino Blended Crème", "Đồ uống đá xay"]
        }

        for keyword, category_list in common_keywords.items():
            if keyword in question_lower:
                for category_name in category_list:
                    if category_name not in categories:
                        categories.append(category_name)

    # Xác thực danh mục với Neo4j
    if categories:
        validated_categories = DatabaseValidator.validate_category_names(categories)
        if validated_categories:
            return validated_categories

    return categories

def _get_vietnamese_category_name(category_name: str) -> str:
    """
    Chuyển đổi tên danh mục từ tiếng Anh sang tiếng Việt

    Args:
        category_name (str): Tên danh mục tiếng Anh

    Returns:
        str: Tên danh mục tiếng Việt
    """
    category_mapping = {
        "Classic Espresso Drinks": "Đồ uống cà phê espresso cổ điển",
        "Coffee": "Cà phê",
        "Frappuccino Blended Coffee": "Cà phê đá xay",
        "Frappuccino Blended Crème": "Kem đá xay",
        "Frappuccino Light Blended Coffee": "Cà phê đá xay ít béo",
        "Shaken Iced Beverages": "Đồ uống đá lắc",
        "Signature Espresso Drinks": "Đồ uống cà phê đặc biệt",
        "Smoothies": "Sinh tố",
        "Tazo Tea Drinks": "Đồ uống trà"
    }

    return category_mapping.get(category_name, "")

def _extract_filters(question: str) -> Dict[str, Any]:
    """
    Trích xuất các bộ lọc từ câu hỏi

    Args:
        question (str): Câu hỏi của người dùng

    Returns:
        Dict[str, Any]: Các bộ lọc được trích xuất
    """
    filters = {}
    question_lower = question.lower()

    # Trích xuất thông tin về giá
    price_patterns = [
        r"giá\s+dưới\s+(\d+)[k\s]",
        r"dưới\s+(\d+)[k\s]",
        r"rẻ\s+hơn\s+(\d+)[k\s]",
        r"không\s+quá\s+(\d+)[k\s]",
        r"giá\s+khoảng\s+(\d+)[k\s]",
        r"khoảng\s+(\d+)[k\s]",
        r"(\d+)k",
        r"(\d+)\s+nghìn"
    ]

    for pattern in price_patterns:
        matches = re.search(pattern, question_lower)
        if matches:
            price = int(matches.group(1)) * 1000  # Chuyển đổi k thành đơn vị đồng

            # Xác định loại bộ lọc giá
            if "dưới" in question_lower or "rẻ hơn" in question_lower or "không quá" in question_lower:
                filters["max_price"] = price
            elif "trên" in question_lower or "đắt hơn" in question_lower or "ít nhất" in question_lower:
                filters["min_price"] = price
            else:
                # Nếu không có từ khóa rõ ràng, sử dụng khoảng giá
                filters["price_range"] = {
                    "min": max(0, price - 10000),
                    "max": price + 10000
                }
            break

    # Trích xuất thông tin về đường
    sugar_patterns = {
        "low": [
            r"ít\s+đường", r"ít\s+ngọt", r"không\s+đường", r"không\s+ngọt",
            r"đường\s+thấp", r"giảm\s+đường", r"đường\s+ít"
        ],
        "high": [
            r"nhiều\s+đường", r"ngọt", r"đường\s+nhiều", r"đường\s+cao"
        ]
    }

    for sugar_level, patterns in sugar_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                if sugar_level == "low":
                    filters["low_sugar"] = True
                else:
                    filters["high_sugar"] = True
                break
        if "low_sugar" in filters or "high_sugar" in filters:
            break

    # Trích xuất thông tin về caffeine
    caffeine_patterns = {
        "low": [
            r"không\s+caffeine", r"ít\s+caffeine", r"caffeine\s+thấp",
            r"giảm\s+caffeine", r"không\s+muốn\s+tỉnh\s+táo"
        ],
        "high": [
            r"nhiều\s+caffeine", r"caffeine\s+cao", r"tỉnh\s+táo",
            r"cần\s+tỉnh\s+táo", r"muốn\s+tỉnh\s+táo", r"đang\s+buồn\s+ngủ"
        ]
    }

    for caffeine_level, patterns in caffeine_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                if caffeine_level == "low":
                    filters["low_caffeine"] = True
                else:
                    filters["high_caffeine"] = True
                break
        if "low_caffeine" in filters or "high_caffeine" in filters:
            break

    # Trích xuất thông tin về calo
    calorie_patterns = {
        "low": [
            r"ít\s+calo", r"calo\s+thấp", r"giảm\s+cân", r"đang\s+ăn\s+kiêng",
            r"ít\s+béo", r"không\s+béo", r"đang\s+diet"
        ],
        "high": [
            r"nhiều\s+calo", r"calo\s+cao", r"tăng\s+cân", r"cần\s+năng\s+lượng"
        ]
    }

    for calorie_level, patterns in calorie_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                if calorie_level == "low":
                    filters["low_calories"] = True
                else:
                    filters["high_calories"] = True
                break
        if "low_calories" in filters or "high_calories" in filters:
            break

    # Trích xuất thông tin về kích thước
    size_patterns = {
        "small": [r"nhỏ", r"short", r"size\s+s"],
        "medium": [r"vừa", r"tall", r"size\s+m"],
        "large": [r"lớn", r"grande", r"size\s+l"],
        "extra_large": [r"rất\s+lớn", r"venti", r"size\s+xl"]
    }

    for size, patterns in size_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                filters["size"] = size
                break
        if "size" in filters:
            break

    # Trích xuất thông tin về loại sữa
    milk_patterns = {
        "nonfat": [r"sữa\s+không\s+béo", r"sữa\s+tách\s+béo", r"nonfat\s+milk", r"skim\s+milk"],
        "2%": [r"sữa\s+2%", r"2%\s+milk"],
        "whole": [r"sữa\s+nguyên\s+kem", r"sữa\s+béo", r"whole\s+milk"],
        "soy": [r"sữa\s+đậu\s+nành", r"soymilk", r"soy\s+milk"],
        "almond": [r"sữa\s+hạnh\s+nhân", r"almond\s+milk"],
        "coconut": [r"sữa\s+dừa", r"coconut\s+milk"]
    }

    for milk_type, patterns in milk_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                filters["milk_type"] = milk_type
                break
        if "milk_type" in filters:
            break

    # Trích xuất thông tin về nhiệt độ
    temp_patterns = {
        "hot": [r"nóng", r"hot"],
        "iced": [r"đá", r"lạnh", r"iced", r"cold"]
    }

    for temp, patterns in temp_patterns.items():
        for pattern in patterns:
            if re.search(pattern, question_lower):
                filters["temperature"] = temp
                break
        if "temperature" in filters:
            break

    # Xử lý các trường hợp đặc biệt
    if "sinh tố" in question_lower or "smoothie" in question_lower:
        # Sinh tố thường không có caffeine
        filters["low_caffeine"] = True

        # Kiểm tra các loại trái cây
        fruits = {
            "mango": ["xoài", "mango"],
            "strawberry": ["dâu", "strawberry"],
            "banana": ["chuối", "banana"],
            "orange": ["cam", "orange"],
            "blueberry": ["việt quất", "blueberry"],
            "avocado": ["bơ", "avocado"],
            "coconut": ["dừa", "coconut"]
        }

        for fruit_name, keywords in fruits.items():
            for keyword in keywords:
                if keyword in question_lower:
                    if "fruits" not in filters:
                        filters["fruits"] = []
                    filters["fruits"].append(fruit_name)

    # Xử lý các trường hợp đặc biệt cho cà phê
    if "cà phê" in question_lower or "coffee" in question_lower:
        # Kiểm tra các loại cà phê đặc biệt
        coffee_types = {
            "espresso": ["espresso"],
            "latte": ["latte", "cà phê sữa"],
            "mocha": ["mocha"],
            "americano": ["americano"],
            "cappuccino": ["cappuccino"],
            "macchiato": ["macchiato"]
        }

        for coffee_type, keywords in coffee_types.items():
            for keyword in keywords:
                if keyword in question_lower:
                    filters["coffee_type"] = coffee_type
                    break
            if "coffee_type" in filters:
                break

    return filters

@count_llm_call
def _get_intent_text_from_llm(question: str, context: Optional[Dict[str, Any]] = None) -> str:
    """
    Sử dụng LLM để suy luận ý định chi tiết

    Args:
        question (str): Câu hỏi của người dùng
        context (Dict, optional): Ngữ cảnh bổ sung (thông tin khách hàng, lịch sử chat)

    Returns:
        str: Ý định được suy luận dưới dạng văn bản
    """
    try:
        # Chuẩn bị thông tin ngữ cảnh
        context_info = ""
        if context:
            # Thêm thông tin về khách hàng
            if 'customer' in context:
                customer = context['customer']
                customer_info = f"""
Thông tin khách hàng:
- Tên: {customer.get('name', 'Không xác định')}
- ID: {customer.get('id', 'Không xác định')}
"""
                context_info += customer_info

            # Thêm thông tin về lịch sử đơn hàng
            if 'order_history' in context and context['order_history']:
                orders = context['order_history']
                order_info = "Lịch sử đơn hàng gần đây:\n"
                for i, order in enumerate(orders[:3], 1):  # Chỉ lấy 3 đơn hàng gần nhất
                    order_info += f"- Đơn hàng {i}: {order.get('date', 'Không xác định')}, Tổng tiền: {order.get('total', 'Không xác định')}\n"
                context_info += order_info

            # Thêm thông tin về lịch sử chat
            if 'chat_history' in context and context['chat_history']:
                chat_history = context['chat_history']
                chat_info = "Lịch sử chat gần đây:\n"
                for i, chat in enumerate(chat_history[-3:], 1):  # Chỉ lấy 3 tin nhắn gần nhất
                    chat_info += f"- Người dùng: {chat.get('user_message', '')}\n"
                    chat_info += f"  Hệ thống: {chat.get('system_message', '')}\n"
                context_info += chat_info

        # Tạo prompt để suy luận ý định
        prompt = f"""Bạn là một chuyên gia phân tích ngôn ngữ tự nhiên và chuyên gia về đồ uống. Nhiệm vụ của bạn là phân tích câu hỏi của người dùng và suy luận ý định thực sự của họ.

Câu hỏi của người dùng: "{question}"

{context_info if context_info else ""}

Hãy suy luận ý định thực sự của người dùng dựa trên câu hỏi của họ và ngữ cảnh (nếu có). Ví dụ:
- Nếu người dùng nói "tôi khát" hoặc "trời nóng quá", họ đang tìm kiếm đồ uống giải khát, mát lạnh
- Nếu người dùng nói "tôi mệt" hoặc "buồn ngủ quá", họ đang tìm kiếm đồ uống có caffeine để tỉnh táo
- Nếu người dùng chỉ nói tên đồ uống như "trà sữa", họ đang tìm kiếm thông tin về loại đồ uống đó
- Nếu người dùng nói "thức uống tốt cho sức khỏe", họ đang tìm kiếm đồ uống có giá trị dinh dưỡng cao
- Nếu người dùng hỏi về cửa hàng, họ đang tìm kiếm thông tin về địa điểm, giờ mở cửa
- Nếu người dùng hỏi về đơn hàng, họ đang tìm kiếm thông tin về đơn hàng của họ
- Nếu người dùng hỏi về sản phẩm cụ thể như "sinh tố dâu chuối", họ đang tìm kiếm thông tin về sản phẩm đó
- Nếu người dùng hỏi về đặc điểm sản phẩm như "cà phê nào ít đường nhất", họ đang tìm kiếm sản phẩm phù hợp với yêu cầu cụ thể

Trả lời NGẮN GỌN trong 1-2 câu, chỉ nêu ý định thực sự của người dùng, không thêm bất kỳ giải thích nào khác.

Ý định của người dùng:"""

        # Lưu temperature hiện tại
        current_temp = getattr(gemini_client, '_temperature', 0.0)

        try:
            # Đặt temperature thấp hơn cho việc suy luận ý định
            gemini_client._temperature = 0.1

            # Gọi LLM để suy luận ý định
            response = gemini_client.generate_text(prompt)

            # Trả về ý định được suy luận
            inferred_intent = response.strip()
            log_info(f"🧠 Inferred intent from LLM: {inferred_intent}")

            return inferred_intent

        finally:
            # Khôi phục temperature ban đầu
            gemini_client._temperature = current_temp

    except Exception as e:
        log_error(f"Error getting intent from LLM: {str(e)}")
        return f"Tìm kiếm thông tin về {question}"
