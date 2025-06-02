"""
Database operations for Customer Agent
"""
import json
from ...neo4j_client.connection import execute_query, execute_query_with_semaphore
from ...utils.logger import log_info, log_error, log_warning

class CustomerDB:
    """Class xử lý các thao tác cơ sở dữ liệu liên quan đến khách hàng"""

    def __init__(self):
        """Khởi tạo CustomerDB"""
        pass

    def get_customer_info(self, customer_id):
        """
        Lấy thông tin khách hàng theo ID

        Args:
            customer_id (str): ID của khách hàng

        Returns:
            dict: Thông tin khách hàng hoặc None nếu không tìm thấy
        """
        try:
            if not customer_id:
                log_error("customer_id là None hoặc rỗng")
                return None

            # Thử tìm với customer_id dạng số trước
            try:
                customer_id_int = int(customer_id)
                log_info(f"Thử tìm khách hàng với ID dạng số: {customer_id_int}")

                query = """
                MATCH (c:Customer)
                WHERE c.id = $customer_id
                RETURN c {.*} as customer
                LIMIT 1
                """

                result = execute_query_with_semaphore(query, {'customer_id': customer_id_int}, use_cache=False)

                if result and 'customer' in result[0]:
                    log_info(f"Tìm thấy khách hàng với ID số {customer_id_int}")
                    return result[0]['customer']
            except (ValueError, TypeError):
                log_info(f"customer_id '{customer_id}' không phải dạng số")

            # Nếu không tìm thấy với ID số, thử với ID dạng chuỗi
            log_info(f"Thử tìm khách hàng với ID dạng chuỗi: {customer_id}")

            query = """
            MATCH (c:Customer)
            WHERE c.id = $customer_id
            RETURN c {.*} as customer
            LIMIT 1
            """

            result = execute_query_with_semaphore(query, {'customer_id': str(customer_id)}, use_cache=False)

            if result and 'customer' in result[0]:
                log_info(f"Tìm thấy khách hàng với ID chuỗi {customer_id}")
                return result[0]['customer']

            log_warning(f"Không tìm thấy khách hàng với ID {customer_id} (cả dạng số và chuỗi)")
            return None

        except Exception as e:
            log_error(f"Lỗi khi lấy thông tin khách hàng {customer_id}: {str(e)}")
            return None

    def get_customer_orders(self, customer_id):
        """
        Lấy danh sách đơn hàng của khách hàng

        Args:
            customer_id (str): ID của khách hàng

        Returns:
            list: Danh sách đơn hàng
        """
        try:
            if not customer_id:
                log_error("customer_id là None hoặc rỗng")
                return []

            # Thử chuyển đổi customer_id thành số nguyên
            try:
                customer_id_int = int(customer_id)
            except (ValueError, TypeError):
                log_error(f"Không thể chuyển đổi customer_id '{customer_id}' thành số nguyên")
                return []

            # Lấy tất cả các đơn hàng của khách hàng
            query = """
            MATCH (c:Customer {id: $customer_id})
            OPTIONAL MATCH (o:Order)
            WHERE o.customer_id = $customer_id
            OPTIONAL MATCH (od:Order_Detail)
            WHERE od.order_id = o.id
            OPTIONAL MATCH (od)-[:VARIANT_ID]->(v:Variant)
            OPTIONAL MATCH (v)-[:PRODUCT_ID]->(p:Product)
            WITH o, od, v, p
            ORDER BY o.order_date DESC, o.id
            WITH o, collect({
                id: od.id,
                variant_id: CASE WHEN v IS NOT NULL THEN v.id ELSE null END,
                variant_name: CASE WHEN v IS NOT NULL THEN v.name ELSE null END,
                product_id: CASE WHEN p IS NOT NULL THEN p.id ELSE null END,
                product_name: CASE WHEN p IS NOT NULL THEN p.name ELSE null END,
                price: CASE WHEN v IS NOT NULL THEN v.price ELSE 0 END,
                quantity: CASE WHEN od IS NOT NULL THEN od.quantity ELSE 0 END,
                rate: CASE WHEN od IS NOT NULL THEN od.rate ELSE 0 END
            }) as order_items
            RETURN o {
                .*,
                items: [item IN order_items WHERE item.id IS NOT NULL],
                date: o.order_date
            } as order
            ORDER BY o.order_date DESC
            """

            result = execute_query_with_semaphore(query, {'customer_id': customer_id_int}, use_cache=False)

            if not result:
                log_info(f"Không tìm thấy đơn hàng nào cho khách hàng {customer_id}")
                return []

            # Xử lý kết quả
            orders = []
            for record in result:
                if 'order' in record:
                    order = record['order']
                    
                    # Đảm bảo các trường bắt buộc có giá trị mặc định
                    order['date'] = order.get('date', '')
                    order['items'] = order.get('items', [])
                    
                    # Xử lý từng item trong đơn hàng
                    for item in order['items']:
                        item['price'] = item.get('price', 0)
                        item['quantity'] = item.get('quantity', 0)
                        item['rate'] = item.get('rate', 0)
                        item['variant_name'] = item.get('variant_name', '')
                        item['product_name'] = item.get('product_name', '')
                    
                    orders.append(order)

            log_info(f"Đã lấy {len(orders)} đơn hàng cho khách hàng {customer_id}")
            return orders

        except Exception as e:
            log_error(f"Lỗi khi lấy danh sách đơn hàng của khách hàng {customer_id}: {str(e)}")
            return []

    def get_customer_embedding(self, customer_id):
        """
        Lấy vector đặc trưng khuôn mặt của khách hàng

        Args:
            customer_id (str): ID của khách hàng

        Returns:
            list: Danh sách vector đặc trưng khuôn mặt
        """
        try:
            query = """
            MATCH (c:Customer {id: $customer_id})
            RETURN c.embedding as embedding
            """

            result = execute_query_with_semaphore(query, {'customer_id': customer_id}, use_cache=True)

            if not result or 'embedding' not in result[0] or not result[0]['embedding']:
                return []

            # Chuyển đổi từ chuỗi JSON thành list
            try:
                embeddings = json.loads(result[0]['embedding'])
                return embeddings
            except json.JSONDecodeError:
                log_error(f"Lỗi khi parse embedding của khách hàng {customer_id}")
                return []

        except Exception as e:
            log_error(f"Lỗi khi lấy embedding của khách hàng {customer_id}: {str(e)}")
            return []

    def get_all_customer_orders(self, customer_id):
        """
        Lấy toàn bộ danh sách đơn hàng của khách hàng để hiển thị trong popup "Thông tin toàn bộ đơn hàng"

        Args:
            customer_id (str): ID của khách hàng

        Returns:
            list: Toàn bộ danh sách đơn hàng
        """
        try:
            # Chuyển đổi customer_id thành số nguyên
            try:
                customer_id_int = int(customer_id)
            except (ValueError, TypeError):
                log_error(f"Không thể chuyển đổi customer_id '{customer_id}' thành số nguyên")
                return []

            # Đầu tiên, lấy tất cả các đơn hàng của khách hàng (không phải chi tiết đơn hàng)
            count_query = """
            MATCH (c:Customer {id: $customer_id})
            OPTIONAL MATCH (o:Order)
            WHERE o.customer_id = $customer_id
            RETURN count(o) as order_count
            """
            count_result = execute_query_with_semaphore(count_query, {'customer_id': customer_id_int}, use_cache=True)
            order_count = count_result[0]["order_count"] if count_result else 0
            log_info(f"Số lượng đơn hàng thực tế: {order_count}")

            # Sau đó, lấy chi tiết đơn hàng cho mỗi đơn hàng
            query = """
            MATCH (c:Customer {id: $customer_id})
            OPTIONAL MATCH (o:Order)
            WHERE o.customer_id = $customer_id
            OPTIONAL MATCH (od:Order_Detail)
            WHERE od.order_id = o.id
            OPTIONAL MATCH (od)-[:VARIANT_ID]->(v:Variant)
            OPTIONAL MATCH (v)-[:PRODUCT_ID]->(p:Product)
            WITH o, od, v, p
            ORDER BY o.order_date DESC, o.id
            WITH o, collect({
                id: od.id,
                variant_id: CASE WHEN v IS NOT NULL THEN v.id ELSE null END,
                variant_name: CASE WHEN v IS NOT NULL THEN v.name ELSE null END,
                product_id: CASE WHEN p IS NOT NULL THEN p.id ELSE null END,
                product_name: CASE WHEN p IS NOT NULL THEN p.name ELSE null END,
                price: CASE WHEN v IS NOT NULL THEN v.price ELSE null END,
                quantity: CASE WHEN od IS NOT NULL THEN od.quantity ELSE null END,
                rate: CASE WHEN od IS NOT NULL THEN od.rate ELSE null END
            }) as order_items
            RETURN o {
                .*,
                items: [item IN order_items WHERE item.id IS NOT NULL]
            } as order
            ORDER BY o.order_date DESC
            """

            result = execute_query_with_semaphore(query, {'customer_id': customer_id_int}, use_cache=True)

            if not result:
                log_error(f"Không tìm thấy đơn hàng nào cho khách hàng {customer_id}")
                return []

            # Xử lý kết quả
            orders = []
            for record in result:
                if 'order' in record:
                    order = record['order']
                    # Đảm bảo định dạng ngày tháng
                    if 'order_date' in order:
                        order['date'] = order['order_date']  # Thêm trường date để tương thích với template

                    # Đảm bảo items là list
                    if 'items' in order:
                        if order['items'] is None:
                            log_error(f"Trường 'items' là None, đang chuyển đổi thành list rỗng")
                            order['items'] = []
                        elif callable(order['items']):
                            log_error(f"Trường 'items' là một hàm, đang chuyển đổi thành list rỗng")
                            order['items'] = []
                        elif not isinstance(order['items'], list):
                            log_error(f"Trường 'items' không phải là list, đang chuyển đổi")
                            try:
                                order['items'] = list(order['items'])
                            except:
                                order['items'] = []
                        for j, item in enumerate(order['items']):
                            if 'price' in item and item['price'] is None:
                                log_warning(f"Đơn hàng có item {j} với giá trị price là None, đang đặt giá trị mặc định")
                                item['price'] = 0
                            if 'quantity' in item and item['quantity'] is None:
                                log_warning(f"Đơn hàng có item {j} với giá trị quantity là None, đang đặt giá trị mặc định")
                                item['quantity'] = 0
                            if 'rate' in item and item['rate'] is None:
                                log_warning(f"Đơn hàng có item {j} với giá trị rate là None, đang đặt giá trị mặc định")
                                item['rate'] = 0
                    else:
                        order['items'] = []

                    orders.append(order)
            return orders

        except Exception as e:
            log_error(f"Lỗi khi lấy toàn bộ đơn hàng của khách hàng {customer_id}: {str(e)}")
            return []

    def get_all_customers_with_embedding(self):
        """
        Lấy danh sách tất cả khách hàng có vector đặc trưng khuôn mặt

        Returns:
            list: Danh sách khách hàng có vector đặc trưng khuôn mặt
        """
        try:
            query = """
            MATCH (c:Customer)
            WHERE c.embedding IS NOT NULL
            RETURN c.id as id, c.name as name
            """

            result = execute_query_with_semaphore(query, use_cache=True)

            if not result:
                return []

            return result

        except Exception as e:
            log_error(f"Lỗi khi lấy danh sách khách hàng có embedding: {str(e)}")
            return []

    def verify_customer_credentials(self, customer_id, password):
        """
        Xác thực thông tin đăng nhập của khách hàng

        Args:
            customer_id (str): ID của khách hàng
            password (str): Mật khẩu của khách hàng

        Returns:
            dict: Thông tin khách hàng nếu xác thực thành công, None nếu thất bại
        """
        try:
            # Chuyển đổi customer_id thành số nguyên nếu có thể
            try:
                customer_id_int = int(customer_id)
            except (ValueError, TypeError):
                log_error(f"Không thể chuyển đổi customer_id '{customer_id}' thành số nguyên")
                customer_id_int = customer_id  # Giữ nguyên giá trị nếu không thể chuyển đổi

            # Truy vấn thông tin khách hàng với ID và mật khẩu
            query = """
            MATCH (c:Customer)
            WHERE c.id = $customer_id
            RETURN c {.*} as customer
            LIMIT 1
            """

            result = execute_query_with_semaphore(query, {'customer_id': customer_id_int}, use_cache=False)

            if not result or 'customer' not in result[0]:
                log_warning(f"Không tìm thấy khách hàng với ID {customer_id}")
                return None

            customer = result[0]['customer']

            # Kiểm tra mật khẩu
            # Lưu ý: Trong môi trường thực tế, mật khẩu nên được mã hóa và so sánh an toàn
            # Đây là triển khai đơn giản cho mục đích demo
            stored_password = customer.get('password')

            # Nếu khách hàng không có mật khẩu trong DB, sử dụng ID làm mật khẩu mặc định
            if not stored_password:
                stored_password = str(customer_id)

            if password == stored_password:
                log_info(f"Xác thực thành công cho khách hàng {customer_id}")
                return customer
            else:
                log_warning(f"Mật khẩu không chính xác cho khách hàng {customer_id}")
                return None

        except Exception as e:
            log_error(f"Lỗi khi xác thực thông tin đăng nhập của khách hàng {customer_id}: {str(e)}")
            return None