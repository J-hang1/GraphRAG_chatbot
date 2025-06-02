"""
Module chứa các bảng ánh xạ từ khóa tiếng Việt sang tiếng Anh và ngược lại
Dựa trên cấu trúc database thực tế
"""

# Bảng ánh xạ từ khóa tiếng Việt sang tiếng Anh
VIETNAMESE_TO_ENGLISH_MAPPING = {
    # Bảng Categories
    "id danh mục": ["Id", "Categories_id"],
    "tên danh mục": ["Name_Cat"],
    "mô tả danh mục": ["Description"],

    # Bảng Product
    "id sản phẩm": ["Id", "Product_id"],
    "tên sản phẩm": ["Name_Product"],
    "mô tả sản phẩm": ["Descriptions"],
    "link ảnh": ["Link_Image"],

    # Bảng Variant
    "tùy chọn đồ uống": ["Beverage Option"],
    "calo": ["Calories"],
    "chất xơ": ["Dietary_Fibre_g"],
    "đường": ["Sugars_g"],
    "protein": ["Protein_g"],
    "vitamin a": ["Vitamin_A"],
    "vitamin c": ["Vitamin_C"],
    "caffeine": ["Caffeine_mg"],
    "đơn giá": ["Price"],
    "bán chạy": ["Sales_rank"],

    # Bảng Store
    "id cửa hàng": ["Id", "Store_id"],
    "tên cửa hàng": ["Name_Store"],
    "địa chỉ": ["Address", "location"],
    "số điện thoại": ["Phone"],
    "giờ mở cửa đóng cửa": ["Open_Close"],

    # Bảng Orders
    "id đơn hàng": ["Id", "Order_id"],
    "id khách hàng": ["Customer_id", "id"],
    "ngày đặt hàng": ["Order_date"],

    # Bảng Order_detail
    "số lượng": ["Quantity"],
    "đánh giá": ["Rate"],

    # Bảng customers
    "tên khách hàng": ["name"],
    "giới tính": ["sex"],
    "tuổi": ["age"],
    "ảnh": ["picture"],
    "embedding": ["embedding"],
}

# Bảng ánh xạ ngược từ tiếng Anh sang tiếng Việt
ENGLISH_TO_VIETNAMESE_MAPPING = {
    # Bảng Categories
    "Id": "id danh mục",
    "Categories_id": "id danh mục",
    "Name_Cat": "tên danh mục",
    "Description": "mô tả danh mục",

    # Bảng Product
    "Product_id": "id sản phẩm",
    "Name_Product": "tên sản phẩm",
    "Descriptions": "mô tả sản phẩm",
    "Link_Image": "link ảnh",

    # Bảng Variant
    "Beverage Option": "tùy chọn đồ uống",
    "Calories": "calo",
    "Dietary_Fibre_g": "chất xơ",
    "Sugars_g": "đường",
    "Protein_g": "protein",
    "Vitamin_A": "vitamin a",
    "Vitamin_C": "vitamin c",
    "Caffeine_mg": "caffeine",
    "Price": "đơn giá",
    "Sales_rank": "bán chạy",

    # Bảng Store
    "Store_id": "id cửa hàng",
    "Name_Store": "tên cửa hàng",
    "Address": "địa chỉ",
    "Phone": "số điện thoại",
    "Open_Close": "giờ mở cửa đóng cửa",

    # Bảng Orders
    "Order_id": "id đơn hàng",
    "Customer_id": "id khách hàng",
    "Order_date": "ngày đặt hàng",

    # Bảng Order_detail
    "Quantity": "số lượng",
    "Rate": "đánh giá",

    # Bảng customers
    "id": "id khách hàng",
    "name": "tên khách hàng",
    "sex": "giới tính",
    "age": "tuổi",
    "location": "địa chỉ",
    "picture": "ảnh",
    "embedding": "embedding",
}

def translate_vietnamese_to_english(vietnamese_term):
    """Dịch từ tiếng Việt sang tiếng Anh sử dụng bảng ánh xạ"""
    # Chuẩn hóa từ khóa (lowercase)
    vietnamese_term = vietnamese_term.lower()

    # Tìm trong bảng ánh xạ
    if vietnamese_term in VIETNAMESE_TO_ENGLISH_MAPPING:
        return VIETNAMESE_TO_ENGLISH_MAPPING[vietnamese_term]

    # Tìm kiếm một phần
    for vn_term, en_terms in VIETNAMESE_TO_ENGLISH_MAPPING.items():
        if vn_term in vietnamese_term or vietnamese_term in vn_term:
            return en_terms

    # Nếu không tìm thấy, trả về từ gốc
    return [vietnamese_term]

def translate_english_to_vietnamese(english_term):
    """Dịch từ tiếng Anh sang tiếng Việt sử dụng bảng ánh xạ"""
    # Chuẩn hóa từ khóa (lowercase)
    english_term = english_term.lower()

    # Tìm trong bảng ánh xạ
    if english_term in ENGLISH_TO_VIETNAMESE_MAPPING:
        return ENGLISH_TO_VIETNAMESE_MAPPING[english_term]

    # Nếu không tìm thấy, trả về từ gốc
    return english_term
