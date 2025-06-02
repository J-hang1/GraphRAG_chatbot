"""
Module for statistical queries and aggregation functions for GraphRAG agent
"""
import re
from typing import Dict, List, Any, Optional
from app.utils.logger import log_info, log_error
from ..core.constants import STATISTICAL_PATTERNS, QUERY_TEMPLATES
from ..core.core_functions import extract_comparison_value_from_text

def generate_statistical_cypher_query(intent_data: Dict[str, Any]) -> Optional[str]:
    """
    Tạo truy vấn Cypher cho các câu hỏi thống kê

    Args:
        intent_data: Dữ liệu ý định từ LLM

    Returns:
        Câu truy vấn Cypher hoặc None nếu không thể tạo
    """
    try:
        statistical_type = intent_data.get("statistical_type")
        attributes = intent_data.get("attributes", [])
        comparison_value = intent_data.get("comparison_value")

        # Nếu không có statistical_type, thử suy luận từ filters và product_attributes
        if not statistical_type:
            filters = intent_data.get("filters", {})
            entities = intent_data.get("entities", {})
            product_attributes = entities.get("product_attributes", {})
            constraints = entities.get("constraints", {})

            # Kết hợp filters, product_attributes và constraints
            all_attributes = {**filters, **product_attributes, **constraints}

            if all_attributes:
                # Xử lý trường hợp đặc biệt: constraints có "high" hoặc "low"
                if "high" in constraints and constraints["high"] is True:
                    # Tìm thuộc tính từ product_attributes hoặc attributes_of_interest
                    attributes_of_interest = entities.get("attributes_of_interest", [])
                    if product_attributes:
                        attr_name = list(product_attributes.keys())[0]
                        attributes = [attr_name]
                        statistical_type = "max"
                        comparison_value = None
                        log_info(f"Suy luận từ constraints high=True: {attr_name} cao nhất")
                    elif attributes_of_interest:
                        attr_name = attributes_of_interest[0]
                        attributes = [attr_name]
                        statistical_type = "max"
                        comparison_value = None
                        log_info(f"Suy luận từ constraints high=True và attributes_of_interest: {attr_name} cao nhất")
                elif "low" in constraints and constraints["low"] is True:
                    # Tương tự cho "low"
                    attributes_of_interest = entities.get("attributes_of_interest", [])
                    if product_attributes:
                        attr_name = list(product_attributes.keys())[0]
                        attributes = [attr_name]
                        statistical_type = "min"
                        comparison_value = None
                        log_info(f"Suy luận từ constraints low=True: {attr_name} thấp nhất")
                    elif attributes_of_interest:
                        attr_name = attributes_of_interest[0]
                        attributes = [attr_name]
                        statistical_type = "min"
                        comparison_value = None
                        log_info(f"Suy luận từ constraints low=True và attributes_of_interest: {attr_name} thấp nhất")
                else:
                    # Logic cũ cho các trường hợp khác
                    for attr_name, attr_value in all_attributes.items():
                        if attr_value and attr_value is not True:  # Bỏ qua Boolean True
                            attributes = [attr_name]

                            # Suy luận statistical_type từ giá trị
                            attr_value_lower = str(attr_value).lower()
                            if any(keyword in attr_value_lower for keyword in ["cao nhất", "nhiều nhất", "max", "maximum", "lớn nhất", "đắt nhất", "đắt", "ngọt nhất", "ngọt", "nhiều", "giàu nhất", "giàu"]):
                                statistical_type = "max"
                                comparison_value = None
                                log_info(f"Suy luận câu hỏi thống kê: {attr_name} cao nhất/nhiều nhất/giàu nhất (từ '{attr_value}')")
                            elif any(keyword in attr_value_lower for keyword in ["thấp nhất", "ít nhất", "min", "minimum", "nhỏ nhất", "ít", "rẻ nhất", "rẻ"]):
                                statistical_type = "min"
                                comparison_value = None
                                log_info(f"Suy luận câu hỏi thống kê: {attr_name} thấp nhất/ít nhất/rẻ nhất (từ '{attr_value}')")
                            elif any(keyword in attr_value_lower for keyword in ["lớn hơn", "nhiều hơn", "trên", ">", "greater"]):
                                statistical_type = "greater_than"
                                # Trích xuất số từ chuỗi
                                comparison_value = extract_comparison_value_from_text(attr_value)
                                log_info(f"Suy luận câu hỏi thống kê: {attr_name} > {comparison_value}")
                            elif any(keyword in attr_value_lower for keyword in ["nhỏ hơn", "ít hơn", "dưới", "<", "less"]):
                                statistical_type = "less_than"
                                # Trích xuất số từ chuỗi
                                comparison_value = extract_comparison_value_from_text(attr_value)
                                log_info(f"Suy luận câu hỏi thống kê: {attr_name} < {comparison_value}")
                            else:
                                # Xử lý giá trị Boolean hoặc các trường hợp đặc biệt
                                if attr_value is True or str(attr_value).lower() in ["true", "có", "yes"]:
                                    # Nếu là True, có thể là yêu cầu tìm sản phẩm có thuộc tính này
                                    # Tạm thời bỏ qua vì không rõ yêu cầu cụ thể
                                    log_info(f"Bỏ qua thuộc tính Boolean: {attr_name} = {attr_value}")
                                    continue
                                elif attr_value is False or str(attr_value).lower() in ["false", "không", "no"]:
                                    # Tương tự với False
                                    log_info(f"Bỏ qua thuộc tính Boolean: {attr_name} = {attr_value}")
                                    continue
                                else:
                                    # Thử chuyển đổi thành số để xem có phải giá trị cụ thể không
                                    attr_value_str = str(attr_value).strip()

                                    # Kiểm tra khoảng giá trị (ví dụ: "5-10g", "10-20")
                                    if "-" in attr_value_str and not attr_value_str.startswith("-"):
                                        # Tách khoảng giá trị
                                        parts = attr_value_str.split("-")
                                        if len(parts) == 2:
                                            try:
                                                # Trích xuất số từ mỗi phần
                                                min_val = extract_comparison_value_from_text(parts[0])
                                                max_val = extract_comparison_value_from_text(parts[1])

                                                if min_val is not None and max_val is not None:
                                                    statistical_type = "range"
                                                    comparison_value = [min_val, max_val]
                                                    log_info(f"Suy luận câu hỏi thống kê từ khoảng: {attr_name} trong khoảng {min_val}-{max_val}")
                                                else:
                                                    log_error(f"Không thể trích xuất khoảng giá trị từ: {attr_value}")
                                                    continue
                                            except Exception as e:
                                                log_error(f"Lỗi xử lý khoảng giá trị '{attr_value}': {e}")
                                                continue
                                        else:
                                            log_error(f"Định dạng khoảng giá trị không hợp lệ: {attr_value}")
                                            continue

                                    # Xử lý giá trị phần trăm
                                    elif "%" in attr_value_str:
                                        try:
                                            # Loại bỏ ký hiệu % và chuyển đổi
                                            numeric_value = float(attr_value_str.replace("%", "").replace(",", ""))
                                            statistical_type = "equal"
                                            comparison_value = numeric_value
                                            log_info(f"Suy luận câu hỏi thống kê từ phần trăm: {attr_name} = {comparison_value}%")
                                        except ValueError:
                                            log_error(f"Không thể chuyển đổi giá trị phần trăm: {attr_value}")
                                            continue
                                    else:
                                        # Sử dụng hàm extract_comparison_value_from_text để xử lý giá trị phức tạp
                                        numeric_value = extract_comparison_value_from_text(attr_value_str)
                                        if numeric_value is not None:
                                            statistical_type = "equal"
                                            comparison_value = numeric_value
                                            log_info(f"Suy luận câu hỏi thống kê từ text: {attr_name} = {comparison_value}")
                                        else:
                                            log_error(f"Không thể suy luận statistical_type từ giá trị: {attr_value}")
                                            continue

                            break

        # Nếu vẫn chưa có thông tin, thử trích xuất từ intent_text
        if not statistical_type or not attributes:
            intent_text = intent_data.get("intent_text", "").lower()

            # Tìm pattern "thuộc tính + từ khóa so sánh + số"
            import re

            # ƯU TIÊN: Tìm giá trị số cụ thể TRƯỚC khi loại trừ
            specific_value_patterns = [
                (r"(\d+)\s*g?\s*(đường|sugar)", "sugars_g", "equal"),
                (r"(\d+)\s*mg?\s*(caffeine|cafein)", "caffeine_mg", "equal"),
                (r"(\d+)\s*g?\s*(protein)", "protein_g", "equal"),
                (r"(\d+)\s*(calories|calo)", "calories", "equal"),
                (r"(\d+)\s*(đồng|vnd)\s*(giá|price)", "price", "equal"),
                (r"(giá|price)\s*(\d+)", "price", "equal"),
                (r"khoảng\s*(\d+)\s*g?\s*(đường|sugar)", "sugars_g", "equal"),
                (r"khoảng\s*(\d+)\s*mg?\s*(caffeine|cafein)", "caffeine_mg", "equal"),
                (r"khoảng\s*(\d+)\s*g?\s*(protein)", "protein_g", "equal"),
                (r"khoảng\s*(\d+)\s*(calories|calo)", "calories", "equal")
            ]

            for pattern, attr, stat_type in specific_value_patterns:
                match = re.search(pattern, intent_text)
                if match:
                    attributes = [attr]
                    statistical_type = stat_type
                    comparison_value = float(match.group(1))
                    log_info(f"Trích xuất giá trị cụ thể từ intent_text: {attr} {stat_type} {comparison_value}")
                    break

            # Nếu chưa tìm thấy giá trị cụ thể, mới tìm MAX/MIN
            if not statistical_type:
                # Pattern cho MAX/MIN
                max_min_patterns = [
                (r"(calories|calo|calo)\s+(cao nhất|nhiều nhất|max|maximum)", "calories", "max"),
                (r"(calories|calo|calo)\s+(thấp nhất|ít nhất|min|minimum)", "calories", "min"),
                (r"(giá|price)\s+(cao nhất|đắt nhất|max|maximum)", "price", "max"),
                (r"(giá|price)\s+(thấp nhất|rẻ nhất|min|minimum)", "price", "min"),
                (r"(protein)\s+(cao nhất|nhiều nhất|max|maximum)", "protein_g", "max"),
                (r"(protein)\s+(thấp nhất|ít nhất|min|minimum)", "protein_g", "min"),
                (r"(caffeine|cafein)\s+(cao nhất|nhiều nhất|max|maximum)", "caffeine_mg", "max"),
                (r"(caffeine|cafein)\s+(thấp nhất|ít nhất|min|minimum)", "caffeine_mg", "min"),
                # Thêm pattern cho chất xơ
                (r"(chất xơ|chat xo|fiber|dietary.?fiber|dietary.?fibre)\s+(cao nhất|nhiều nhất|giàu nhất|max|maximum)", "dietary_fibre_g", "max"),
                (r"(chất xơ|chat xo|fiber|dietary.?fiber|dietary.?fibre)\s+(thấp nhất|ít nhất|min|minimum)", "dietary_fibre_g", "min"),
                # Thêm pattern cho vitamin A và vitamin C
                (r"(vitamin\s*a|vitamin_a)\s+(cao nhất|nhiều nhất|giàu nhất|max|maximum)", "vitamin_a", "max"),
                (r"(vitamin\s*a|vitamin_a)\s+(thấp nhất|ít nhất|min|minimum)", "vitamin_a", "min"),
                (r"(vitamin\s*c|vitamin_c)\s+(cao nhất|nhiều nhất|giàu nhất|max|maximum)", "vitamin_c", "max"),
                (r"(vitamin\s*c|vitamin_c)\s+(thấp nhất|ít nhất|min|minimum)", "vitamin_c", "min"),
                # Pattern ngược lại: từ khóa + thuộc tính
                (r"(cao nhất|nhiều nhất|max|maximum).*(calories|calo)", "calories", "max"),
                (r"(thấp nhất|ít nhất|min|minimum).*(calories|calo)", "calories", "min"),
                (r"(cao nhất|đắt nhất|max|maximum).*(giá|price)", "price", "max"),
                (r"(thấp nhất|rẻ nhất|min|minimum).*(giá|price)", "price", "min"),
                (r"(cao nhất|nhiều nhất|max|maximum).*(protein)", "protein_g", "max"),
                (r"(thấp nhất|ít nhất|min|minimum).*(protein)", "protein_g", "min"),
                (r"(cao nhất|nhiều nhất|max|maximum).*(caffeine|cafein)", "caffeine_mg", "max"),
                (r"(thấp nhất|ít nhất|min|minimum).*(caffeine|cafein)", "caffeine_mg", "min"),
                # Pattern ngược lại cho chất xơ
                (r"(giàu|cao nhất|nhiều nhất|max|maximum).*(chất xơ|chat xo|fiber|dietary.?fiber|dietary.?fibre)", "dietary_fibre_g", "max"),
                (r"(ít|thấp nhất|ít nhất|min|minimum).*(chất xơ|chat xo|fiber|dietary.?fiber|dietary.?fibre)", "dietary_fibre_g", "min"),
                # Pattern ngược lại cho vitamin A và vitamin C
                (r"(giàu|cao nhất|nhiều nhất|max|maximum).*(vitamin\s*a|vitamin_a)", "vitamin_a", "max"),
                (r"(ít|thấp nhất|ít nhất|min|minimum).*(vitamin\s*a|vitamin_a)", "vitamin_a", "min"),
                (r"(giàu|cao nhất|nhiều nhất|max|maximum).*(vitamin\s*c|vitamin_c)", "vitamin_c", "max"),
                (r"(ít|thấp nhất|ít nhất|min|minimum).*(vitamin\s*c|vitamin_c)", "vitamin_c", "min")
            ]

            for pattern, attr, stat_type in max_min_patterns:
                match = re.search(pattern, intent_text)
                if match:
                    attributes = [attr]
                    statistical_type = stat_type
                    comparison_value = None
                    log_info(f"Trích xuất từ intent_text: {attr} {stat_type} (từ pattern '{pattern}')")
                    break

            # Nếu chưa tìm thấy, tìm pattern "thuộc tính + từ khóa so sánh + số"
            if not statistical_type:
                patterns = [
                    (r"calo\s+(dưới|nhỏ hơn|<)\s*(\d+)", "calories", "less_than"),
                    (r"calo\s+(trên|lớn hơn|>)\s*(\d+)", "calories", "greater_than"),
                    (r"giá\s+(dưới|nhỏ hơn|<)\s*(\d+)", "price", "less_than"),
                    (r"giá\s+(trên|lớn hơn|>)\s*(\d+)", "price", "greater_than"),
                    (r"caffeine\s+(dưới|nhỏ hơn|<)\s*(\d+)", "caffeine_mg", "less_than"),
                    (r"caffeine\s+(trên|lớn hơn|>)\s*(\d+)", "caffeine_mg", "greater_than"),
                    (r"protein\s+(dưới|nhỏ hơn|<)\s*(\d+)", "protein_g", "less_than"),
                    (r"protein\s+(trên|lớn hơn|>)\s*(\d+)", "protein_g", "greater_than"),
                    (r"đường\s+(dưới|nhỏ hơn|<)\s*(\d+)", "sugars_g", "less_than"),
                    (r"đường\s+(trên|lớn hơn|>)\s*(\d+)", "sugars_g", "greater_than")
                ]

                for pattern, attr, stat_type in patterns:
                    match = re.search(pattern, intent_text)
                    if match:
                        attributes = [attr]
                        statistical_type = stat_type
                        comparison_value = float(match.group(2))
                        log_info(f"Trích xuất từ intent_text: {attr} {stat_type} {comparison_value}")
                        break

        if not statistical_type or not attributes:
            log_error("Thiếu thông tin statistical_type hoặc attributes")
            return None

        # Mapping thuộc tính từ tiếng Việt sang tên trường trong database
        attribute_mapping = {
            "giá": "price",
            "gia": "price",
            "price": "price",
            "calo": "calories",
            "calories": "calories",
            "protein": "protein_g",
            "đường": "sugars_g",
            "duong": "sugars_g",
            "sugar": "sugars_g",
            "sugars": "sugars_g",
            "sweetness": "sugars_g",  # Độ ngọt tương ứng với lượng đường
            "ngọt": "sugars_g",
            "caffeine": "caffeine_mg",
            "cafein": "caffeine_mg",
            "xếp hạng": "sales_rank",
            "xep hang": "sales_rank",
            "sales_rank": "sales_rank",
            # Thêm các thuộc tính khác (chỉ những trường thực sự có trong database)
            "chất xơ": "dietary_fibre_g",
            "chat xo": "dietary_fibre_g",
            "fiber": "dietary_fibre_g",
            "dietary fiber": "dietary_fibre_g",
            "dietary fibre": "dietary_fibre_g",
            "vitamin a": "vitamin_a",
            "vitamin c": "vitamin_c"
        }

        # Chuyển đổi thuộc tính
        db_attributes = []
        for attr in attributes:
            attr_lower = attr.lower().strip()

            # Kiểm tra xem attr đã là tên database field chưa
            if attr_lower in attribute_mapping:
                db_attributes.append(attribute_mapping[attr_lower])
                log_info(f"Mapping thuộc tính: '{attr}' → '{attribute_mapping[attr_lower]}'")
            elif attr_lower in attribute_mapping.values():
                # Nếu attr đã là tên database field (như 'dietary_fibre_g'), sử dụng trực tiếp
                db_attributes.append(attr_lower)
                log_info(f"Sử dụng trực tiếp thuộc tính database: '{attr}' → '{attr_lower}'")
            else:
                log_error(f"Không nhận diện được thuộc tính: {attr}")
                log_info(f"Các thuộc tính hỗ trợ: {list(attribute_mapping.keys())} và {list(attribute_mapping.values())}")
                return None

        if not db_attributes:
            log_error("Không có thuộc tính hợp lệ")
            return None

        # Tạo truy vấn dựa trên loại thống kê
        if statistical_type == "max":
            return _generate_max_query(db_attributes[0])
        elif statistical_type == "min":
            return _generate_min_query(db_attributes[0])
        elif statistical_type == "equal":
            return _generate_equal_query(db_attributes[0], comparison_value)
        elif statistical_type == "greater_than":
            return _generate_greater_than_query(db_attributes[0], comparison_value)
        elif statistical_type == "less_than":
            return _generate_less_than_query(db_attributes[0], comparison_value)
        elif statistical_type == "range":
            return _generate_range_query(db_attributes[0], comparison_value)
        else:
            log_error(f"Không hỗ trợ loại thống kê: {statistical_type}")
            return None

    except Exception as e:
        log_error(f"Lỗi khi tạo truy vấn thống kê: {str(e)}")
        return None

def _generate_max_query(attribute: str) -> str:
    """Tạo truy vấn tìm giá trị cao nhất"""
    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE v.{attribute} IS NOT NULL
    WITH MAX(toFloat(v.{attribute})) as max_value
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE toFloat(v.{attribute}) = max_value
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY v.sales_rank ASC
    LIMIT 10
    """

def _generate_min_query(attribute: str) -> str:
    """Tạo truy vấn tìm giá trị thấp nhất"""
    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE v.{attribute} IS NOT NULL
    WITH MIN(toFloat(v.{attribute})) as min_value
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE toFloat(v.{attribute}) = min_value
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY v.sales_rank ASC
    LIMIT 10
    """

def _generate_equal_query(attribute: str, value: Any) -> str:
    """Tạo truy vấn tìm giá trị bằng"""
    if value is None:
        return None

    # Chuyển đổi giá trị thành số
    try:
        # Chỉ loại bỏ dấu phẩy (phân cách hàng nghìn), KHÔNG loại bỏ dấu chấm thập phân
        value_str = str(value).replace(",", "")
        numeric_value = float(value_str)
        log_info(f"Chuyển đổi giá trị: '{value}' → {numeric_value}")
    except ValueError:
        log_error(f"Không thể chuyển đổi giá trị '{value}' thành số")
        return None

    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE v.{attribute} IS NOT NULL AND toFloat(v.{attribute}) = {numeric_value}
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY v.sales_rank ASC
    LIMIT 20
    """

def _generate_greater_than_query(attribute: str, value: Any) -> str:
    """Tạo truy vấn tìm giá trị lớn hơn"""
    if value is None:
        return None

    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE toFloat(v.{attribute}) > {float(value)}
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY toFloat(v.{attribute}) DESC, v.sales_rank ASC
    LIMIT 20
    """

def _generate_less_than_query(attribute: str, value: Any) -> str:
    """Tạo truy vấn tìm giá trị nhỏ hơn"""
    if value is None:
        return None

    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE toFloat(v.{attribute}) < {float(value)}
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY toFloat(v.{attribute}) ASC, v.sales_rank ASC
    LIMIT 20
    """

def _generate_range_query(attribute: str, value_range: Any) -> str:
    """Tạo truy vấn tìm giá trị trong khoảng"""
    if not value_range or not isinstance(value_range, (list, tuple)) or len(value_range) != 2:
        return None

    min_val, max_val = value_range
    return f"""
    MATCH (v:Variant)-[:PRODUCT_ID]->(p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
    WHERE toFloat(v.{attribute}) >= {float(min_val)} AND toFloat(v.{attribute}) <= {float(max_val)}
    RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
           c.id as category_id, c.name_cat as category_name, c.description as category_description,
           v.id as variant_id, v.name as variant_name, v.`Beverage Option` as beverage_option,
           v.price as price, v.sugars_g as sugars_g, v.caffeine_mg as caffeine_mg,
           v.calories as calories, v.protein_g as protein_g, v.dietary_fibre_g as dietary_fibre_g,
           v.vitamin_a as vitamin_a, v.vitamin_c as vitamin_c, v.sales_rank as sales_rank,
           v.product_id as variant_product_id, v.product_name as variant_product_name,
           v.{attribute} as target_value
    ORDER BY toFloat(v.{attribute}) ASC, v.sales_rank ASC
    LIMIT 20
    """

def is_statistical_query(intent_data: Dict[str, Any]) -> bool:
    """
    Kiểm tra xem có phải là câu hỏi thống kê không

    Args:
        intent_data: Dữ liệu ý định từ LLM

    Returns:
        True nếu là câu hỏi thống kê
    """
    intent = intent_data.get("intent", "").lower()
    intent_text = intent_data.get("intent_text", "").lower()
    statistical_type = intent_data.get("statistical_type")

    # Kiểm tra từ khóa thống kê TRƯỚC khi loại trừ
    statistical_keywords = ["thống kê", "so sánh", "cao nhất", "thấp nhất", "nhiều nhất", "ít nhất", "ít", "rẻ nhất", "rẻ", "đắt nhất", "đắt",
                           "ngọt nhất", "ngọt", "bằng", "lớn hơn", "nhỏ hơn", "dưới", "trên", "trong khoảng", "giá", "=", ">", "<", "nhất"]

    has_statistical_keywords = any(keyword in intent_text for keyword in statistical_keywords)

    # Chỉ loại trừ nếu KHÔNG có từ khóa thống kê
    if not has_statistical_keywords:
        non_statistical_patterns = [
            "1 loại", "một loại", "duy nhất", "chỉ có", "bao nhiêu loại", "có mấy",
            "danh sách", "liệt kê", "tất cả", "những gì", "nào có", "có những"
        ]

        # Nếu câu hỏi chứa các pattern không phải thống kê và KHÔNG có từ khóa thống kê, trả về False
        if any(pattern in intent_text for pattern in non_statistical_patterns):
            log_info(f"Loại trừ câu hỏi không phải thống kê: tìm thấy pattern '{[p for p in non_statistical_patterns if p in intent_text]}' và không có từ khóa thống kê")
            return False
    else:
        log_info(f"Có từ khóa thống kê '{[kw for kw in statistical_keywords if kw in intent_text]}', không loại trừ")

    has_statistical_intent = any(keyword in intent for keyword in statistical_keywords)
    has_statistical_text = has_statistical_keywords  # Đã tính ở trên
    has_statistical_type = statistical_type is not None

    # Kiểm tra xem có filters với giá trị cụ thể không (có thể là câu hỏi thống kê)
    filters = intent_data.get("filters", {})
    has_price_filter = "giá" in filters or "price" in filters

    # Kiểm tra product_attributes và constraints có giá trị cụ thể không
    entities = intent_data.get("entities", {})
    product_attributes = entities.get("product_attributes", {})
    constraints = entities.get("constraints", {})

    # Chỉ coi là có specific attributes nếu chúng liên quan đến thuộc tính số
    valid_attributes = ["giá", "price", "calo", "calories", "protein", "đường", "sugars", "caffeine", "cafein", "sweetness", "ngọt",
                       "vitamin a", "vitamin_a", "vitamin c", "vitamin_c", "chất xơ", "dietary_fibre_g", "fiber"]
    # Kiểm tra có thuộc tính hợp lệ với giá trị số/phần trăm
    def has_numeric_or_percentage_value(attributes_dict):
        for attr_name, attr_value in attributes_dict.items():
            attr_name_lower = attr_name.lower()
            log_info(f"Kiểm tra thuộc tính: '{attr_name}' (lower: '{attr_name_lower}') = '{attr_value}'")

            # Kiểm tra tên thuộc tính có hợp lệ không (không phân biệt hoa thường)
            is_valid_attr = attr_name_lower in [va.lower() for va in valid_attributes]
            log_info(f"Thuộc tính '{attr_name}' hợp lệ: {is_valid_attr}")

            if is_valid_attr and attr_value:
                attr_value_str = str(attr_value).strip()
                log_info(f"Kiểm tra giá trị: '{attr_value_str}'")

                # Kiểm tra giá trị phần trăm
                if "%" in attr_value_str:
                    try:
                        numeric_value = float(attr_value_str.replace("%", "").replace(",", ""))
                        log_info(f"✅ Tìm thấy giá trị phần trăm hợp lệ: {numeric_value}%")
                        return True
                    except ValueError:
                        log_info(f"❌ Không thể chuyển đổi phần trăm: {attr_value_str}")
                        pass

                # Kiểm tra giá trị số
                try:
                    numeric_value = float(attr_value_str.replace(",", ""))
                    log_info(f"✅ Tìm thấy giá trị số hợp lệ: {numeric_value}")
                    return True
                except ValueError:
                    log_info(f"❌ Không thể chuyển đổi số: {attr_value_str}")
                    pass
            else:
                if not is_valid_attr:
                    log_info(f"❌ Thuộc tính '{attr_name}' không hợp lệ")
                if not attr_value:
                    log_info(f"❌ Giá trị rỗng cho thuộc tính '{attr_name}'")

        log_info("❌ Không tìm thấy thuộc tính hợp lệ với giá trị số/phần trăm")
        return False

    has_specific_attributes = (
        any(attr.lower() in [va.lower() for va in valid_attributes] for attr in product_attributes.keys()) or
        any(attr.lower() in [va.lower() for va in valid_attributes] for attr in constraints.keys()) or
        # Kiểm tra trường hợp đặc biệt: có "high"/"low" trong constraints và thuộc tính trong product_attributes
        (("high" in constraints or "low" in constraints) and len(product_attributes) > 0) or
        # Kiểm tra có giá trị số/phần trăm
        has_numeric_or_percentage_value(product_attributes) or
        has_numeric_or_percentage_value(constraints)
    )

    # Log để debug
    log_info(f"Statistical query check:")
    log_info(f"  - has_statistical_intent: {has_statistical_intent}")
    log_info(f"  - has_statistical_text: {has_statistical_text}")
    log_info(f"  - has_statistical_type: {has_statistical_type}")
    log_info(f"  - has_price_filter: {has_price_filter}")
    log_info(f"  - has_specific_attributes: {has_specific_attributes}")
    log_info(f"  - filters: {filters}")
    log_info(f"  - product_attributes: {product_attributes}")
    log_info(f"  - constraints: {constraints}")
    log_info(f"  - len(product_attributes): {len(product_attributes)}")
    log_info(f"  - len(constraints): {len(constraints)}")

    return (has_statistical_intent or has_statistical_text or has_statistical_type or
            has_price_filter or has_specific_attributes)

def aggregate_results_by_category_and_product(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate results by category and product

    Args:
        results: List of results from GraphRAG agent

    Returns:
        Dict containing statistics by category and product
    """
    log_info("Aggregating results by category and product...")

    if not results:
        log_info("No results to aggregate")
        return {
            "categories": {},
            "products": {},
            "variants": [],
            "top_products": []
        }

    has_product_description = any(result.get("product_description") for result in results)
    has_category_description = any(result.get("category_description") for result in results)
    log_info(f"Description info: product_description={has_product_description}, category_description={has_category_description}")

    categories = {}
    products = {}
    all_variants = []

    for result in results:
        if "variant_id" in result:
            variant = result
            category_id = variant.get("category_id")
            category_name = variant.get("category_name")
            product_id = variant.get("product_id")
            product_name = variant.get("product_name")

            all_variants.append(variant)

            if category_id not in categories:
                categories[category_id] = {
                    "id": category_id,
                    "name": category_name,
                    "product_count": 0,
                    "variant_count": 0,
                    "products": []
                }

            if product_id not in products:
                products[product_id] = {
                    "id": product_id,
                    "name": product_name,
                    "category_id": category_id,
                    "category_name": category_name,
                    "variant_count": 0,
                    "variants": []
                }

                if product_id not in categories[category_id]["products"]:
                    categories[category_id]["products"].append(product_id)
                    categories[category_id]["product_count"] += 1

            products[product_id]["variants"].append(variant)
            products[product_id]["variant_count"] += 1
            categories[category_id]["variant_count"] += 1
        else:
            product = result
            category_id = product.get("category_id")
            category_name = product.get("category_name")
            category_description = product.get("category_description", "")
            product_id = product.get("product_id")
            product_name = product.get("product_name")
            product_description = product.get("product_description")

            if product_description is None and category_description:
                product_description = category_description
                log_info(f"Using category description for product {product_name} (ID: {product_id})")

            if category_id not in categories:
                categories[category_id] = {
                    "id": category_id,
                    "name": category_name,
                    "product_count": 0,
                    "variant_count": 0,
                    "products": []
                }

            if product_id not in products:
                products[product_id] = {
                    "id": product_id,
                    "name": product_name,
                    "description": product_description,
                    "category_id": category_id,
                    "category_name": category_name,
                    "category_description": category_description,
                    "variant_count": 0,
                    "variants": []
                }

                if product_id not in categories[category_id]["products"]:
                    categories[category_id]["products"].append(product_id)
                    categories[category_id]["product_count"] += 1

    top_products = select_top_products(products, 3)

    statistics = {
        "categories": categories,
        "products": products,
        "variants": all_variants,
        "top_products": top_products
    }

    log_info(f"Number of categories: {len(categories)}")
    log_info(f"Number of products: {len(products)}")
    log_info(f"Number of variants: {len(all_variants)}")
    log_info(f"Number of top products: {len(top_products)}")

    return statistics

def select_top_products(products: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    """
    Select top products based on variant count

    Args:
        products: Dictionary containing product information
        limit: Number of products to select

    Returns:
        List containing top product information
    """
    sorted_products = sorted(
        products.values(),
        key=lambda x: x["variant_count"],
        reverse=True
    )

    return sorted_products[:limit]

def format_statistics_for_response(statistics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Format statistics for response to Recommend Agent

    Args:
        statistics: Dictionary containing statistics information

    Returns:
        Dict containing formatted information
    """
    categories = statistics.get("categories", {})
    products = statistics.get("products", {})
    top_products = statistics.get("top_products", [])

    formatted_results = []

    for category_id, category in categories.items():
        category_data = {
            "category_id": category_id,
            "category_name": category["name"],
            "product_count": category["product_count"],
            "variant_count": category["variant_count"],
            "products": []
        }

        for product_id in category["products"]:
            if product_id in products:
                product = products[product_id]
                product_data = {
                    "product_id": product_id,
                    "product_name": product["name"],
                    "variant_count": product["variant_count"]
                }
                if "description" in product:
                    product_data["description"] = product["description"]
                category_data["products"].append(product_data)

        formatted_results.append(category_data)

    return {
        "categories": formatted_results,
        "top_products": top_products
    }

# Function moved to core_functions.py
