"""
Module xử lý việc dịch tên sản phẩm giữa tiếng Việt và tiếng Anh
Hỗ trợ tìm kiếm sản phẩm bằng cả tên tiếng Việt và tiếng Anh
Đã được tối ưu để giảm số lần gọi LLM
"""
import re
from typing import Dict, List, Any, Optional, Tuple, Set
from functools import lru_cache

from ...utils.logger import log_info, log_error
from ...llm_clients.gemini_client import gemini_client
from ...utils.llm_counter import count_llm_call
from ...utils.vietnamese_to_english_mapping import translate_vietnamese_to_english, translate_english_to_vietnamese

# Cache cho việc dịch tên sản phẩm
TRANSLATION_CACHE = {
    'vi_to_en': {},  # Tiếng Việt sang tiếng Anh
    'en_to_vi': {}   # Tiếng Anh sang tiếng Việt
}

# Bảng ánh xạ tên sản phẩm tiếng Anh sang tiếng Việt
PRODUCT_NAME_EN_TO_VI = {
    # Cà phê
    "brewed coffee": "cà phê phin",
    "caffè latte": "cà phê sữa",
    "caffè mocha": "cà phê mocha",
    "vanilla latte": "cà phê sữa vani",
    "caffè americano": "cà phê americano",
    "cappuccino": "cà phê cappuccino",
    "espresso": "cà phê espresso",
    "skinny latte": "cà phê sữa ít béo",
    "caramel macchiato": "cà phê caramel macchiato",
    "white chocolate mocha": "cà phê mocha sô cô la trắng",
    "hot chocolate": "sô cô la nóng",
    "iced brewed coffee": "cà phê phin đá",
    "iced brewed coffee with milk": "cà phê phin sữa đá",

    # Đá xay (Frappuccino)
    "coffee frappuccino": "cà phê đá xay",
    "mocha frappuccino": "mocha đá xay",
    "caramel frappuccino": "caramel đá xay",
    "java chip frappuccino": "java chip đá xay",
    "coffee light frappuccino": "cà phê đá xay ít béo",
    "mocha light frappuccino": "mocha đá xay ít béo",
    "caramel light frappuccino": "caramel đá xay ít béo",
    "frappuccino": "đá xay",
    "frappe": "đá xay",

    # Sinh tố (Smoothie)
    "banana chocolate smoothie": "sinh tố chuối sô cô la",
    "orange mango banana smoothie": "sinh tố cam xoài chuối",
    "strawberry banana smoothie": "sinh tố dâu chuối",
    "smoothie": "sinh tố",

    # Trà (Tea)
    "tazo chai tea latte": "trà chai sữa",
    "tazo green tea latte": "trà xanh sữa",
    "shaken iced tazo tea": "trà đá lắc",
    "shaken iced tazo tea lemonade": "trà chanh đá lắc",
    "tea": "trà",
    "green tea": "trà xanh",
    "black tea": "trà đen",
    "oolong tea": "trà ô long",
    "jasmine tea": "trà hoa lài",
    "earl grey": "trà earl grey",
    "chai tea": "trà chai",
    "matcha": "trà xanh matcha",
    "herbal tea": "trà thảo mộc",

    # Trà sữa
    "milk tea": "trà sữa",
    "bubble tea": "trà sữa trân châu",
    "boba tea": "trà sữa trân châu",
    "pearl milk tea": "trà sữa trân châu",
    "taro milk tea": "trà sữa khoai môn",
    "thai milk tea": "trà sữa thái",

    # Đồ uống khác
    "caramel apple spice": "táo caramel gia vị",
    "strawberries & crème": "kem dâu",
    "vanilla bean": "kem vani",

    # Từ khóa chung
    "coffee": "cà phê",
    "espresso": "cà phê espresso",
    "americano": "cà phê americano",
    "latte": "cà phê sữa",
    "cappuccino": "cà phê cappuccino",
    "mocha": "cà phê mocha",
    "macchiato": "cà phê macchiato",
    "flat white": "cà phê flat white",
    "cold brew": "cà phê ủ lạnh",
    "iced coffee": "cà phê đá",
    "vietnamese coffee": "cà phê việt nam",

    # Nước ép
    "juice": "nước ép",
    "orange juice": "nước cam",
    "apple juice": "nước táo",
    "watermelon juice": "nước dưa hấu",
    "pineapple juice": "nước dứa",
    "carrot juice": "nước ép cà rốt",
    "mixed juice": "nước ép hỗn hợp",

    # Soda
    "soda": "soda",
    "sparkling water": "nước có ga",
    "lemon soda": "soda chanh",
    "strawberry soda": "soda dâu",
    "peach soda": "soda đào",
    "passion fruit soda": "soda chanh dây"
}

# Bảng ánh xạ tên sản phẩm tiếng Việt sang tiếng Anh
PRODUCT_NAME_VI_TO_EN = {v: k for k, v in PRODUCT_NAME_EN_TO_VI.items()}

# Bổ sung thêm một số tên sản phẩm tiếng Việt phổ biến
PRODUCT_NAME_VI_TO_EN.update({
    "cà phê đen": "black coffee",
    "cà phê sữa đá": "iced milk coffee",
    "bạc xỉu": "vietnamese white coffee",
    "trà đào": "peach tea",
    "trà vải": "lychee tea",
    "trà chanh": "lemon tea",
    "trà sữa truyền thống": "traditional milk tea",
    "trà sữa matcha": "matcha milk tea",
    "trà sữa socola": "chocolate milk tea",
    "sinh tố việt quất": "blueberry smoothie",
    "sinh tố dừa": "coconut smoothie",
    "nước ép cam": "orange juice",
    "nước ép táo": "apple juice",
    "nước ép dứa": "pineapple juice",
    "đá xay cà phê": "coffee frappe",
    "đá xay trà xanh": "green tea frappe",
    "soda chanh": "lemon soda"
})

def translate_product_name(product_name: str, target_language: str = "vi") -> str:
    """
    Dịch tên sản phẩm sang ngôn ngữ đích
    Sử dụng cache để tránh dịch lại các tên đã dịch trước đó

    Args:
        product_name (str): Tên sản phẩm cần dịch
        target_language (str): Ngôn ngữ đích ("vi" hoặc "en")

    Returns:
        str: Tên sản phẩm đã được dịch
    """
    if not product_name:
        return ""

    product_name = product_name.lower().strip()

    # Kiểm tra cache trước
    cache_key = 'en_to_vi' if target_language == "vi" else 'vi_to_en'
    if product_name in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for '{product_name}' -> '{TRANSLATION_CACHE[cache_key][product_name]}'")
        return TRANSLATION_CACHE[cache_key][product_name]

    result = None

    if target_language == "vi":
        # Dịch từ tiếng Anh sang tiếng Việt
        if product_name in PRODUCT_NAME_EN_TO_VI:
            result = PRODUCT_NAME_EN_TO_VI[product_name]
        else:
            # Tìm kiếm khớp chính xác trước
            for en_name, vi_name in PRODUCT_NAME_EN_TO_VI.items():
                if en_name == product_name:
                    result = vi_name
                    break

            # Nếu không tìm thấy khớp chính xác, tìm kiếm khớp một phần
            if not result:
                for en_name, vi_name in PRODUCT_NAME_EN_TO_VI.items():
                    # Chỉ khớp nếu từ khóa là một phần đáng kể của tên sản phẩm
                    if (en_name in product_name and len(en_name) >= 4) or (product_name in en_name and len(product_name) >= 4):
                        result = vi_name
                        break
    else:
        # Dịch từ tiếng Việt sang tiếng Anh
        if product_name in PRODUCT_NAME_VI_TO_EN:
            result = PRODUCT_NAME_VI_TO_EN[product_name]
        else:
            # Tìm kiếm khớp chính xác trước
            for vi_name, en_name in PRODUCT_NAME_VI_TO_EN.items():
                if vi_name == product_name:
                    result = en_name
                    break

            # Nếu không tìm thấy khớp chính xác, tìm kiếm khớp một phần
            if not result:
                for vi_name, en_name in PRODUCT_NAME_VI_TO_EN.items():
                    # Chỉ khớp nếu từ khóa là một phần đáng kể của tên sản phẩm
                    if (vi_name in product_name and len(vi_name) >= 4) or (product_name in vi_name and len(product_name) >= 4):
                        result = en_name
                        break

    # Nếu không tìm thấy trong bảng ánh xạ, sử dụng LLM để dịch
    if not result:
        result = _translate_with_llm(product_name, target_language)

    # Lưu vào cache
    TRANSLATION_CACHE[cache_key][product_name] = result

    return result

def get_all_product_name_variations(product_name: str) -> Set[str]:
    """
    Lấy tất cả các biến thể của tên sản phẩm (cả tiếng Việt và tiếng Anh)
    Đã được tối ưu để giảm số lần gọi LLM

    Args:
        product_name (str): Tên sản phẩm gốc

    Returns:
        Set[str]: Tập hợp các biến thể của tên sản phẩm
    """
    if not product_name:
        return set()

    # Kiểm tra cache
    cache_key = 'variations'
    if not hasattr(TRANSLATION_CACHE, cache_key):
        TRANSLATION_CACHE[cache_key] = {}

    product_name_lower = product_name.lower().strip()

    # Kiểm tra cache trước
    if product_name_lower in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for variations of '{product_name_lower}'")
        return TRANSLATION_CACHE[cache_key][product_name_lower]

    variations = {product_name_lower}

    # Xác định ngôn ngữ của tên sản phẩm
    is_vietnamese = any(char in "àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ" for char in product_name_lower)

    # Thêm bản dịch sang ngôn ngữ khác
    if is_vietnamese:
        # Dịch từ tiếng Việt sang tiếng Anh
        en_translation = translate_product_name(product_name_lower, "en")
        if en_translation != product_name_lower:
            variations.add(en_translation)
    else:
        # Dịch từ tiếng Anh sang tiếng Việt
        vi_translation = translate_product_name(product_name_lower, "vi")
        if vi_translation != product_name_lower:
            variations.add(vi_translation)

    # Thêm các biến thể phổ biến (chỉ thêm tối đa 3 biến thể)
    common_variations = _generate_common_variations(product_name_lower)
    for variation in common_variations[:3]:
        variations.add(variation)

    # Lưu vào cache
    TRANSLATION_CACHE[cache_key][product_name_lower] = variations

    return variations

def enhance_product_search_query(query: str) -> str:
    """
    Tăng cường câu truy vấn tìm kiếm sản phẩm bằng cách thêm các biến thể tên sản phẩm
    Đã được tối ưu để giảm số lần gọi LLM và tập trung vào các biến thể có ý nghĩa

    Args:
        query (str): Câu truy vấn gốc

    Returns:
        str: Câu truy vấn đã được tăng cường
    """
    # Kiểm tra cache
    cache_key = 'enhanced_queries'
    if not hasattr(TRANSLATION_CACHE, cache_key):
        TRANSLATION_CACHE[cache_key] = {}

    # Kiểm tra cache trước
    if query in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for enhanced query: '{query}'")
        return TRANSLATION_CACHE[cache_key][query]

    # Tìm các tên sản phẩm trong câu truy vấn
    product_names = _extract_product_names_from_query(query)

    if not product_names:
        return query

    # Tạo câu truy vấn mới với các biến thể tên sản phẩm
    enhanced_query = query

    for product_name in product_names:
        # Lấy tối đa 3 biến thể cho mỗi tên sản phẩm
        variations = list(get_all_product_name_variations(product_name))[:3]

        # Loại bỏ tên sản phẩm gốc khỏi variations
        if product_name in variations:
            variations.remove(product_name)

        # Thêm các biến thể vào câu truy vấn
        if variations:
            variation_str = " OR ".join([f'"{v}"' for v in variations])
            enhanced_query = enhanced_query.replace(product_name, f'({product_name} OR {variation_str})')

    # Lưu vào cache
    TRANSLATION_CACHE[cache_key][query] = enhanced_query

    return enhanced_query

def generate_cypher_product_name_condition(product_name: str) -> str:
    """
    Tạo điều kiện Cypher cho tên sản phẩm, bao gồm cả tên tiếng Việt và tiếng Anh
    Đã được tối ưu để giảm số lần gọi LLM và tạo điều kiện Cypher hiệu quả hơn

    Args:
        product_name (str): Tên sản phẩm

    Returns:
        str: Điều kiện Cypher
    """
    if not product_name:
        return "true"  # Điều kiện luôn đúng nếu không có tên sản phẩm

    # Kiểm tra cache
    cache_key = 'cypher_conditions'
    if not hasattr(TRANSLATION_CACHE, cache_key):
        TRANSLATION_CACHE[cache_key] = {}

    product_name_lower = product_name.lower().strip()

    # Kiểm tra cache trước
    if product_name_lower in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for Cypher condition: '{product_name_lower}'")
        return TRANSLATION_CACHE[cache_key][product_name_lower]

    # Lấy tối đa 3 biến thể cho tên sản phẩm
    variations = list(get_all_product_name_variations(product_name))[:3]

    # Đảm bảo tên sản phẩm gốc có trong variations
    if product_name_lower not in variations:
        variations.insert(0, product_name_lower)

    # Tạo điều kiện Cypher
    conditions = []
    for variation in variations:
        # Sử dụng regex matching (=~) thay vì CONTAINS
        # Thêm ký tự escape cho các ký tự đặc biệt trong regex
        escaped_variation = re.escape(variation)
        conditions.append(f'p.name =~ "(?i).*{escaped_variation}.*"')

    cypher_condition = "(" + " OR ".join(conditions) + ")"

    # Lưu vào cache
    TRANSLATION_CACHE[cache_key][product_name_lower] = cypher_condition

    return cypher_condition

@count_llm_call
def _translate_with_llm(text: str, target_language: str = "vi") -> str:
    """
    Sử dụng LLM để dịch văn bản
    Đã được tối ưu để giảm số lần gọi LLM

    Args:
        text (str): Văn bản cần dịch
        target_language (str): Ngôn ngữ đích ("vi" hoặc "en")

    Returns:
        str: Văn bản đã được dịch
    """
    if not text:
        return ""

    text = text.lower().strip()

    # Kiểm tra cache trước
    cache_key = 'en_to_vi' if target_language == "vi" else 'vi_to_en'
    if text in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for translation '{text}' -> '{TRANSLATION_CACHE[cache_key][text]}'")
        return TRANSLATION_CACHE[cache_key][text]

    # Kiểm tra bảng ánh xạ trước khi gọi LLM
    if target_language == "vi" and text in PRODUCT_NAME_EN_TO_VI:
        translation = PRODUCT_NAME_EN_TO_VI[text]
        TRANSLATION_CACHE[cache_key][text] = translation
        return translation
    elif target_language == "en" and text in PRODUCT_NAME_VI_TO_EN:
        translation = PRODUCT_NAME_VI_TO_EN[text]
        TRANSLATION_CACHE[cache_key][text] = translation
        return translation

    # Kiểm tra xem có thể tìm thấy một phần trong bảng ánh xạ không
    if target_language == "vi":
        for en_name, vi_name in PRODUCT_NAME_EN_TO_VI.items():
            if (en_name in text and len(en_name) >= 4) or (text in en_name and len(text) >= 4):
                TRANSLATION_CACHE[cache_key][text] = vi_name
                return vi_name
    else:
        for vi_name, en_name in PRODUCT_NAME_VI_TO_EN.items():
            if (vi_name in text and len(vi_name) >= 4) or (text in vi_name and len(text) >= 4):
                TRANSLATION_CACHE[cache_key][text] = en_name
                return en_name

    # Nếu không tìm thấy trong bảng ánh xạ, sử dụng LLM để dịch
    try:
        language = "Vietnamese" if target_language == "vi" else "English"

        prompt = f"""Translate the following beverage name to {language}. Keep it concise and natural:

        {text}

        Only return the translated name, nothing else."""

        # Lưu temperature hiện tại
        current_temp = getattr(gemini_client, '_temperature', 0.0)

        try:
            # Đặt temperature thấp cho việc dịch
            gemini_client._temperature = 0.1

            # Gọi LLM để dịch
            response = gemini_client.generate_text(prompt)

            # Trả về kết quả dịch
            translation = response.strip()
            log_info(f"🧠 Translated '{text}' to '{translation}' using LLM")

            # Lưu vào cache
            TRANSLATION_CACHE[cache_key][text] = translation

            # Cập nhật bảng ánh xạ để sử dụng cho lần sau
            if target_language == "vi":
                PRODUCT_NAME_EN_TO_VI[text] = translation
            else:
                PRODUCT_NAME_VI_TO_EN[text] = translation

            return translation

        finally:
            # Khôi phục temperature ban đầu
            gemini_client._temperature = current_temp

    except Exception as e:
        log_error(f"Error translating with LLM: {str(e)}")
        return text

def _generate_common_variations(product_name: str) -> List[str]:
    """
    Tạo các biến thể phổ biến của tên sản phẩm
    Đã được tối ưu để tạo ít biến thể hơn và tập trung vào các biến thể có ý nghĩa

    Args:
        product_name (str): Tên sản phẩm gốc

    Returns:
        List[str]: Danh sách các biến thể
    """
    variations = []
    product_name_lower = product_name.lower()

    # Bảng ánh xạ các tiền tố và hậu tố phổ biến
    common_prefixes = {
        "cà phê": ["espresso", "latte", "cappuccino", "americano", "mocha", "macchiato"],
        "trà": ["green tea", "black tea", "oolong tea", "jasmine tea", "earl grey", "chai tea"],
        "sinh tố": ["smoothie"],
        "nước ép": ["juice"],
        "đá xay": ["frappuccino", "frappe"],
        "trà sữa": ["milk tea", "bubble tea", "boba tea"]
    }

    common_suffixes = {
        "đá": ["iced"],
        "nóng": ["hot"],
        "ít đường": ["less sugar", "low sugar"],
        "không đường": ["no sugar", "sugar-free"],
        "sữa": ["milk", "with milk"]
    }

    # Xử lý các tiền tố
    for vi_prefix, en_prefixes in common_prefixes.items():
        # Nếu tên sản phẩm bắt đầu bằng tiền tố tiếng Việt, thêm phiên bản không có tiền tố
        if product_name_lower.startswith(vi_prefix + " "):
            suffix = product_name_lower[len(vi_prefix) + 1:]
            if len(suffix) >= 3:  # Chỉ thêm nếu phần còn lại đủ dài
                variations.append(suffix)

        # Nếu tên sản phẩm bắt đầu bằng tiền tố tiếng Anh, thêm phiên bản với tiền tố tiếng Việt
        for en_prefix in en_prefixes:
            if product_name_lower.startswith(en_prefix + " "):
                suffix = product_name_lower[len(en_prefix) + 1:]
                if len(suffix) >= 3:  # Chỉ thêm nếu phần còn lại đủ dài
                    variations.append(vi_prefix + " " + suffix)

    # Xử lý các hậu tố
    for vi_suffix, en_suffixes in common_suffixes.items():
        # Nếu tên sản phẩm kết thúc bằng hậu tố tiếng Việt, thêm phiên bản không có hậu tố
        if product_name_lower.endswith(" " + vi_suffix):
            prefix = product_name_lower[:-len(vi_suffix) - 1]
            if len(prefix) >= 3:  # Chỉ thêm nếu phần còn lại đủ dài
                variations.append(prefix)

        # Nếu tên sản phẩm kết thúc bằng hậu tố tiếng Anh, thêm phiên bản với hậu tố tiếng Việt
        for en_suffix in en_suffixes:
            if product_name_lower.endswith(" " + en_suffix):
                prefix = product_name_lower[:-len(en_suffix) - 1]
                if len(prefix) >= 3:  # Chỉ thêm nếu phần còn lại đủ dài
                    variations.append(prefix + " " + vi_suffix)

    # Xử lý các trường hợp đặc biệt
    special_cases = {
        "cà phê sữa đá": ["iced milk coffee", "iced latte", "cà phê sữa", "cà phê đá"],
        "cà phê đen đá": ["iced black coffee", "cà phê đen", "cà phê đá"],
        "trà sữa trân châu": ["bubble milk tea", "boba milk tea", "pearl milk tea", "trà sữa"],
        "sinh tố xoài": ["mango smoothie", "sinh tố"],
        "nước cam": ["orange juice", "nước ép cam"]
    }

    # Thêm các biến thể đặc biệt nếu tên sản phẩm khớp
    for case, case_variations in special_cases.items():
        if product_name_lower == case:
            variations.extend(case_variations)
            break

    # Loại bỏ các biến thể trùng lặp và tên gốc
    unique_variations = []
    for variation in variations:
        if variation != product_name_lower and variation not in unique_variations:
            unique_variations.append(variation)

    return unique_variations

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

def _extract_product_names_from_query(query: str) -> List[str]:
    """
    Trích xuất tên sản phẩm từ câu truy vấn
    Đã được tối ưu để trích xuất cụm từ hoàn chỉnh và giảm số lần gọi LLM

    Args:
        query (str): Câu truy vấn

    Returns:
        List[str]: Danh sách tên sản phẩm
    """
    if not query:
        return []

    # Kiểm tra cache
    cache_key = 'extracted_products'
    if not hasattr(TRANSLATION_CACHE, cache_key):
        TRANSLATION_CACHE[cache_key] = {}

    query_lower = query.lower().strip()

    # Kiểm tra cache trước
    if query_lower in TRANSLATION_CACHE[cache_key]:
        log_info(f"🔄 Cache hit for extracted products from: '{query_lower}'")
        return TRANSLATION_CACHE[cache_key][query_lower]

    product_names = []

    # Bước 1: Tìm kiếm các cụm từ hoàn chỉnh trước
    # Danh sách các cụm từ cụ thể để tìm kiếm
    specific_product_patterns = [
        # Cà phê
        r"cà phê\s+(?:sữa|đen|đá|nóng|phin|espresso|latte|mocha|americano|cappuccino)(?:\s+(?:đá|nóng|ít đường|không đường|ít sữa))*",
        r"(?:brewed|iced)\s+coffee(?:\s+with\s+(?:milk|sugar|cream))?",
        r"(?:caffè|caffe)\s+(?:latte|mocha|americano)",
        r"(?:vanilla|caramel)\s+latte",
        r"(?:cappuccino|espresso|macchiato)",
        r"(?:white\s+chocolate\s+mocha)",

        # Trà
        r"trà\s+(?:xanh|đen|sữa|đào|vải|chanh|hoa lài|ô long|matcha)(?:\s+(?:đá|nóng|ít đường|không đường))*",
        r"(?:green|black|oolong|jasmine|earl grey|chai)\s+tea",
        r"(?:tazo\s+chai|tazo\s+green)\s+tea\s+latte",
        r"(?:shaken\s+iced\s+tazo)\s+tea(?:\s+lemonade)?",

        # Sinh tố
        r"sinh tố\s+(?:xoài|dâu|chuối|bơ|dừa|việt quất|cam)(?:\s+(?:sữa chua|sữa|đá|ít đường))*",
        r"(?:banana\s+chocolate|orange\s+mango\s+banana|strawberry\s+banana)\s+smoothie",
        r"(?:mango|strawberry|banana|avocado|coconut|blueberry|orange)\s+smoothie",

        # Đá xay
        r"(?:cà phê|mocha|caramel|java chip|trà xanh)\s+đá xay",
        r"(?:coffee|mocha|caramel|java chip)\s+(?:frappuccino|frappe)",

        # Trà sữa
        r"trà sữa\s+(?:trân châu|khoai môn|thái|matcha|socola)(?:\s+(?:đá|nóng|ít đường|không đường))*",
        r"(?:bubble|boba|pearl milk|taro milk|thai milk)\s+tea",

        # Sô cô la
        r"sô cô la\s+(?:nóng|đá)",
        r"hot\s+chocolate"
    ]

    # Tìm kiếm các cụm từ cụ thể
    for pattern in specific_product_patterns:
        matches = re.findall(pattern, query_lower)
        for match in matches:
            if match and match not in product_names:
                product_names.append(match)

    # Bước 2: Nếu không tìm thấy cụm từ cụ thể, tìm kiếm từ khóa chung
    if not product_names:
        # Danh sách các từ khóa để tìm tên sản phẩm
        prefixes = ["cà phê", "trà", "trà sữa", "sinh tố", "nước ép", "đá xay", "soda",
                    "coffee", "tea", "milk tea", "smoothie", "juice", "frappe", "frappuccino"]

        for prefix in prefixes:
            # Tìm tên sản phẩm với prefix
            pattern = rf"{prefix}\s+(\w+(?:\s+\w+)*)"
            matches = re.findall(pattern, query_lower)

            if matches:
                for match in matches:
                    product_name = f"{prefix} {match}".strip()
                    if product_name not in product_names:
                        product_names.append(product_name)
            elif prefix in query_lower:
                # Nếu chỉ có prefix mà không có từ sau
                product_names.append(prefix)

    # Bước 3: Loại bỏ các tên sản phẩm trùng lặp hoặc là phần con của tên khác
    if product_names:
        product_names = _remove_redundant_product_names(product_names)

    # Lưu vào cache
    TRANSLATION_CACHE[cache_key][query_lower] = product_names

    return product_names
