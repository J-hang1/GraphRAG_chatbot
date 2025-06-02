"""
Order routes for order management
"""
from flask import request, jsonify, session
from . import create_blueprint, APIError
from ..utils.logger import log_info, log_error
from ..utils.middleware import rate_limit, log_request, init_request_context
from ..agents.order_agent.logic import OrderAgent
from ..utils.response_formatter import formatter

# Create blueprint
bp = create_blueprint('order')

@bp.route('/orders', methods=['GET'])
@log_request
def get_orders():
    """Lấy danh sách đơn hàng"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Bạn chưa đăng nhập'
        }), 401

    try:
        # Lấy danh sách đơn hàng
        order_agent = OrderAgent()
        orders = order_agent.get_orders(user_id)

        return jsonify({
            'success': True,
            'orders': orders
        })

    except Exception as e:
        log_error(f"Lỗi khi lấy danh sách đơn hàng: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Đã xảy ra lỗi khi lấy danh sách đơn hàng'
        }), 500

@bp.route('/orders/<order_id>', methods=['GET'])
@log_request
def get_order(order_id):
    """Lấy thông tin chi tiết đơn hàng"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Bạn chưa đăng nhập'
        }), 401

    try:
        # Lấy thông tin đơn hàng
        order_agent = OrderAgent()
        order = order_agent.get_order_details(order_id, user_id)

        if order:
            return jsonify({
                'success': True,
                'order': order
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy đơn hàng'
            }), 404

    except Exception as e:
        log_error(f"Lỗi khi lấy thông tin đơn hàng: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Đã xảy ra lỗi khi lấy thông tin đơn hàng'
        }), 500

@bp.route('/orders', methods=['POST'])
@log_request
@rate_limit
@init_request_context
def create_order():
    """Tạo đơn hàng mới"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Bạn chưa đăng nhập'
        }), 401

    # Lấy dữ liệu đơn hàng từ request
    data = request.get_json()
    if not data:
        raise APIError('Dữ liệu đơn hàng không hợp lệ', 400)

    # Kiểm tra các trường bắt buộc
    if 'items' not in data or not isinstance(data['items'], list) or len(data['items']) == 0:
        raise APIError('Đơn hàng phải có ít nhất một sản phẩm', 400)

    try:
        # Tạo đơn hàng mới
        order_agent = OrderAgent()
        order = order_agent.create_order(user_id, data)

        return jsonify({
            'success': True,
            'message': 'Đơn hàng đã được tạo thành công',
            'order': order
        })

    except Exception as e:
        log_error(f"Lỗi khi tạo đơn hàng: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Đã xảy ra lỗi khi tạo đơn hàng'
        }), 500

@bp.route('/api/customer-orders', methods=['GET'])
@log_request
def get_customer_orders_api():
    """API endpoint để lấy thông tin đơn hàng của khách hàng đã đăng nhập"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id or user_id == 'guest':
        return formatter.unauthorized('Bạn chưa đăng nhập')

    try:
        # Lấy thông tin đơn hàng từ Neo4j
        from ..agents.customer_agent.customer_db import CustomerDB
        customer_db = CustomerDB()

        log_info(f"Đang lấy thông tin đơn hàng cho khách hàng {user_id}")

        # Lấy 2 đơn hàng gần nhất
        recent_orders = customer_db.get_customer_orders(user_id)

        # Lấy tất cả đơn hàng
        all_orders = customer_db.get_all_customer_orders(user_id)

        log_info(f"Đã lấy {len(recent_orders)} đơn hàng gần nhất và {len(all_orders)} tổng số đơn hàng")

        return formatter.success(data={
            'recent_orders': recent_orders,
            'all_orders': all_orders
        })

    except Exception as e:
        log_error(f"Lỗi khi lấy thông tin đơn hàng: {str(e)}")
        return formatter.error(
            message='Đã xảy ra lỗi khi lấy thông tin đơn hàng',
            status_code=500,
            error_code='ORDER_FETCH_ERROR'
        )
