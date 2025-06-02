"""
Module chứa từ điển ánh xạ từ đồng nghĩa cho các thực thể và thuộc tính trong Neo4j
"""
# Phần còn lại của file được chuyển từ app\services\entity_synonyms.py
from typing import Dict, List

def get_entity_synonyms() -> Dict[str, List[str]]:
    """
    Trả về từ điển ánh xạ các từ đồng nghĩa cho thực thể và thuộc tính.
    Key là thuật ngữ chuẩn trong schema, value là list các từ đồng nghĩa.

    Returns:
        Dict[str, List[str]]: Từ điển ánh xạ từ đồng nghĩa
    """
    return {
        # Product Names (Tên sản phẩm)
        'Banana Chocolate Smoothie': ['sinh tố chuối sô-cô-la', 'smoothie chuối socola', 'sinh tố chuối chocolate'],
        'Brewed Coffee': ['cà phê phin', 'cà phê pha', 'cà phê đen', 'filter coffee', 'drip coffee'],
        'Caffè Americano': ['cà phê americano', 'americano', 'cafe americano'],
        'Caffè Latte': ['cà phê latte', 'cafe latte', 'latte', 'cà phê sữa kiểu ý'],
        'Caffè Mocha': ['cà phê mocha', 'cafe mocha', 'mocha', 'cà phê sô-cô-la'],
        'Cappuccino': ['cà phê cappuccino', 'cafe cappuccino', 'cà phê ý'],
        'Caramel Apple Spice': ['táo caramel nóng', 'đồ uống táo caramel', 'apple caramel'],
        'Caramel Frappuccino': ['frappuccino caramel', 'caramel đá xay', 'cà phê caramel đá xay'],
        'Caramel Light Frappuccino': ['frappuccino caramel ít đường', 'caramel đá xay light', 'light caramel frappuccino'],
        'Caramel Macchiato': ['caramel macchiato', 'macchiato caramel', 'cà phê macchiato caramel'],
        'Coffee Frappuccino': ['cà phê đá xay', 'coffee đá xay', 'frappuccino cà phê'],
        'Coffee Light Frappuccino': ['cà phê đá xay ít đường', 'coffee đá xay light', 'frappuccino cà phê light'],
        'Espresso': ['cà phê espresso', 'cafe espresso', 'cà phê ý đậm'],
        'Hot Chocolate': ['sô-cô-la nóng', 'chocolate nóng', 'ca cao nóng'],
        'Iced Brewed Coffee': ['cà phê đen đá', 'cà phê phin đá', 'cafe đá'],
        'Iced Brewed Coffee With Milk': ['cà phê sữa đá', 'cafe sữa đá', 'cà phê đá có sữa'],
        'Java Chip Frappuccino': ['java chip đá xay', 'frappuccino java chip', 'cà phê java chip đá xay'],
        'Mocha Frappuccino': ['mocha đá xay', 'frappuccino mocha', 'cà phê mocha đá xay'],
        'Mocha Light Frappuccino': ['mocha đá xay ít đường', 'frappuccino mocha light', 'mocha light đá xay'],
        'Orange Mango Banana Smoothie': ['sinh tố cam xoài chuối', 'smoothie cam xoài chuối'],
        'Shaken Iced Tazo Tea': ['trà tazo đá lắc', 'trà lắc đá tazo', 'tazo tea đá'],
        'Shaken Iced Tazo Tea Lemonade': ['trà tazo chanh đá lắc', 'trà chanh tazo đá', 'tazo tea chanh'],
        'Skinny Latte (Any Flavour)': ['latte ít béo', 'latte không đường', 'latte ít calo'],
        'Strawberries & Crème': ['kem dâu đá xay', 'dâu kem đá xay', 'strawberry cream frappuccino'],
        'Strawberry Banana Smoothie': ['sinh tố dâu chuối', 'smoothie dâu chuối'],
        'Tazo Chai Tea Latte': ['trà sữa chai tazo', 'chai tea latte', 'trà chai tazo'],
        'Tazo Green Tea Latte': ['trà xanh sữa tazo', 'green tea latte', 'latte trà xanh'],
        'Vanilla Bean': ['vanilla đá xay', 'vanilla bean frappuccino', 'kem vanilla đá xay'],
        'Vanilla Latte': ['latte vanilla', 'cà phê vanilla', 'cafe vanilla'],
        'White Chocolate Mocha': ['mocha sô-cô-la trắng', 'white mocha', 'cà phê mocha trắng'],

        # Node Labels (Thực thể)
        'Categorie': ['danh mục', 'loại', 'nhóm', 'category', 'categories', 'phân loại', 'thể loại'],
        'Product': ['sản phẩm', 'đồ uống', 'thức uống', 'nước uống', 'drink', 'beverage', 'item'],
        'Variant': ['biến thể', 'phiên bản', 'size', 'kích thước', 'variant', 'option', 'tùy chọn'],
        'Customer': ['khách hàng', 'người dùng', 'user', 'client', 'consumer', 'guest'],
        'Order': ['đơn hàng', 'hóa đơn', 'order', 'bill', 'receipt', 'purchase'],
        'OrderDetail': ['chi tiết đơn hàng', 'order detail', 'order item', 'item detail'],
        'Store': ['cửa hàng', 'chi nhánh', 'shop', 'store', 'branch', 'location'],

        # Tên các danh mục (Categories)
        'Classic Espresso Drinks': ['đồ uống espresso cổ điển', 'espresso classic', 'classic espresso', 'thức uống espresso truyền thống', 'cà phê espresso'],
        'Coffee': ['cà phê', 'cafe', 'coffee', 'thức uống cà phê', 'đồ uống cà phê'],
        'Frappuccino Blended Coffee': ['frappuccino cà phê', 'cà phê frappuccino', 'coffee frappuccino', 'frappuccino đá xay', 'cà phê đá xay'],
        'Frappuccino Blended Crème': ['frappuccino kem', 'cream frappuccino', 'frappuccino không cà phê', 'kem đá xay', 'đồ uống kem đá xay'],
        'Frappuccino Light Blended Coffee': ['frappuccino light', 'light frappuccino', 'frappuccino ít calo', 'frappuccino không đường', 'cà phê đá xay ít đường'],
        'Shaken Iced Beverages': ['đồ uống lắc đá', 'thức uống đá lắc', 'shaken drinks', 'đồ uống kiểu lắc', 'thức uống lắc'],
        'Signature Espresso Drinks': ['đồ uống espresso đặc trưng', 'thức uống espresso signature', 'signature coffee', 'cà phê espresso đặc biệt', 'espresso signature'],
        'Smoothies': ['sinh tố', 'nước ép trái cây', 'đồ uống xay', 'smoothie', 'nước trái cây'],
        'Tazo Tea Drinks': ['trà tazo', 'đồ uống trà', 'tazo tea', 'thức uống trà', 'trà'],

        # Biến thể (Variants/Sizes)
        'Short': ['nhỏ', 'size s', 'cỡ nhỏ', 'short size'],
        'Tall': ['vừa', 'size m', 'cỡ vừa', 'tall size'],
        'Grande': ['lớn', 'size l', 'cỡ lớn', 'grande size'],
        'Venti': ['cực lớn', 'size xl', 'cỡ cực lớn', 'venti size'],

        # Properties của Categorie
        'name_cat': ['tên danh mục', 'tên loại', 'category name', 'tên thể loại'],
        'description': ['mô tả', 'miêu tả', 'giới thiệu', 'desc', 'chi tiết'],

        # Properties của Product
        'name_product': ['tên sản phẩm', 'tên đồ uống', 'product name', 'beverage name', 'drink name'],
        'descriptions': ['mô tả sản phẩm', 'miêu tả sản phẩm', 'product description', 'giới thiệu sản phẩm'],
        'link_image': ['ảnh', 'hình', 'image', 'picture', 'photo', 'link ảnh', 'đường dẫn ảnh'],
        'categories_id': ['mã danh mục', 'category id', 'mã loại', 'id danh mục'],

        # Properties của Variant
        'Beverage Option': ['size', 'kích cỡ', 'cỡ', 'option', 'tùy chọn', 'loại'],
        'price': ['giá', 'giá tiền', 'đơn giá', 'cost', 'amount', 'giá bán'],
        'calories': ['calo', 'cal', 'năng lượng', 'calories', 'calorie'],
        'caffeine_mg': ['caffeine', 'cafein', 'chất caffeine', 'hàm lượng caffeine'],
        'protein_g': ['protein', 'đạm', 'chất đạm', 'hàm lượng protein'],
        'sugars_g': ['đường', 'sugar', 'chất đường', 'hàm lượng đường', 'carbohydrate'],
        'dietary_fibre_g': ['chất xơ', 'fiber', 'fibre', 'dietary fiber', 'hàm lượng chất xơ'],
        'vitamin_a': ['vitamin a', 'vita a', 'hàm lượng vitamin a'],
        'vitamin_c': ['vitamin c', 'vita c', 'hàm lượng vitamin c'],
        'sales_rank': ['xếp hạng bán', 'rank', 'ranking', 'thứ hạng bán'],
        'product_id': ['mã sản phẩm', 'product id', 'id sản phẩm'],

        # Properties của Customer
        'name': ['tên khách hàng', 'họ tên', 'fullname', 'customer name'],
        'sex': ['giới tính', 'gender', 'phái'],
        'age': ['tuổi', 'age', 'độ tuổi'],
        'location': ['địa điểm', 'nơi ở', 'location', 'place', 'address'],
        'picture': ['ảnh đại diện', 'avatar', 'profile picture', 'photo'],
        'embedding': ['vector', 'embedding vector', 'customer vector'],

        # Properties của Order
        'customer_id': ['mã khách hàng', 'id khách hàng', 'customer id'],
        'store_id': ['mã cửa hàng', 'id cửa hàng', 'store id', 'shop id'],
        'order_date': ['ngày đặt', 'ngày mua', 'date', 'purchase date', 'thời gian đặt'],

        # Properties của OrderDetail
        'order_id': ['mã đơn hàng', 'id đơn hàng', 'order id'],
        'variant_id': ['mã biến thể', 'id biến thể', 'variant id'],
        'quantity': ['số lượng', 'quantity', 'amount', 'qty'],
        'rate': ['đánh giá', 'rating', 'score', 'star rating'],

        # Properties của Store
        'name_store': ['tên cửa hàng', 'tên chi nhánh', 'store name', 'shop name'],
        'address': ['địa chỉ', 'location', 'place', 'store address'],
        'phone': ['số điện thoại', 'sđt', 'phone number', 'tel', 'telephone'],
        'open_close': ['giờ mở cửa', 'giờ làm việc', 'opening hours', 'business hours', 'working hours'],

        # Relationships (Mối quan hệ)
        'HAS_CATEGORIE': ['thuộc danh mục', 'thuộc loại', 'in category', 'has category'],
        'HAS_PRODUCT': ['có sản phẩm', 'belongs to product', 'của sản phẩm'],
        'HAS_CUSTOMER': ['của khách hàng', 'belongs to customer', 'customer order'],
        'HAS_STORE': ['tại cửa hàng', 'at store', 'store order'],
        'HAS_ORDER': ['thuộc đơn hàng', 'belongs to order', 'of order'],
        'HAS_VARIANT': ['có biến thể', 'has variant', 'variant detail'],

        # Common attributes (Thuộc tính chung)
        'id': ['mã', 'code', 'number', 'identifier'],

        # Beverage Options - Sizes (Kích cỡ)
        'Short': ['ly nhỏ', 'cỡ nhỏ nhất', 'size s', 'size nhỏ', 'short size', 'nhỏ'],
        'Tall': ['ly vừa', 'cỡ vừa', 'size m', 'size medium', 'tall size', 'vừa'],
        'Grande': ['ly lớn', 'cỡ lớn', 'size l', 'size large', 'grande size', 'lớn'],
        'Venti': ['ly cực lớn', 'cỡ đặc biệt', 'size xl', 'size extra large', 'venti size', 'cực lớn'],
        
        # Beverage Options - Milk Types (Loại sữa)
        '2% Milk': ['sữa 2%', 'sữa tách kem một phần', 'sữa ít béo', 'two percent milk', 'reduced fat milk'],
        'Whole Milk': ['sữa nguyên kem', 'sữa béo', 'sữa tươi nguyên chất', 'full cream milk', 'regular milk'],
        'Nonfat Milk': ['sữa không béo', 'sữa tách kem', 'sữa 0%', 'skim milk', 'fat free milk'],
        'Soymilk': ['sữa đậu nành', 'sữa đậu', 'sữa thực vật', 'soy milk', 'soy beverage'],

        # Beverage Options - Size with Milk Combinations (Kết hợp kích cỡ và sữa)
        'Grande Nonfat Milk': ['ly lớn sữa không béo', 'grande sữa tách kem', 'size l sữa không béo', 'large skim milk'],
        'Short Nonfat Milk': ['ly nhỏ sữa không béo', 'short sữa tách kem', 'size s sữa không béo', 'small skim milk'],
        'Tall Nonfat Milk': ['ly vừa sữa không béo', 'tall sữa tách kem', 'size m sữa không béo', 'medium skim milk'],
        'Venti Nonfat Milk': ['ly cực lớn sữa không béo', 'venti sữa tách kem', 'size xl sữa không béo', 'extra large skim milk'],

        # Beverage Options - Espresso Shots (Số shot espresso)
        'Solo': ['một shot', 'đơn', 'một phần', 'single shot', 'one shot espresso'],
        'Doppio': ['hai shot', 'đôi', 'hai phần', 'double shot', 'two shots espresso']
    }
