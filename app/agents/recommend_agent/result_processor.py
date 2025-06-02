"""
Module xử lý kết quả truy vấn và tạo câu trả lời
"""
import json
import time
from typing import List, Dict, Literal
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser
from app.utils.logger import log_info, log_error
from app.llm_clients.gemini_client import gemini_client
from .prompt_templates_updated import RESULT_PROCESSING_TEMPLATE

def _filter_sensitive_data(results: List[Dict], context: Dict = None) -> List[Dict]:
    """
    Lọc dữ liệu nhạy cảm từ kết quả truy vấn

    Args:
        results: Danh sách kết quả truy vấn
        context: Ngữ cảnh bổ sung (thông tin khách hàng, lịch sử chat)

    Returns:
        Danh sách kết quả đã được lọc
    """
    if not results:
        return []

    # Lấy ID khách hàng hiện tại (nếu có)
    current_customer_id = None
    if context and 'customer_info' in context and context['customer_info']:
        current_customer_id = context['customer_info'].get('id')

    # Xác định loại kết quả
    result_type = _determine_result_type(results)

    # Nếu là kết quả về đơn hàng hoặc khách hàng, chỉ giữ lại thông tin của khách hàng hiện tại
    if result_type == "order" or "customer" in str(results).lower():
        filtered_results = []
        for result in results:
            # Kiểm tra các trường có thể chứa ID khách hàng
            customer_id_fields = ["customer_id", "cus.id", "o.customer_id", "user_id"]

            # Kiểm tra xem kết quả có thuộc về khách hàng hiện tại không
            is_current_customer = False

            for field in customer_id_fields:
                if field in result and result[field] is not None:
                    # Nếu có ID khách hàng hiện tại và trùng khớp, giữ lại kết quả
                    if current_customer_id and str(result[field]) == str(current_customer_id):
                        is_current_customer = True
                        break

            # Nếu là khách hàng hiện tại hoặc không có thông tin khách hàng trong kết quả, giữ lại
            if is_current_customer or not any(field in result for field in customer_id_fields):
                # Loại bỏ thông tin nhạy cảm của khách hàng khác
                filtered_result = result.copy()

                # Loại bỏ các trường nhạy cảm
                sensitive_fields = ["email", "phone", "address", "credit_card", "password", "face_embedding"]
                for field in sensitive_fields:
                    if field in filtered_result:
                        filtered_result[field] = "[REDACTED]"

                filtered_results.append(filtered_result)

        return filtered_results

    # Đối với các loại kết quả khác, giữ nguyên
    return results


def _log_entity_ids(results: List[Dict]) -> None:
    """
    Log thông tin về kết quả truy vấn để đánh giá việc trả lời

    Args:
        results: Danh sách kết quả truy vấn
    """
    if not results:
        log_info("❌ Không có kết quả để log")
        return

    # Log số lượng kết quả
    log_info(f"📊 Số lượng kết quả: {len(results)}")

    # Log thông tin về loại kết quả
    result_types = set()
    for result in results:
        if "id" in result:
            # Chuyển đổi ID thành chuỗi để đảm bảo có thể xử lý được
            result_id = str(result["id"])
            result_types.add(result_id.split("_")[0] if "_" in result_id else result_id)

    log_info(f"📊 Loại kết quả: {', '.join(result_types) if result_types else 'Không xác định'}")

    # Log thông tin về số lượng biến thể
    variant_count = 0
    for result in results:
        if "variant_details" in result:
            if isinstance(result["variant_details"], dict) and "variants" in result["variant_details"]:
                variant_count += len(result["variant_details"]["variants"])
            elif isinstance(result["variant_details"], list):
                variant_count += len(result["variant_details"])

    log_info(f"📊 Số lượng biến thể: {variant_count}")

    # Log thông tin về số lượng sản phẩm
    product_count = 0
    for result in results:
        if "product_info" in result:
            if isinstance(result["product_info"], dict) and "products" in result["product_info"]:
                product_count += len(result["product_info"]["products"])
            elif isinstance(result["product_info"], list):
                product_count += len(result["product_info"])

    log_info(f"📊 Số lượng sản phẩm: {product_count}")

    # Log thông tin về điểm số
    scores = []
    for result in results:
        if "score" in result:
            scores.append(str(result["score"]))

    log_info(f"📊 Điểm số: {', '.join(scores) if scores else 'Không có'}")

def _determine_result_type(results: List[Dict]) -> Literal["product", "store", "order", "unknown"]:
    """
    Xác định loại kết quả dựa trên các trường trong kết quả

    Args:
        results: Danh sách kết quả truy vấn

    Returns:
        Loại kết quả: "product", "store", "order", hoặc "unknown"
    """
    if not results:
        return "unknown"

    # Lấy kết quả đầu tiên để kiểm tra
    first_result = results[0]

    # Kiểm tra các trường đặc trưng của sản phẩm
    product_fields = ["name_product", "p.name_product", "descriptions", "p.descriptions",
                     "Beverage_Option", "v.Beverage_Option", "caffeine_mg", "v.caffeine_mg"]

    # Kiểm tra các trường đặc trưng của cửa hàng
    store_fields = ["name_store", "s.name_store", "address", "s.address", "phone", "s.phone", "open_close", "s.open_close"]

    # Kiểm tra các trường đặc trưng của đơn hàng
    order_fields = ["order_date", "o.order_date", "order_id", "o.id", "customer_id", "o.customer_id"]

    # Đếm số trường khớp cho mỗi loại
    product_matches = sum(1 for field in product_fields if field in first_result)
    store_matches = sum(1 for field in store_fields if field in first_result)
    order_matches = sum(1 for field in order_fields if field in first_result)

    # Xác định loại dựa trên số trường khớp nhiều nhất
    if product_matches >= store_matches and product_matches >= order_matches:
        return "product"
    elif store_matches >= product_matches and store_matches >= order_matches:
        return "store"
    elif order_matches >= product_matches and order_matches >= store_matches:
        return "order"
    else:
        return "unknown"


def _organize_variants_by_product_and_category(results: List[Dict]) -> Dict[str, Dict]:
    """
    Tổng hợp các biến thể theo sản phẩm và danh mục

    Args:
        results: Danh sách kết quả truy vấn

    Returns:
        Dict: Thông tin tổng hợp về các biến thể theo sản phẩm và danh mục
    """
    # Log thông tin về kết quả đầu vào
    log_info(f"Bắt đầu tổ chức dữ liệu với {len(results)} kết quả")
    if results:
        log_info(f"Cấu trúc kết quả đầu tiên: {list(results[0].keys())}")

    # Tạo dictionary để lưu trữ thông tin
    organized_data = {
        "by_category": {},  # Tổ chức theo danh mục
        "by_product": {},   # Tổ chức theo sản phẩm
        "all_variants": [], # Danh sách tất cả các biến thể
        "statistics": {     # Thống kê
            "total_categories": 0,
            "total_products": 0,
            "total_variants": 0,
            "products_by_category": {},
            "variants_by_product": {},
            "sorted_products": [],
            "top_products": []
        }
    }

    # Kiểm tra xem kết quả có phải là kết quả gốc từ Neo4j không
    if results and all(isinstance(result, dict) and "category_id" in result and "product_id" in result and "category_name" in result and "product_name" in result for result in results):
        log_info("Phát hiện kết quả gốc từ Neo4j, xử lý theo định dạng gốc")

        # Duyệt qua từng kết quả
        for result in results:
            # Lấy thông tin từ kết quả
            category_id = result.get("category_id")
            category_name = result.get("category_name")
            category_description = result.get("category_description", "")
            product_id = result.get("product_id")
            product_name = result.get("product_name")
            product_description = result.get("product_description", "")

            # Tạo key cho danh mục và sản phẩm
            category_key = f"{category_id}_{category_name}"
            product_key = f"{product_id}_{product_name}"

            # Nếu danh mục chưa có trong dictionary, thêm vào
            if category_key not in organized_data["by_category"]:
                organized_data["by_category"][category_key] = {
                    "id": category_id,
                    "name": category_name,
                    "description": category_description,
                    "products": {},
                    "variants": []
                }
                # Cập nhật thống kê
                organized_data["statistics"]["total_categories"] += 1
                organized_data["statistics"]["products_by_category"][category_key] = 0

            # Nếu sản phẩm chưa có trong dictionary của danh mục, thêm vào
            if product_key not in organized_data["by_category"][category_key]["products"]:
                organized_data["by_category"][category_key]["products"][product_key] = {
                    "id": product_id,
                    "name": product_name,
                    "description": product_description,
                    "variants": []
                }

            # Nếu sản phẩm chưa có trong dictionary chính, thêm vào
            if product_key not in organized_data["by_product"]:
                organized_data["by_product"][product_key] = {
                    "id": product_id,
                    "name": product_name,
                    "description": product_description,
                    "category_id": category_id,
                    "category_name": category_name,
                    "variants": []
                }
                # Cập nhật thống kê
                organized_data["statistics"]["total_products"] += 1
                organized_data["statistics"]["variants_by_product"][product_key] = 0
                organized_data["statistics"]["products_by_category"][category_key] += 1

            # Kiểm tra xem kết quả có chứa thông tin về biến thể không
            if "variant_id" in result:
                # Lấy thông tin về biến thể - ĐẦY ĐỦ TẤT CẢ THUỘC TÍNH
                variant_id = result.get("variant_id")
                beverage_option = result.get("beverage_option")
                price = result.get("price")

                # Sử dụng tên field chính xác từ database
                sugars_g = result.get("sugars_g")
                caffeine_mg = result.get("caffeine_mg")
                calories = result.get("calories")
                sales_rank = result.get("sales_rank")
                protein_g = result.get("protein_g")

                # Thêm các thuộc tính bị thiếu
                dietary_fibre_g = result.get("dietary_fibre_g")
                vitamin_a = result.get("vitamin_a")
                vitamin_c = result.get("vitamin_c")
                variant_name = result.get("variant_name")
                variant_product_id = result.get("variant_product_id")
                variant_product_name = result.get("variant_product_name")
                target_value = result.get("target_value")

                # Tạo đối tượng biến thể với ĐẦY ĐỦ thuộc tính (12 thuộc tính chính)
                variant = {
                    "id": variant_id,                           # 1. ID variant
                    "variant_name": variant_name,
                    "beverage_option": beverage_option,         # 2. Beverage Option
                    "price": price,                             # 3. Price
                    "sugars_g": sugars_g,                       # 4. Sugars_g
                    "caffeine_mg": caffeine_mg,                 # 5. Caffeine_mg
                    "calories": calories,                       # 6. Calories
                    "protein_g": protein_g,                     # 7. Protein_g
                    "dietary_fibre_g": dietary_fibre_g,         # 8. Dietary_fibre_g
                    "vitamin_a": vitamin_a,                     # 9. Vitamin_a
                    "vitamin_c": vitamin_c,                     # 10. Vitamin_c
                    "sales_rank": sales_rank,                   # 11. Sales_rank
                    "product_id": result.get("product_id"),     # 12. Product_id (thêm mới)
                    "variant_product_id": variant_product_id,
                    "variant_product_name": variant_product_name,
                    "target_value": target_value
                }

                # Thêm biến thể vào sản phẩm trong dictionary chính
                organized_data["by_product"][product_key]["variants"].append(variant)

                # Thêm biến thể vào sản phẩm trong dictionary của danh mục
                organized_data["by_category"][category_key]["products"][product_key]["variants"].append(variant)

                # Thêm biến thể vào danh sách tất cả các biến thể
                variant_with_product_info = variant.copy()
                variant_with_product_info["product_id"] = product_id
                variant_with_product_info["product_name"] = product_name
                variant_with_product_info["category_id"] = category_id
                variant_with_product_info["category_name"] = category_name
                organized_data["all_variants"].append(variant_with_product_info)

                # Cập nhật thống kê
                organized_data["statistics"]["total_variants"] += 1
                organized_data["statistics"]["variants_by_product"][product_key] += 1

        return organized_data

    # Duyệt qua từng kết quả
    for result in results:
        # Kiểm tra xem kết quả có phải là danh mục không
        if "id" in result and "name" in result and "products" in result:
            # Đây là kết quả danh mục từ GraphRAG agent
            category_id = result["id"]
            category_name = result["name"]
            category_description = result.get("description", "")
            category_description = result.get("category_description", category_description)  # Thử lấy từ category_description nếu có
            products = result.get("products", [])

            # Log thông tin danh mục
            log_info(f"Xử lý danh mục: {category_name} (ID: {category_id})")
            if category_description:
                log_info(f"Mô tả danh mục: {category_description[:100]}...")

            # Tạo key cho danh mục
            category_key = f"{category_id}_{category_name}"

            # Nếu danh mục chưa có trong dictionary, thêm vào
            if category_key not in organized_data["by_category"]:
                organized_data["by_category"][category_key] = {
                    "id": category_id,
                    "name": category_name,
                    "description": category_description,
                    "products": {},
                    "variants": []
                }

            # Thêm sản phẩm vào danh mục
            for product in products:
                product_id = product.get("id")
                product_name = product.get("name")

                if product_id and product_name:
                    # Tạo key cho sản phẩm
                    product_key = f"{product_id}_{product_name}"

                    # Nếu sản phẩm chưa có trong dictionary của danh mục, thêm vào
                    if product_key not in organized_data["by_category"][category_key]["products"]:
                        # Sử dụng mô tả danh mục nếu không có mô tả sản phẩm
                        product_description = product.get("description")
                        if product_description is None and category_description:
                            product_description = category_description
                            log_info(f"Sử dụng mô tả danh mục cho sản phẩm {product_name} (ID: {product_id}) trong danh mục")

                        organized_data["by_category"][category_key]["products"][product_key] = {
                            "id": product_id,
                            "name": product_name,
                            "description": product_description,
                            "variants": []
                        }

                    # Nếu sản phẩm chưa có trong dictionary chính, thêm vào
                    if product_key not in organized_data["by_product"]:
                        organized_data["by_product"][product_key] = {
                            "id": product_id,
                            "name": product_name,
                            "description": product_description,
                            "category_id": category_id,
                            "category_name": category_name,
                            "category_description": category_description,
                            "variants": []
                        }

            continue

        # Kiểm tra xem kết quả có phải là sản phẩm với biến thể không
        if "id" in result and "name" in result and "category_id" in result and "category_name" in result:
            # Đây là kết quả sản phẩm từ GraphRAG agent
            product_id = result["id"]
            product_name = result["name"]
            category_id = result["category_id"]
            category_name = result["category_name"]
            category_description = result.get("category_description", "")
            product_description = result.get("product_description")

            # Sử dụng mô tả danh mục nếu không có mô tả sản phẩm
            if product_description is None and category_description:
                product_description = category_description
                log_info(f"Sử dụng mô tả danh mục cho sản phẩm {product_name} (ID: {product_id})")

            # Log thông tin sản phẩm
            log_info(f"Xử lý sản phẩm: {product_name} (ID: {product_id}) từ danh mục: {category_name} (ID: {category_id})")
            if product_description:
                log_info(f"Mô tả sản phẩm: {product_description[:100]}...")

            # Lấy biến thể nếu có
            variants = []
            if "variants" in result:
                variants = result["variants"]
                log_info(f"Sản phẩm có {len(variants)} biến thể")

            # Tạo key cho danh mục và sản phẩm
            category_key = f"{category_id}_{category_name}"
            product_key = f"{product_id}_{product_name}"

            # Nếu danh mục chưa có trong dictionary, thêm vào
            if category_key not in organized_data["by_category"]:
                organized_data["by_category"][category_key] = {
                    "id": category_id,
                    "name": category_name,
                    "description": category_description,
                    "products": {},
                    "variants": []
                }

            # Nếu sản phẩm chưa có trong dictionary của danh mục, thêm vào
            if product_key not in organized_data["by_category"][category_key]["products"]:
                organized_data["by_category"][category_key]["products"][product_key] = {
                    "id": product_id,
                    "name": product_name,
                    "variants": []
                }

            # Nếu sản phẩm chưa có trong dictionary chính, thêm vào
            if product_key not in organized_data["by_product"]:
                organized_data["by_product"][product_key] = {
                    "id": product_id,
                    "name": product_name,
                    "description": product_description,
                    "category_id": category_id,
                    "category_name": category_name,
                    "category_description": category_description,
                    "variants": []
                }

            # Thêm các biến thể vào sản phẩm
            for variant in variants:
                # Chuẩn hóa tên thuộc tính
                normalized_variant = {}
                for key, value in variant.items():
                    if key.lower() == "name":
                        normalized_variant["beverage_option"] = value
                    elif key.lower() == "price":
                        normalized_variant["price"] = value
                    elif key.lower() == "sugar":
                        normalized_variant["sugars_g"] = value
                    elif key.lower() == "caffeine":
                        normalized_variant["caffeine_mg"] = value
                    elif key.lower() == "calories":
                        normalized_variant["calories"] = value
                    elif key.lower() == "id":
                        normalized_variant["variant_id"] = value
                    else:
                        normalized_variant[key] = value

                # Thêm biến thể vào sản phẩm trong dictionary chính
                organized_data["by_product"][product_key]["variants"].append(normalized_variant)

                # Thêm biến thể vào sản phẩm trong dictionary của danh mục
                organized_data["by_category"][category_key]["products"][product_key]["variants"].append(normalized_variant)

                # Thêm biến thể vào danh sách tất cả các biến thể
                variant_with_product_info = normalized_variant.copy()
                variant_with_product_info["product_id"] = product_id
                variant_with_product_info["product_name"] = product_name
                variant_with_product_info["category_id"] = category_id
                variant_with_product_info["category_name"] = category_name
                organized_data["all_variants"].append(variant_with_product_info)

            # Log thông tin về các biến thể
            log_info(f"Đã tìm thấy {len(variants)} biến thể trong kết quả")
            if variants:
                log_info(f"Biến thể đầu tiên: {json.dumps(variants[0], ensure_ascii=False)}")

            continue

        # Xử lý các trường hợp khác (cấu trúc dữ liệu cũ)
        variants = []

        # Kiểm tra cấu trúc dữ liệu từ GraphRAG agent
        if "variants" in result:
            # Cấu trúc dữ liệu mới từ GraphRAG agent
            variants = result["variants"]
        elif "variant_details" in result:
            # Cấu trúc dữ liệu cũ
            if isinstance(result["variant_details"], dict) and "variants" in result["variant_details"]:
                variants = result["variant_details"]["variants"]
            elif isinstance(result["variant_details"], list):
                variants = result["variant_details"]

        # Log thông tin về các biến thể
        log_info(f"Đã tìm thấy {len(variants)} biến thể trong kết quả")
        if variants:
            log_info(f"Biến thể đầu tiên: {json.dumps(variants[0], ensure_ascii=False)}")

        # Lấy thông tin về tất cả các biến thể
        all_variants = []
        if "all_variants" in result:
            all_variants = result["all_variants"]

        # Duyệt qua từng biến thể trong variants
        for variant in variants:
            # Chuẩn hóa tên thuộc tính
            normalized_variant = {}
            for key, value in variant.items():
                # Xử lý các trường hợp đặc biệt
                if key.lower() == "name" or key.lower() == "beverage_option" or key.lower() == "beverage_optioon":
                    normalized_variant["beverage_option"] = value
                elif key.lower() == "price":
                    normalized_variant["price"] = value
                elif key.lower() == "sugar" or key.lower() == "sugars_g":
                    normalized_variant["sugars_g"] = value
                elif key.lower() == "caffeine" or key.lower() == "caffeine_mg":
                    normalized_variant["caffeine_mg"] = value
                elif key.lower() == "calories":
                    normalized_variant["calories"] = value
                elif key.lower() == "id" or key.lower() == "variant_id":
                    normalized_variant["variant_id"] = value
                elif key.lower() == "protein" or key.lower() == "protein_g":
                    normalized_variant["protein_g"] = value
                elif key.lower() == "sales_rank":
                    normalized_variant["sales_rank"] = value
                else:
                    normalized_variant[key] = value

            # Log thông tin về biến thể đã chuẩn hóa
            log_info(f"Biến thể đã chuẩn hóa: {json.dumps(normalized_variant, ensure_ascii=False)[:100]}...")

            # Thêm vào danh sách tất cả các biến thể
            organized_data["all_variants"].append(normalized_variant)

            # Lấy thông tin về danh mục
            category_id = variant.get("category_id")
            category_name = variant.get("category_name")

            if category_id and category_name:
                # Tạo key cho danh mục
                category_key = f"{category_id}_{category_name}"

                # Nếu danh mục chưa có trong dictionary, thêm vào
                if category_key not in organized_data["by_category"]:
                    organized_data["by_category"][category_key] = {
                        "id": category_id,
                        "name": category_name,
                        "products": {},
                        "variants": []
                    }

                # Thêm biến thể vào danh sách biến thể của danh mục
                organized_data["by_category"][category_key]["variants"].append(normalized_variant)

                # Lấy thông tin về sản phẩm
                product_id = variant.get("product_id")
                product_name = variant.get("product_name")

                if product_id and product_name:
                    # Tạo key cho sản phẩm
                    product_key = f"{product_id}_{product_name}"

                    # Nếu sản phẩm chưa có trong dictionary của danh mục, thêm vào
                    if product_key not in organized_data["by_category"][category_key]["products"]:
                        organized_data["by_category"][category_key]["products"][product_key] = {
                            "id": product_id,
                            "name": product_name,
                            "variants": []
                        }

                    # Thêm biến thể vào danh sách biến thể của sản phẩm trong danh mục
                    organized_data["by_category"][category_key]["products"][product_key]["variants"].append(normalized_variant)

                    # Nếu sản phẩm chưa có trong dictionary chính, thêm vào
                    if product_key not in organized_data["by_product"]:
                        organized_data["by_product"][product_key] = {
                            "id": product_id,
                            "name": product_name,
                            "category_id": category_id,
                            "category_name": category_name,
                            "variants": []
                        }

                    # Thêm biến thể vào danh sách biến thể của sản phẩm
                    organized_data["by_product"][product_key]["variants"].append(normalized_variant)

        # Duyệt qua từng biến thể trong all_variants
        for variant in all_variants:
            # Kiểm tra xem biến thể đã có trong danh sách tất cả các biến thể chưa
            variant_id = variant.get("variant_id")
            if variant_id and not any(v.get("variant_id") == variant_id for v in organized_data["all_variants"]):
                # Thêm vào danh sách tất cả các biến thể
                organized_data["all_variants"].append(variant)

    # Tính toán số lượng biến thể cho mỗi sản phẩm
    for product_key, product_info in organized_data["by_product"].items():
        variant_count = len(product_info.get("variants", []))
        organized_data["statistics"]["variants_by_product"][product_key] = variant_count
        organized_data["statistics"]["total_variants"] += variant_count

        # Cập nhật số lượng sản phẩm
        if product_key not in organized_data["statistics"]["products_by_category"]:
            organized_data["statistics"]["total_products"] += 1

            # Cập nhật số lượng sản phẩm theo danh mục
            category_id = product_info.get("category_id")
            category_name = product_info.get("category_name")
            if category_id and category_name:
                category_key = f"{category_id}_{category_name}"
                if category_key not in organized_data["statistics"]["products_by_category"]:
                    organized_data["statistics"]["products_by_category"][category_key] = 0
                    organized_data["statistics"]["total_categories"] += 1
                organized_data["statistics"]["products_by_category"][category_key] += 1

    # Thống kê và sắp xếp các sản phẩm theo số lượng biến thể và xếp hạng bán chạy
    product_stats = []
    for product_key, product_info in organized_data["by_product"].items():
        # Tính điểm trung bình của xếp hạng bán chạy
        avg_sales_rank = 0
        total_variants = len(product_info.get("variants", []))
        if total_variants > 0:
            sum_sales_rank = sum(variant.get("sales_rank", 999) for variant in product_info.get("variants", []))
            avg_sales_rank = sum_sales_rank / total_variants

        product_stats.append({
            "key": product_key,
            "id": product_info.get("id", "Unknown"),
            "name": product_info.get("name", "Unknown"),
            "category_id": product_info.get("category_id", "Unknown"),
            "category_name": product_info.get("category_name", "Unknown"),
            "variant_count": total_variants,
            "avg_sales_rank": avg_sales_rank,
            "info": product_info
        })

    # Nhóm sản phẩm theo danh mục
    products_by_category = {}
    for product in product_stats:
        category_id = product["category_id"]
        if category_id not in products_by_category:
            products_by_category[category_id] = []
        products_by_category[category_id].append(product)

    # Sắp xếp sản phẩm trong mỗi danh mục theo xếp hạng bán chạy và số lượng biến thể
    for category_id, products in products_by_category.items():
        products_by_category[category_id] = sorted(
            products,
            key=lambda x: (x["avg_sales_rank"], -x["variant_count"])
        )

    # Chọn ra tối đa 3 sản phẩm từ mỗi danh mục
    diverse_products = []
    for category_id, products in products_by_category.items():
        diverse_products.extend(products[:3])

    # Sắp xếp lại theo xếp hạng bán chạy
    diverse_products.sort(key=lambda x: x["avg_sales_rank"])

    # Lưu trữ thông tin sản phẩm đã sắp xếp
    organized_data["statistics"]["sorted_products"] = diverse_products

    # Chọn ra 3 sản phẩm hàng đầu từ danh sách đa dạng
    top_products = diverse_products[:3]
    organized_data["statistics"]["top_products"] = top_products

    # Log thông tin thống kê
    log_info(f"Thống kê: {organized_data['statistics']['total_categories']} danh mục, {organized_data['statistics']['total_products']} sản phẩm, {organized_data['statistics']['total_variants']} biến thể")
    if top_products:
        log_info(f"Top 3 sản phẩm: {', '.join([p['name'] for p in top_products])}")
    else:
        log_info("Không có sản phẩm hàng đầu")

    return organized_data


def _format_organized_data_for_llm(organized_data: Dict[str, Dict], max_products: int = 3) -> str:
    """
    Định dạng dữ liệu đã tổ chức để truyền cho LLM

    Args:
        organized_data: Dữ liệu đã tổ chức
        max_products: Số lượng sản phẩm tối đa để hiển thị trong phần chính

    Returns:
        str: Dữ liệu đã định dạng
    """
    # Log thông tin về dữ liệu đã tổ chức
    log_info(f"Định dạng dữ liệu với {len(organized_data['by_product'])} sản phẩm và {len(organized_data['by_category'])} danh mục")
    log_info(f"Thống kê: {organized_data['statistics']['total_categories']} danh mục, {organized_data['statistics']['total_products']} sản phẩm, {organized_data['statistics']['total_variants']} biến thể")

    # Kiểm tra xem có sản phẩm nào không
    if not organized_data["by_product"]:
        # Kiểm tra xem có danh mục nào không
        if organized_data["by_category"]:
            result = "THÔNG TIN DANH MỤC VÀ SẢN PHẨM LIÊN QUAN:\n\n"

            # Hiển thị thông tin danh mục trước
            for category_key, category_info in organized_data["by_category"].items():
                result += f"📂 **DANH MỤC: {category_info['name']}**\n"

                # Thêm mô tả danh mục nếu có
                if "description" in category_info and category_info["description"]:
                    result += f"Mô tả danh mục: {category_info['description']}\n"

                # Thêm số lượng sản phẩm trong danh mục
                product_count = len(category_info["products"]) if category_info["products"] else 0
                result += f"Số lượng sản phẩm: {product_count}\n\n"

                # Hiển thị danh sách sản phẩm trong danh mục
                if category_info["products"]:
                    result += "📋 **CÁC SẢN PHẨM TRONG DANH MỤC:**\n"
                    for i, (product_key, product_info) in enumerate(category_info["products"].items(), 1):
                        result += f"{i}. **{product_info['name']}**\n"

                        # Thêm mô tả sản phẩm nếu có và khác với mô tả danh mục
                        if "description" in product_info and product_info["description"]:
                            # Kiểm tra xem mô tả sản phẩm có giống với mô tả danh mục không
                            category_desc = category_info.get("description", "")
                            if product_info["description"] != category_desc and product_info["description"].strip():
                                # Cắt bớt mô tả nếu quá dài và loại bỏ phần lặp lại
                                product_desc = product_info["description"].strip()
                                # Tìm và loại bỏ phần lặp lại
                                if len(product_desc) > 200:
                                    # Tìm vị trí có thể cắt (dấu chấm hoặc dấu phẩy)
                                    cut_pos = product_desc.find('.', 150)
                                    if cut_pos == -1:
                                        cut_pos = product_desc.find(',', 150)
                                    if cut_pos != -1:
                                        product_desc = product_desc[:cut_pos + 1]
                                    else:
                                        product_desc = product_desc[:200] + "..."

                                result += f"   Mô tả: {product_desc}\n"

                        result += "\n"

                result += "─" * 50 + "\n\n"

            return result
        else:
            return "THÔNG TIN SẢN PHẨM CHÍNH:\n\nKhông có thông tin sản phẩm nào.\n\nDANH SÁCH SẢN PHẨM GỢI Ý:\n\nKhông có sản phẩm nào được gợi ý."

    # Sử dụng thông tin thống kê đã có
    if "statistics" in organized_data and "sorted_products" in organized_data["statistics"] and organized_data["statistics"]["sorted_products"]:
        # Sử dụng danh sách sản phẩm đã sắp xếp từ thống kê
        all_products = organized_data["statistics"]["sorted_products"]

        # Lấy tối đa 3 sản phẩm cho phần chính
        top_products = all_products[:3]

        # Lấy các sản phẩm còn lại cho phần gợi ý (chỉ khi có nhiều hơn 3 sản phẩm)
        remaining_products = all_products[3:] if len(all_products) > 3 else []

        # Log thông tin
        log_info(f"Tổng số sản phẩm: {len(all_products)}")
        log_info(f"Sản phẩm chính: {len(top_products)}")
        log_info(f"Sản phẩm gợi ý: {len(remaining_products)}")

        if len(all_products) <= 3:
            log_info("Số lượng sản phẩm <= 3, không tạo phần gợi ý")
    else:
        # Tạo danh sách sản phẩm đã sắp xếp theo xếp hạng bán chạy (phương pháp cũ)
        sorted_products = []
        for product_key, product_info in organized_data["by_product"].items():
            # Tính điểm trung bình của xếp hạng bán chạy
            avg_sales_rank = 0
            total_variants = len(product_info["variants"])
            if total_variants > 0:
                sum_sales_rank = sum(variant.get("sales_rank", 999) for variant in product_info["variants"])
                avg_sales_rank = sum_sales_rank / total_variants
            else:
                # Nếu không có biến thể, sử dụng giá trị mặc định
                avg_sales_rank = 500  # Giá trị trung bình

            sorted_products.append({
                "key": product_key,
                "id": product_info.get("id", "Unknown"),
                "name": product_info.get("name", "Unknown"),
                "info": product_info,
                "avg_sales_rank": avg_sales_rank
            })

        # Sắp xếp sản phẩm theo xếp hạng bán chạy (thấp hơn = tốt hơn)
        sorted_products.sort(key=lambda x: x["avg_sales_rank"])

        # Lấy tối đa 3 sản phẩm cho phần chính
        top_products = sorted_products[:3]

        # Lấy các sản phẩm còn lại cho phần gợi ý (chỉ khi có nhiều hơn 3 sản phẩm)
        remaining_products = sorted_products[3:] if len(sorted_products) > 3 else []

        # Log thông tin
        log_info(f"Sử dụng phương pháp cũ: {len(sorted_products)} sản phẩm")
        log_info(f"Sản phẩm chính: {len(top_products)}")
        log_info(f"Sản phẩm gợi ý: {len(remaining_products)}")

        if len(sorted_products) <= 3:
            log_info("Số lượng sản phẩm <= 3, không tạo phần gợi ý")

    # Kiểm tra xem có biến thể nào không
    has_variants = False

    # Kiểm tra top_products trước
    for product in top_products:
        if product["info"]["variants"]:
            has_variants = True
            break

    # Nếu không tìm thấy trong top_products, kiểm tra remaining_products
    if not has_variants and remaining_products:
        for product in remaining_products:
            if product["info"]["variants"]:
                has_variants = True
                break

    # Tạo chuỗi kết quả dựa trên loại dữ liệu
    if has_variants:
        result = "THÔNG TIN SẢN PHẨM VÀ BIẾN THỂ LIÊN QUAN:\n\n"
    else:
        result = "THÔNG TIN SẢN PHẨM LIÊN QUAN:\n\n"

    # Tạo một từ điển để lưu trữ các biến thể đã được xử lý
    processed_variants = set()

    # Tạo một tập hợp để lưu trữ các sản phẩm đã được hiển thị
    displayed_products = set()

    # Thêm thông tin về các sản phẩm chính
    for i, product in enumerate(top_products):
        product_info = product["info"]
        product_key = product["key"]

        # Thêm sản phẩm vào danh sách đã hiển thị
        displayed_products.add(product_key)

        result += f"{i+1}. **{product_info['name']}**\n"

        # Thêm thông tin về danh mục
        if "category_name" in product_info:
            result += f"   📂 **Danh mục:** {product_info['category_name']}\n"

            # Thêm mô tả danh mục nếu có
            if "category_description" in product_info and product_info["category_description"]:
                category_desc = product_info["category_description"].strip()
                # Cắt bớt mô tả danh mục nếu quá dài
                if len(category_desc) > 150:
                    cut_pos = category_desc.find('.', 100)
                    if cut_pos != -1:
                        category_desc = category_desc[:cut_pos + 1]
                    else:
                        category_desc = category_desc[:150] + "..."
                result += f"   📝 **Mô tả danh mục:** {category_desc}\n"

        # Thêm mô tả sản phẩm nếu có và không phải là mô tả danh mục
        if "description" in product_info and product_info["description"]:
            # Kiểm tra xem mô tả sản phẩm có giống với mô tả danh mục không
            category_desc = product_info.get("category_description", "")
            if product_info["description"] != category_desc and product_info["description"].strip():
                # Cắt bớt mô tả sản phẩm nếu quá dài và loại bỏ phần lặp lại
                product_desc = product_info["description"].strip()
                # Tìm và loại bỏ phần lặp lại
                if len(product_desc) > 200:
                    # Tìm vị trí có thể cắt (dấu chấm hoặc dấu phẩy)
                    cut_pos = product_desc.find('.', 150)
                    if cut_pos == -1:
                        cut_pos = product_desc.find(',', 150)
                    if cut_pos != -1:
                        product_desc = product_desc[:cut_pos + 1]
                    else:
                        product_desc = product_desc[:200] + "..."

                result += f"   🔍 **Mô tả sản phẩm:** {product_desc}\n"

        # Thêm thông tin về biến thể tốt nhất (chỉ hiển thị 1 biến thể cho mỗi sản phẩm)
        if product_info["variants"]:
            # Sắp xếp biến thể theo xếp hạng bán chạy
            sorted_variants = sorted(
                product_info["variants"],
                key=lambda x: (float(x.get("sales_rank", 999)) if x.get("sales_rank") is not None else 999)
            )

            # Chọn biến thể tốt nhất
            best_variant = sorted_variants[0]

            result += f"\tTùy chọn tốt nhất: {best_variant.get('beverage_option', 'Không có')}, "
            result += f"Giá: {best_variant.get('price', 'Không có')}, "
            result += f"Calories: {best_variant.get('calories', 'Không có')}, "
            result += f"Protein (g): {best_variant.get('protein_g', 'Không có')}, "
            result += f"Đường (g): {best_variant.get('sugars_g', 'Không có')}, "
            result += f"Caffeine (mg): {best_variant.get('caffeine_mg', 'Không có')}"

            # Thêm vitamin nếu có
            if best_variant.get('vitamin_a') and str(best_variant.get('vitamin_a')).replace('%', '').strip() not in ['0', '0.0', '']:
                result += f", Vitamin A: {best_variant.get('vitamin_a')}"
            if best_variant.get('vitamin_c') and str(best_variant.get('vitamin_c')).replace('%', '').strip() not in ['0', '0.0', '']:
                result += f", Vitamin C: {best_variant.get('vitamin_c')}"
            if best_variant.get('dietary_fibre_g') and str(best_variant.get('dietary_fibre_g')).strip() not in ['0', '0.0', '']:
                result += f", Chất xơ (g): {best_variant.get('dietary_fibre_g')}"

            result += "\n"

            # Thêm variant_id vào danh sách đã xử lý
            if "variant_id" in best_variant:
                processed_variants.add(str(best_variant["variant_id"]))

            # Thêm thông tin về số lượng biến thể khác
            if len(product_info["variants"]) > 1:
                result += f"\t(Còn {len(product_info['variants']) - 1} tùy chọn khác)\n"

        # Thêm dòng phân cách giữa các sản phẩm
        result += "\n" + "─" * 50 + "\n\n"

    # Thêm thông tin về các sản phẩm còn lại (chỉ khi có nhiều hơn 3 sản phẩm)
    if remaining_products and len(remaining_products) > 0:
        result += "GỢI Ý THÊM:\n\n"

        for i, product in enumerate(remaining_products):
            product_info = product["info"]
            product_key = product["key"]

            # Thêm sản phẩm vào danh sách đã hiển thị
            displayed_products.add(product_key)

            result += f"{i+1}. **{product_info['name']}**"

            # Thêm thông tin về danh mục
            if "category_name" in product_info:
                result += f": Thuộc danh mục {product_info['category_name']}"

            result += "\n"

            # Thêm thông tin về biến thể tốt nhất (chỉ hiển thị 1 biến thể cho mỗi sản phẩm)
            if product_info["variants"]:
                # Sắp xếp biến thể theo xếp hạng bán chạy
                sorted_variants = sorted(
                    product_info["variants"],
                    key=lambda x: (float(x.get("sales_rank", 999)) if x.get("sales_rank") is not None else 999)
                )

                # Chọn biến thể tốt nhất
                best_variant = sorted_variants[0]

                result += f"\tTùy chọn tốt nhất: {best_variant.get('beverage_option', 'Không có')}, "
                result += f"Giá: {best_variant.get('price', 'Không có')}, "
                result += f"Calories: {best_variant.get('calories', 'Không có')}, "
                result += f"Protein (g): {best_variant.get('protein_g', 'Không có')}, "
                result += f"Đường (g): {best_variant.get('sugars_g', 'Không có')}, "
                result += f"Caffeine (mg): {best_variant.get('caffeine_mg', 'Không có')}"

                # Thêm vitamin nếu có
                if best_variant.get('vitamin_a') and str(best_variant.get('vitamin_a')).replace('%', '').strip() not in ['0', '0.0', '']:
                    result += f", Vitamin A: {best_variant.get('vitamin_a')}"
                if best_variant.get('vitamin_c') and str(best_variant.get('vitamin_c')).replace('%', '').strip() not in ['0', '0.0', '']:
                    result += f", Vitamin C: {best_variant.get('vitamin_c')}"
                if best_variant.get('dietary_fibre_g') and str(best_variant.get('dietary_fibre_g')).strip() not in ['0', '0.0', '']:
                    result += f", Chất xơ (g): {best_variant.get('dietary_fibre_g')}"

                result += "\n"

                # Thêm variant_id vào danh sách đã xử lý
                if "variant_id" in best_variant:
                    processed_variants.add(str(best_variant["variant_id"]))

                # Thêm thông tin về số lượng biến thể khác
                if len(product_info["variants"]) > 1:
                    result += f"\t(Còn {len(product_info['variants']) - 1} tùy chọn khác)\n"

            result += "\n"

    # Tìm các biến thể chưa được xử lý
    unprocessed_variants = []
    for variant in organized_data["all_variants"]:
        if "variant_id" in variant and str(variant["variant_id"]) not in processed_variants:
            unprocessed_variants.append(variant)

    # Nếu có biến thể chưa được xử lý, thêm vào phần gợi ý
    if unprocessed_variants:
        # Tổ chức các biến thể chưa được xử lý theo sản phẩm
        unprocessed_by_product = {}
        for variant in unprocessed_variants:
            product_id = variant.get("product_id")
            product_name = variant.get("product_name")
            if product_id and product_name:
                product_key = f"{product_id}_{product_name}"
                if product_key not in unprocessed_by_product:
                    unprocessed_by_product[product_key] = {
                        "name": product_name,
                        "category_name": variant.get("category_name", "Không xác định"),
                        "variants": []
                    }
                unprocessed_by_product[product_key]["variants"].append(variant)

        # Thêm các biến thể chưa được xử lý vào phần gợi ý
        if unprocessed_by_product:
            if "GỢI Ý THÊM:" not in result:
                result += "GỢI Ý THÊM:\n\n"

            for product_key, product_info in unprocessed_by_product.items():
                result += f"Sản phẩm: {product_info['name']}\n"

                # Thêm mô tả sản phẩm nếu có
                if "description" in product_info and product_info["description"]:
                    result += f"Mô tả: {product_info['description']}\n"

                # Thêm thông tin về biến thể tốt nhất (chỉ hiển thị 1 biến thể cho mỗi sản phẩm)
                # Sắp xếp biến thể theo xếp hạng bán chạy
                sorted_variants = sorted(
                    product_info["variants"],
                    key=lambda x: (float(x.get("sales_rank", 999)) if x.get("sales_rank") is not None else 999)
                )

                # Chọn biến thể tốt nhất
                best_variant = sorted_variants[0]

                result += f"\tTùy chọn tốt nhất: {best_variant.get('beverage_option', 'Không có')}, "
                result += f"Giá: {best_variant.get('price', 'Không có')}, "
                result += f"Calories: {best_variant.get('calories', 'Không có')}, "
                result += f"Protein (g): {best_variant.get('protein_g', 'Không có')}, "
                result += f"Đường (g): {best_variant.get('sugars_g', 'Không có')}, "
                result += f"Caffeine (mg): {best_variant.get('caffeine_mg', 'Không có')}"

                # Thêm vitamin nếu có
                if best_variant.get('vitamin_a') and str(best_variant.get('vitamin_a')).replace('%', '').strip() not in ['0', '0.0', '']:
                    result += f", Vitamin A: {best_variant.get('vitamin_a')}"
                if best_variant.get('vitamin_c') and str(best_variant.get('vitamin_c')).replace('%', '').strip() not in ['0', '0.0', '']:
                    result += f", Vitamin C: {best_variant.get('vitamin_c')}"
                if best_variant.get('dietary_fibre_g') and str(best_variant.get('dietary_fibre_g')).strip() not in ['0', '0.0', '']:
                    result += f", Chất xơ (g): {best_variant.get('dietary_fibre_g')}"

                result += "\n"

                # Thêm thông tin về số lượng biến thể khác
                if len(product_info["variants"]) > 1:
                    result += f"\t(Còn {len(product_info['variants']) - 1} tùy chọn khác)\n"

                result += f"\tThuộc danh mục {product_info['category_name']}\n\n"

    # Kiểm tra xem có sản phẩm nào chưa được hiển thị không
    displayed_products = set()

    # Thêm các sản phẩm đã hiển thị vào tập hợp
    for product in top_products:
        displayed_products.add(product["key"])

    # Log thông tin về sản phẩm hàng đầu
    log_info(f"Đã hiển thị {len(top_products)} sản phẩm hàng đầu: {', '.join([p['name'] for p in top_products])}")

    for product in remaining_products:
        displayed_products.add(product["key"])

    # Log thông tin về sản phẩm gợi ý
    if remaining_products:
        log_info(f"Đã hiển thị {len(remaining_products)} sản phẩm gợi ý: {', '.join([p['name'] for p in remaining_products])}")

    # Tìm các sản phẩm chưa được hiển thị
    undisplayed_products = {}

    # Duyệt qua tất cả các biến thể
    for variant in organized_data["all_variants"]:
        product_id = variant.get("product_id")
        product_name = variant.get("product_name")

        if product_id and product_name:
            product_key = f"{product_id}_{product_name}"

            # Chỉ thêm vào nếu sản phẩm chưa được hiển thị
            if product_key not in displayed_products:
                if product_key not in undisplayed_products:
                    undisplayed_products[product_key] = {
                        "name": product_name,
                        "variants": []
                    }

                undisplayed_products[product_key]["variants"].append(variant)

    # Kiểm tra xem có sản phẩm nào chưa được hiển thị không
    all_products_displayed = True
    undisplayed_product_keys = []

    # Tạo danh sách các sản phẩm chưa được hiển thị
    for product_key in organized_data["by_product"]:
        if product_key not in displayed_products:
            all_products_displayed = False
            undisplayed_product_keys.append(product_key)

    # Kiểm tra xem có cần hiển thị phần gợi ý không (chỉ khi có nhiều hơn 3 sản phẩm tổng cộng)
    total_products_count = len(organized_data["by_product"])

    # Nếu tổng số sản phẩm <= 3, không hiển thị phần gợi ý
    if total_products_count <= 3:
        log_info(f"Tổng số sản phẩm ({total_products_count}) <= 3, không hiển thị phần gợi ý")
    elif all_products_displayed:
        # Không hiển thị gì thêm
        log_info("Tất cả sản phẩm đã được hiển thị, không hiển thị phần DANH SÁCH SẢN PHẨM GỢI Ý")
    else:
        # Chỉ hiển thị các sản phẩm chưa được hiển thị
        products_to_display = {}

        # Lấy thông tin về các sản phẩm chưa được hiển thị
        for product_key in undisplayed_product_keys:
            if product_key in organized_data["by_product"]:
                product_info = organized_data["by_product"][product_key]
                products_to_display[product_key] = {
                    "name": product_info["name"],
                    "description": product_info.get("description"),
                    "category_name": product_info.get("category_name", "Không xác định"),
                    "category_description": product_info.get("category_description")
                }

        # Chỉ hiển thị nếu có sản phẩm chưa được hiển thị
        if products_to_display:
            result += "DANH SÁCH SẢN PHẨM GỢI Ý KHÁC:\n\n"

            for i, (product_key, product_info) in enumerate(sorted(products_to_display.items(), key=lambda x: x[1]["name"])):
                result += f"* **{product_info['name']}** (Danh mục: {product_info['category_name']})\n"
                # Thêm mô tả sản phẩm nếu có và không phải là mô tả danh mục
                if product_info.get("description"):
                    # Kiểm tra xem mô tả sản phẩm có giống với mô tả danh mục không
                    category_desc = product_info.get("category_description", "")
                    if product_info["description"] != category_desc:
                        result += f"  Mô tả: {product_info['description']}\n"
                    elif category_desc:
                        # Nếu mô tả sản phẩm giống với mô tả danh mục, chỉ hiển thị một lần
                        result += f"  Mô tả: {category_desc} (Mô tả danh mục)\n"

            result += "\n"
        else:
            log_info("Không có sản phẩm chưa được hiển thị, không hiển thị phần DANH SÁCH SẢN PHẨM GỢI Ý")

    # Nếu có sản phẩm chưa được hiển thị và không phải tất cả sản phẩm đã được hiển thị
    # Chỉ xử lý khi tổng số sản phẩm > 3
    if undisplayed_products and not all_products_displayed and total_products_count > 3:
        # Kiểm tra xem các sản phẩm trong undisplayed_products có thực sự chưa được hiển thị không
        real_undisplayed = {}
        for product_key, product_info in undisplayed_products.items():
            if product_key not in displayed_products and product_key not in products_to_display:
                real_undisplayed[product_key] = product_info

        # Log thông tin về sản phẩm chưa được hiển thị
        if real_undisplayed:
            log_info(f"Có {len(real_undisplayed)} sản phẩm chưa được hiển thị: {', '.join([info['name'] for info in real_undisplayed.values()])}")
        else:
            log_info("Không có sản phẩm thực sự chưa được hiển thị")

        # Chỉ hiển thị nếu có sản phẩm thực sự chưa được hiển thị
        if real_undisplayed:
            # Nếu chưa có phần "DANH SÁCH SẢN PHẨM GỢI Ý KHÁC", thêm vào
            if "DANH SÁCH SẢN PHẨM GỢI Ý KHÁC" not in result:
                result += "DANH SÁCH SẢN PHẨM GỢI Ý KHÁC:\n\n"

            # Sắp xếp các sản phẩm theo tên
            for i, (product_key, product_info) in enumerate(sorted(real_undisplayed.items(), key=lambda x: x[1]["name"])):
                result += f"{i+1}. **{product_info['name']}**"

                # Thêm thông tin về danh mục nếu có
                if "category_name" in product_info:
                    result += f": Thuộc danh mục {product_info['category_name']}"

                result += "\n"

                # Thêm mô tả sản phẩm nếu có và không phải là mô tả danh mục
                if "description" in product_info and product_info["description"]:
                    # Kiểm tra xem mô tả sản phẩm có giống với mô tả danh mục không
                    category_desc = product_info.get("category_description", "")
                    if product_info["description"] != category_desc:
                        result += f"Mô tả: {product_info['description']}\n"
                    elif category_desc:
                        # Nếu mô tả sản phẩm giống với mô tả danh mục, chỉ hiển thị một lần
                        result += f"Mô tả: {category_desc} (Mô tả danh mục)\n"

                # Sắp xếp các biến thể theo xếp hạng bán chạy
                sorted_variants = sorted(
                    product_info["variants"],
                    key=lambda x: (float(x.get("sales_rank", 999)) if x.get("sales_rank") is not None else 999)
                )

                # Thêm thông tin về biến thể tốt nhất (chỉ hiển thị 1 biến thể cho mỗi sản phẩm)
                if sorted_variants:
                    # Chọn biến thể tốt nhất
                    best_variant = sorted_variants[0]

                    result += f"\tTùy chọn tốt nhất: {best_variant.get('beverage_option', 'Không có')}, "
                    result += f"Giá: {best_variant.get('price', 'Không có')}, "
                    result += f"Calories: {best_variant.get('calories', 'Không có')}, "
                    result += f"Protein (g): {best_variant.get('protein_g', 'Không có')}, "
                    result += f"Đường (g): {best_variant.get('sugars_g', 'Không có')}, "
                    result += f"Caffeine (mg): {best_variant.get('caffeine_mg', 'Không có')}"

                    # Thêm vitamin nếu có
                    if best_variant.get('vitamin_a') and str(best_variant.get('vitamin_a')).replace('%', '').strip() not in ['0', '0.0', '']:
                        result += f", Vitamin A: {best_variant.get('vitamin_a')}"
                    if best_variant.get('vitamin_c') and str(best_variant.get('vitamin_c')).replace('%', '').strip() not in ['0', '0.0', '']:
                        result += f", Vitamin C: {best_variant.get('vitamin_c')}"
                    if best_variant.get('dietary_fibre_g') and str(best_variant.get('dietary_fibre_g')).strip() not in ['0', '0.0', '']:
                        result += f", Chất xơ (g): {best_variant.get('dietary_fibre_g')}"

                    result += "\n"

                    # Thêm thông tin về số lượng biến thể khác
                    if len(sorted_variants) > 1:
                        result += f"\t(Còn {len(sorted_variants) - 1} tùy chọn khác)\n"

                result += "\n"
        else:
            log_info("Không có sản phẩm với biến thể chưa được hiển thị, không hiển thị phần DANH SÁCH SẢN PHẨM GỢI Ý KHÁC")
    elif total_products_count <= 3:
        log_info("Tổng số sản phẩm <= 3, bỏ qua phần xử lý sản phẩm chưa hiển thị")

    return result


def process_results(message: str, results: List[Dict], context: Dict = None) -> str:
    """Xử lý kết quả truy vấn với LLM và retry logic"""
    log_info("\n4️⃣ Processing query results...")
    log_info(f"📝 Original message: {message}")
    log_info(f"📋 Processing {len(results)} results")

    # Log thông tin về kết quả truy vấn
    _log_entity_ids(results)

    if not results:
        log_info("❌ No results to process")
        return "Xin lỗi, tôi không tìm thấy thông tin phù hợp với câu hỏi của bạn."

    # Xác định loại kết quả (sản phẩm, cửa hàng, đơn hàng)
    result_type = _determine_result_type(results)
    log_info(f"📊 Determined result type: {result_type}")

    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            # Tăng cường message với ngữ cảnh từ lịch sử chat
            enhanced_message = message

            if context and 'chat_context' in context and context['chat_context']:
                chat_context = context['chat_context']
                log_info(f"Using chat context for result processing: {str(chat_context)[:200]}...")

                # Nếu có sản phẩm được nhắc đến, thêm vào message
                if 'mentioned_products' in chat_context and chat_context['mentioned_products']:
                    products = ', '.join(chat_context['mentioned_products'])
                    if "đó" in message.lower() or "này" in message.lower() or "kia" in message.lower() or "loại" in message.lower():
                        enhanced_message = f"{message} (Đang đề cập đến sản phẩm: {products})"
                        log_info(f"Enhanced message with mentioned products: {enhanced_message}")

                # Nếu có danh mục được nhắc đến, thêm vào message
                if 'mentioned_categories' in chat_context and chat_context['mentioned_categories']:
                    categories = ', '.join(chat_context['mentioned_categories'])
                    if "đó" in message.lower() or "này" in message.lower() or "kia" in message.lower() or "loại" in message.lower():
                        enhanced_message = f"{enhanced_message} (Danh mục: {categories})"
                        log_info(f"Enhanced message with mentioned categories: {enhanced_message}")

                # Nếu có context_summary, thêm vào message
                if 'context_summary' in chat_context and chat_context['context_summary']:
                    enhanced_message = f"{enhanced_message} (Ngữ cảnh: {chat_context['context_summary']})"
                    log_info(f"Enhanced message with context summary: {enhanced_message}")

                # Nếu có last_intent, thêm vào message
                if 'last_intent' in chat_context and chat_context['last_intent']:
                    enhanced_message = f"{enhanced_message} (Ý định tìm kiếm gần đây: {chat_context['last_intent']})"
                    log_info(f"Enhanced message with last intent: {enhanced_message}")

                # Nếu có preferences, thêm vào message
                if 'preferences' in chat_context and chat_context['preferences']:
                    preferences = ', '.join(chat_context['preferences'])
                    enhanced_message = f"{enhanced_message} (Sở thích của khách hàng: {preferences})"
                    log_info(f"Enhanced message with preferences: {enhanced_message}")

                # Nếu có price_requirements, thêm vào message
                if 'price_requirements' in chat_context and chat_context['price_requirements']:
                    enhanced_message = f"{enhanced_message} (Yêu cầu giá đã đề cập trước đó: {chat_context['price_requirements']})"
                    log_info(f"Enhanced message with price requirements: {enhanced_message}")

                # Nếu có recent_references, thêm vào message
                if 'recent_references' in chat_context and chat_context['recent_references']:
                    enhanced_message = f"{enhanced_message} (Lưu ý: {chat_context['recent_references']})"
                    log_info(f"Enhanced message with recent references: {enhanced_message}")

            # Sử dụng gemini_client với temperature thấp để có câu trả lời chính xác và dựa trên dữ liệu
            # Lưu temperature hiện tại
            current_temp = gemini_client._temperature

            # Đặt temperature thấp cho việc tạo câu trả lời chính xác
            gemini_client._temperature = 0.1

            # Lấy model từ gemini_client
            llm = gemini_client.model

            # Tạo prompt từ template
            prompt = PromptTemplate(
                input_variables=["question", "context"],
                template=RESULT_PROCESSING_TEMPLATE
            )

            # Tạo chain
            chain = prompt | llm | StrOutputParser()

            # Lọc kết quả để đảm bảo bảo mật thông tin khách hàng
            filtered_results = _filter_sensitive_data(results, context)

            # Lấy 3 kết quả tốt nhất làm đầu vào cho việc trả lời câu hỏi
            # Giả định rằng kết quả đã được sắp xếp theo thứ tự ưu tiên từ truy vấn Cypher
            best_results = filtered_results[:3]  # Lấy 3 kết quả đầu tiên (tốt nhất)

            # Log thông tin về số lượng kết quả
            log_info(f"📊 Tổng số kết quả: {len(filtered_results)}, sử dụng 3 kết quả tốt nhất")

            # Kiểm tra xem kết quả có phải là từ GraphRAG agent không
            log_info(f"Kiểm tra cấu trúc dữ liệu từ GraphRAG agent...")

            # Log thông tin chi tiết về kết quả
            for i, result in enumerate(best_results):
                log_info(f"Kết quả {i+1}:")
                for key in result.keys():
                    log_info(f"  - {key}: {str(result[key])[:100]}...")

            # Tổ chức dữ liệu theo sản phẩm và danh mục
            organized_data = _organize_variants_by_product_and_category(best_results)

            # Định dạng dữ liệu đã tổ chức để truyền cho LLM
            formatted_data = _format_organized_data_for_llm(organized_data)

            log_info(f"📋 Formatted organized data: {formatted_data[:500]}...")

            # Thêm thông tin về loại kết quả vào context
            invoke_context = {
                "question": enhanced_message,  # Sử dụng enhanced_message thay vì message
                "context": formatted_data,
                "result_type": result_type
            }

            # Nếu là đơn hàng và có thông tin khách hàng, thêm vào context
            if result_type == "order" and context and 'customer_info' in context:
                customer_info = context.get('customer_info', {})
                customer_name = customer_info.get('name', '')
                customer_id = customer_info.get('id', '')
                if customer_name:
                    invoke_context["customer_name"] = customer_name
                if customer_id:
                    invoke_context["customer_id"] = customer_id

            # Generate response
            response = chain.invoke(invoke_context)

            # Khôi phục temperature ban đầu
            gemini_client._temperature = current_temp

            if response:
                log_info(f"💬 Generated response: {response}")
                return response
            else:
                log_error("No response generated")
                continue

        except Exception as e:
            log_error(f"❌ Error processing results (attempt {attempt + 1}/{max_retries}): {str(e)}")
            if attempt < max_retries - 1:
                time.sleep(retry_delay)
                retry_delay *= 2

    return "Xin lỗi, đã có lỗi khi xử lý kết quả. Vui lòng thử lại sau."
