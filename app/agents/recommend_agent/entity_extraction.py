"""
Module trích xuất thực thể từ câu truy vấn của người dùng
"""
import json
from typing import Dict, Any, Optional
from ...utils.logger import log_info, log_error
from ...utils.llm_counter import count_llm_call
from ...llm_clients import gemini_client

@count_llm_call
def extract_entities(query: str, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Trích xuất các thực thể từ câu truy vấn của người dùng

    Args:
        query: Câu truy vấn của người dùng
        context: Ngữ cảnh bổ sung (thông tin khách hàng, lịch sử chat)

    Returns:
        Dict[str, Any]: Danh sách các thực thể được trích xuất
    """
    log_info("\n🔍 Trích xuất thực thể từ câu truy vấn...")
    log_info(f"📝 Câu truy vấn: {query}")

    # Không cần lấy danh sách sản phẩm và danh mục từ cơ sở dữ liệu nữa
    # vì chúng ta chỉ trích xuất những gì có trong câu truy vấn

    # Tạo prompt để trích xuất thực thể
    prompt = "Bạn là một chuyên gia trích xuất thực thể từ câu truy vấn. Nhiệm vụ của bạn là phân tích câu truy vấn và trích xuất CHÍNH XÁC các thực thể được nhắc đến.\n\n"
    prompt += f"Câu truy vấn: \"{query}\"\n\n"
    prompt += "NGUYÊN TẮC TUYỆT ĐỐI: KHÔNG BAO GIỜ suy luận hoặc dự đoán thông tin không có trong câu truy vấn. Chỉ trích xuất những từ hoặc cụm từ THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n\n"
    prompt += "VÍ DỤ:\n"
    prompt += "- Câu truy vấn: \"Frappuccino có bao nhiêu calo?\"\n"
    prompt += "  + Đúng: entities = [\"Frappuccino\"] (chỉ có Frappuccino được nhắc đến)\n"
    prompt += "  + Sai: entities = [\"Frappuccino\", \"Frappuccino Blended Coffee\", \"Frappuccino Blended Crème\"] (vì các thực thể khác không được nhắc đến)\n\n"
    prompt += "- Câu truy vấn: \"Đồ uống nào giúp giữ ấm tốt vào mùa đông?\"\n"
    prompt += "  + Đúng: entities = [] (vì không có tên sản phẩm, danh mục hoặc biến thể cụ thể nào được nhắc đến, \"Đồ uống\" là một từ khóa chung)\n"
    prompt += "  + Sai: entities = [\"Coffee\", \"Đồ uống\", \"nóng\"] (vì không có thực thể cụ thể nào được nhắc đến)\n\n"
    prompt += "- Câu truy vấn: \"Có loại trà nào có hương vị trái cây không?\"\n"
    prompt += "  + Đúng: entities = [] (vì không có tên sản phẩm, danh mục hoặc biến thể cụ thể nào được nhắc đến, \"trà\" là một từ khóa chung)\n"
    prompt += "  + Sai: entities = [\"trà\", \"Tea\"] (vì không có thực thể cụ thể nào được nhắc đến)\n\n"
    prompt += "- Câu truy vấn: \"So sánh giữa Latte và Mocha\"\n"
    prompt += "  + Đúng: entities = [\"Latte\", \"Mocha\"] (cả hai đều là thực thể cụ thể được nhắc đến)\n"
    prompt += "  + Sai: entities = [\"Latte\", \"Mocha\", \"Espresso\"] (vì Espresso không được nhắc đến)\n\n"
    prompt += "Hãy trích xuất các thông tin sau từ câu truy vấn:\n"
    prompt += "1. Thực thể: CHỈ trích xuất các thực thể cụ thể (tên sản phẩm, tên danh mục, loại biến thể) THỰC SỰ XUẤT HIỆN trong câu truy vấn. Không phân biệt loại thực thể, tất cả đều được đưa vào một mảng duy nhất. Nếu không có thực thể nào được nhắc đến, trả về mảng rỗng.\n"
    prompt += "2. Thông tin cửa hàng: Bất kỳ thông tin nào liên quan đến cửa hàng (địa chỉ, giờ mở cửa, v.v.) THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "3. Thông tin đơn hàng: Bất kỳ thông tin nào liên quan đến đơn hàng (lịch sử đơn hàng, đơn hàng gần đây, v.v.) THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "4. Thuộc tính sản phẩm: Các thuộc tính như giá, kích cỡ, hương vị, v.v. THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "5. Thuộc tính quan tâm: Người dùng quan tâm đến thuộc tính nào? (calo, caffeine, đường, protein, v.v.) THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "6. Giới hạn: Người dùng có giới hạn nào không? (ít calo, nhiều caffeine, v.v.) THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "7. Đối tượng: Người dùng thuộc nhóm đối tượng nào? (người ăn kiêng, người cần năng lượng, v.v.) THỰC SỰ XUẤT HIỆN trong câu truy vấn.\n"
    prompt += "8. Từ khóa: Các từ khóa quan trọng THỰC SỰ CÓ trong câu hỏi.\n\n"
    prompt += "Trả về kết quả dưới dạng JSON với các trường sau:\n"
    prompt += "{\n"
    prompt += "    \"entities\": [],  // Danh sách tất cả các thực thể được nhắc đến (sản phẩm, danh mục, biến thể)\n"
    prompt += "    \"store_info\": false,  // true nếu câu truy vấn liên quan đến thông tin cửa hàng\n"
    prompt += "    \"order_info\": false,  // true nếu câu truy vấn liên quan đến thông tin đơn hàng\n"
    prompt += "    \"product_attributes\": {},  // Các thuộc tính sản phẩm được nhắc đến\n"
    prompt += "    \"attributes_of_interest\": [],  // Thuộc tính người dùng quan tâm (calo, caffeine, đường, protein, v.v.)\n"
    prompt += "    \"constraints\": {},  // Giới hạn của người dùng (ít calo, nhiều caffeine, v.v.)\n"
    prompt += "    \"target_audience\": [],  // Đối tượng người dùng (người ăn kiêng, người cần năng lượng, v.v.)\n"
    prompt += "    \"keywords\": []  // Các từ khóa quan trọng trong câu hỏi\n"
    prompt += "}\n\n"
    prompt += "Chỉ trả về JSON thuần túy, không có văn bản giải thích, không bao quanh bởi dấu backticks hoặc định dạng markdown."

    try:
        # Lưu temperature hiện tại
        current_temp = getattr(gemini_client, '_temperature', 0.0)

        try:
            # Đặt temperature thấp hơn cho việc trích xuất thực thể
            gemini_client._temperature = 0.1

            # Gọi LLM để trích xuất thực thể
            response = gemini_client.generate_text(prompt)

            # Phân tích kết quả JSON
            try:
                # Xử lý trường hợp LLM trả về JSON với định dạng markdown
                response_text = response.strip()

                # Loại bỏ dấu backticks và định dạng markdown nếu có
                if response_text.startswith("```"):
                    # Tìm vị trí của dấu backticks đầu tiên và cuối cùng
                    start_idx = response_text.find("\n", 3) + 1 if response_text.find("\n", 3) > 0 else 3
                    end_idx = response_text.rfind("```")

                    # Trích xuất phần JSON
                    if end_idx > start_idx:
                        response_text = response_text[start_idx:end_idx].strip()
                    else:
                        response_text = response_text[start_idx:].strip()

                # Phân tích JSON
                entities = json.loads(response_text)
                log_info(f"🧠 Trích xuất thực thể thành công: {json.dumps(entities, ensure_ascii=False)}")
                return entities
            except json.JSONDecodeError as e:
                log_error(f"❌ Lỗi khi phân tích kết quả JSON: {response}")
                log_error(f"❌ Chi tiết lỗi: {str(e)}")
                # Trả về kết quả mặc định nếu không thể phân tích JSON
                return {
                    "product_names": [],
                    "category_names": [],
                    "variant_options": [],
                    "store_info": False,
                    "order_info": False,
                    "product_attributes": {}
                }
        finally:
            # Khôi phục temperature ban đầu
            gemini_client._temperature = current_temp
    except Exception as e:
        log_error(f"❌ Lỗi khi trích xuất thực thể: {str(e)}")
        # Trả về kết quả mặc định nếu có lỗi
        return {
            "product_names": [],
            "category_names": [],
            "variant_options": [],
            "store_info": False,
            "order_info": False,
            "product_attributes": {}
        }

# Các phương thức này không còn cần thiết vì chúng ta không cần danh sách tham khảo nữa
# def get_all_products() -> List[str]:
#     """
#     Lấy danh sách tất cả các sản phẩm từ cơ sở dữ liệu
#
#     Returns:
#         List[str]: Danh sách tên sản phẩm
#     """
#     try:
#         query = """
#         MATCH (p:Product)
#         RETURN p.name as product_name
#         """
#         results = execute_query(query)
#         return [result["product_name"] for result in results if result["product_name"]]
#     except Exception as e:
#         log_error(f"❌ Lỗi khi lấy danh sách sản phẩm: {str(e)}")
#         return []
#
# def get_all_categories() -> List[str]:
#     """
#     Lấy danh sách tất cả các danh mục từ cơ sở dữ liệu
#
#     Returns:
#         List[str]: Danh sách tên danh mục
#     """
#     try:
#         query = """
#         MATCH (c:Category)
#         RETURN c.name_cat as category_name
#         """
#         results = execute_query(query)
#         return [result["category_name"] for result in results if result["category_name"]]
#     except Exception as e:
#         log_error(f"❌ Lỗi khi lấy danh sách danh mục: {str(e)}")
#         return []
#
# def get_all_variant_options() -> List[str]:
#     """
#     Lấy danh sách tất cả các loại biến thể từ cơ sở dữ liệu
#
#     Returns:
#         List[str]: Danh sách loại biến thể
#     """
#     try:
#         query = """
#         MATCH (v:Variant)
#         RETURN DISTINCT v.`Beverage Option` as variant_option
#         """
#         results = execute_query(query)
#         return [result["variant_option"] for result in results if result["variant_option"]]
#     except Exception as e:
#         log_error(f"❌ Lỗi khi lấy danh sách loại biến thể: {str(e)}")
#         return []




