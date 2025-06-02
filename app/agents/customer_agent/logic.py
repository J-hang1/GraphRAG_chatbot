"""
Customer agent for face verification and customer information
"""
import base64
import numpy as np
from ...utils.logger import log_error
from .face_auth import face_auth_manager
from .customer_db import CustomerDB

class CustomerAgent:
    """Agent xử lý xác minh danh tính và thông tin khách hàng"""

    def __init__(self):
        """Khởi tạo Customer Agent"""
        self.face_auth = face_auth_manager
        self.customer_db = CustomerDB()

    # Phương thức verify_face với đường dẫn file đã bị loại bỏ
    # Xác thực khuôn mặt chỉ được thực hiện thông qua camera (xử lý frame video)

    def process_video_frame(self, frame_data):
        """
        Xử lý frame video từ webcam

        Args:
            frame_data: Dữ liệu frame dạng base64

        Returns:
            dict: Kết quả xác minh danh tính
        """
        try:
            # Giải mã dữ liệu base64
            image_data = frame_data.split(',')[1]
            image_bytes = base64.b64decode(image_data)

            # Chuyển đổi thành mảng numpy
            import cv2
            nparr = np.frombuffer(image_bytes, np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if frame is None:
                return {
                    'success': False,
                    'message': 'Không thể xử lý hình ảnh'
                }

            # Xác minh khuôn mặt với tối ưu hóa real-time
            return self.face_auth.verify_face_realtime(frame)

        except Exception as e:
            log_error(f"Lỗi khi xử lý frame video: {str(e)}")
            return {
                'success': False,
                'message': 'Lỗi khi xử lý hình ảnh'
            }

    # Các phương thức thêm/sửa/xóa đã bị loại bỏ theo yêu cầu
    # Customer agent chỉ có chức năng xác minh khuôn mặt, lấy thông tin khách hàng,
    # và lấy thông tin các đơn hàng của khách

    def get_all_registered_customers(self):
        """
        Lấy danh sách tất cả khách hàng đã đăng ký khuôn mặt

        Returns:
            list: Danh sách khách hàng đã đăng ký khuôn mặt
        """
        try:
            # Lấy danh sách khách hàng
            customers = self.customer_db.get_all_customers_with_embedding()

            return customers

        except Exception as e:
            log_error(f"Lỗi khi lấy danh sách khách hàng: {str(e)}")
            return []

    def get_customer_info(self, customer_id):
        """
        Lấy thông tin khách hàng từ ID

        Args:
            customer_id: ID của khách hàng

        Returns:
            dict: Thông tin khách hàng hoặc None nếu không tìm thấy
        """
        try:
            # Lấy thông tin khách hàng
            customer = self.customer_db.get_customer_info(customer_id)

            return customer

        except Exception as e:
            log_error(f"Lỗi khi lấy thông tin khách hàng: {str(e)}")
            return None

    def get_customer_orders(self, customer_id):
        """
        Lấy danh sách đơn hàng của khách hàng

        Args:
            customer_id: ID của khách hàng

        Returns:
            list: Danh sách đơn hàng
        """
        try:
            # Lấy danh sách đơn hàng
            orders = self.customer_db.get_customer_orders(customer_id)

            return orders

        except Exception as e:
            log_error(f"Lỗi khi lấy danh sách đơn hàng: {str(e)}")
            return []

    def process_message(self, message, context=None):
        """
        Xử lý tin nhắn liên quan đến khách hàng

        Args:
            message: Tin nhắn từ người dùng
            context: Context của cuộc trò chuyện

        Returns:
            str: Phản hồi cho người dùng
        """
        try:
            # Lấy thông tin khách hàng từ context
            customer_id = None
            if context and 'customer' in context and context['customer']:
                customer_id = context['customer'].get('id')

            if not customer_id:
                return "Bạn cần đăng nhập để xem thông tin khách hàng."

            # Lấy thông tin khách hàng
            customer = self.get_customer_info(customer_id)
            if not customer:
                return "Không tìm thấy thông tin khách hàng."

            # Lấy danh sách đơn hàng
            orders = self.get_customer_orders(customer_id)

            # Tạo phản hồi
            response = f"Thông tin khách hàng:\n"
            response += f"- Tên: {customer['name']}\n"
            if 'email' in customer and customer['email']:
                response += f"- Email: {customer['email']}\n"
            if 'phone' in customer and customer['phone']:
                response += f"- Số điện thoại: {customer['phone']}\n"

            if orders:
                response += f"\nĐơn hàng gần đây ({len(orders)}):\n"
                for i, order in enumerate(orders[:3]):  # Chỉ hiển thị 3 đơn hàng gần nhất
                    response += f"{i+1}. Đơn hàng #{order['id']} - Ngày: {order['date']}\n"
                    if 'total' in order and order['total']:
                        response += f"   Tổng tiền: {order['total']:,.0f} VND\n"

                    if 'items' in order and order['items']:
                        response += f"   Số sản phẩm: {len(order['items'])}\n"
            else:
                response += "\nKhách hàng chưa có đơn hàng nào."

            return response

        except Exception as e:
            log_error(f"Lỗi khi xử lý tin nhắn: {str(e)}")
            return "Đã xảy ra lỗi khi xử lý yêu cầu của bạn."
