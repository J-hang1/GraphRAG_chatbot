"""
Customer routes for face authentication and customer information
"""
import os
from datetime import datetime
from flask import request, render_template, current_app, session, jsonify, redirect
from werkzeug.utils import secure_filename
from . import create_blueprint
from ..utils.logger import log_info, log_error, log_warning
from ..utils.middleware import rate_limit, log_request, init_request_context
from ..agents.customer_agent.logic import CustomerAgent
# Create blueprint
bp = create_blueprint('customer')

# Get socketio instance
def get_socketio():
    from .. import socketio
    return socketio

# Đăng ký route trực tiếp với Flask
from flask import current_app

def register_routes(app):
    """Đăng ký route trực tiếp với Flask app"""
    app.add_url_rule('/customer/face-auth/confirm', 'customer.confirm_face_auth', confirm_face_auth, methods=['POST'])
    app.add_url_rule('/customer/', 'customer.face_auth', face_auth)
    app.add_url_rule('/customer/manual-login', 'customer.manual_login', manual_login, methods=['GET', 'POST'])
    app.add_url_rule('/customer/manual-auth', 'customer.manual_auth', manual_auth, methods=['POST'])

def register_socketio_events(socketio):
    """Đăng ký Socket.IO events"""
    socketio.on_event('video_frame', handle_video_frame)

@bp.route('/')
@log_request
def face_auth():
    """Hiển thị trang xác thực khuôn mặt"""
    # Kiểm tra tham số force
    force = request.args.get('force', 'false').lower() == 'true'

    # Nếu người dùng đã đăng nhập và không có tham số force, chuyển hướng đến trang chatbot
    if not force and session.get('user_id') and not session.get('is_guest', True):
        log_info(f"Người dùng {session.get('user_name')} đã đăng nhập, chuyển hướng đến trang chatbot")
        return redirect('/recommend/chat')

    # Xóa session cũ nếu có
    if session.get('user_id'):
        session.clear()
        session.modified = True
        log_info("Đã xóa session cũ")

    # Tải embedding trước khi hiển thị trang để tránh nhiều yêu cầu đồng thời
    try:
        from ..agents.customer_agent.face_auth import face_auth_manager

        # Tải embedding trực tiếp (không dùng thread) để tránh lỗi application context
        # Sử dụng cache để tránh tải lại nếu đã tải trước đó
        if not face_auth_manager.embeddings_loaded:
            log_info("🔄 Đang tải embedding trước khi hiển thị trang...")
            face_auth_manager.load_all_embeddings()
        else:
            log_info("✅ Đã tải embedding trước đó, sử dụng cache")
    except Exception as e:
        log_error(f"❌ Lỗi khi tải embedding: {str(e)}")

    return render_template('face_auth.html')

@bp.route('/face-auth/confirm', methods=['POST'])
@log_request
def confirm_face_auth():
    try:
        data = request.get_json()
        is_guest = data.get('is_guest', False)
        auto_guest = data.get('auto_guest', False)
        timestamp = data.get('timestamp', 0)
        user_info = data.get('user_info', {})
        
        # Log the request data
        current_app.logger.info(f"Face auth confirmation request: is_guest={is_guest}, auto_guest={auto_guest}, timestamp={timestamp}, user_info={user_info}")
        
        # Check if this is an automatic guest transition
        if auto_guest:
            last_auth_attempt = session.get('last_auth_attempt', 0)
            time_since_attempt = (timestamp - last_auth_attempt) / 1000  # Convert to seconds
            
            # If less than 30 seconds have passed since the last auth attempt, don't allow guest mode
            if time_since_attempt < 30:
                wait_time = 30 - time_since_attempt
                current_app.logger.info(f"Too soon for guest mode. Wait {wait_time:.1f} seconds")
                return jsonify({
                    'success': False,
                    'error': 'Vui lòng thử xác thực khuôn mặt trước',
                    'wait_time': wait_time
                }), 429  # Too Many Requests

            # Update last auth attempt time
            session['last_auth_attempt'] = timestamp
            session.modified = True

        if is_guest:
            # Clear any existing session data
            session.clear()
            
            # Set guest session data
            session['is_guest'] = True
            session['user_id'] = 'guest'
            session['user_name'] = 'Khách'
            session['customer_details'] = {
                'name': 'Khách',
                'email': None,
                'phone': None
            }
            session['orders'] = []
            session.modified = True
            
            current_app.logger.info("Guest session established")
            
            return jsonify({
                'success': True,
                'message': 'Đăng nhập với tư cách khách thành công',
                'redirect': '/recommend/chat'
            })
        else:
            # Handle authenticated user
            if not user_info or 'id' not in user_info:
                current_app.logger.error("Missing user_info in request data")
                return jsonify({
                    'success': False,
                    'message': 'Thiếu thông tin người dùng'
                }), 400

            user_id = user_info['id']
            
            # Get customer details from database
            from ..agents.customer_agent.customer_db import CustomerDB
            customer_db = CustomerDB()
            customer = customer_db.get_customer_info(user_id)
            if not customer:
                current_app.logger.error(f"Customer not found in database: {user_id}")
                return jsonify({
                    'success': False,
                    'message': 'Không tìm thấy thông tin khách hàng'
                }), 404

            # Update session with customer details
            session.clear()  # Clear any existing session data
            session['is_guest'] = False
            session['user_id'] = str(customer.get('id'))
            session['user_name'] = customer.get('name')
            session['customer_details'] = customer
            session['orders'] = []
            session.modified = True
            
            current_app.logger.info(f"Authenticated session established for user {user_id}")
            
            return jsonify({
                'success': True,
                'message': 'Xác thực thành công',
                'redirect': '/recommend/chat'
            })

    except Exception as e:
        current_app.logger.error(f"Error in face auth confirmation: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Lỗi xác thực: {str(e)}'
        }), 500

# Route xác thực khuôn mặt bằng cách tải ảnh lên đã bị loại bỏ
# Xác thực khuôn mặt chỉ được thực hiện thông qua camera (xử lý frame video)

@bp.route('/manual-login', methods=['GET', 'POST'])
@log_request
def manual_login():
    """Xác thực thủ công bằng ID và mật khẩu"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    if session.get('user_id') and not session.get('is_guest', True):
        return redirect('/recommend/chat')

    # Xử lý form đăng nhập
    if request.method == 'POST':
        customer_id = request.form.get('customer_id')
        password = request.form.get('password')

        if not customer_id or not password:
            return render_template('manual_login.html', error='Vui lòng nhập đầy đủ thông tin')

        try:
            # Xác thực thông tin đăng nhập
            from ..agents.customer_agent.customer_db import CustomerDB
            customer_db = CustomerDB()
            customer = customer_db.verify_customer_credentials(customer_id, password)

            if customer:
                # Đăng nhập thành công
                session['is_guest'] = False
                session['user_id'] = customer.get('id')
                session['user_name'] = customer.get('name')

                log_info(f"Đăng nhập thủ công thành công cho khách hàng {customer.get('name')}")

                # Chuyển hướng đến trang chatbot
                return redirect('/recommend/chat')
            else:
                # Đăng nhập thất bại
                log_error(f"Đăng nhập thủ công thất bại cho ID {customer_id}")
                return render_template('manual_login.html', error='ID hoặc mật khẩu không chính xác')

        except Exception as e:
            log_error(f"Lỗi khi xác thực thủ công: {str(e)}")
            return render_template('manual_login.html', error=f'Đã xảy ra lỗi: {str(e)}')

    # Hiển thị form đăng nhập
    return render_template('manual_login.html')

@bp.route('/manual-auth', methods=['POST'])
@log_request
def manual_auth():
    """Xác thực thủ công bằng ID (API endpoint)"""
    try:
        data = request.json
        customer_id = data.get('customer_id')

        if not customer_id:
            return jsonify({
                'success': False,
                'message': 'Thiếu ID khách hàng'
            }), 400

        log_info(f"Đang tìm kiếm khách hàng với ID: {customer_id}, kiểu dữ liệu: {type(customer_id).__name__}")

        # Truy vấn trực tiếp Neo4j với cả ID dạng số và chuỗi
        from ..neo4j_client.connection import execute_query_with_semaphore

        # Thử với ID dạng số
        try:
            customer_id_int = int(customer_id)
            log_info(f"Thử truy vấn với ID dạng số: {customer_id_int}")

            query = """
            MATCH (c:Customer)
            WHERE c.id = $customer_id
            RETURN c {.*} as customer
            LIMIT 1
            """

            result = execute_query_with_semaphore(query, {'customer_id': customer_id_int}, use_cache=False)

            if result and 'customer' in result[0]:
                customer = result[0]['customer']
                log_info(f"Tìm thấy khách hàng với ID số {customer_id_int}: {customer.get('name')}")
            else:
                log_info(f"Không tìm thấy khách hàng với ID số {customer_id_int}, thử với ID chuỗi")

                # Thử với ID dạng chuỗi
                result = execute_query_with_semaphore(query, {'customer_id': str(customer_id)}, use_cache=False)

                if result and 'customer' in result[0]:
                    customer = result[0]['customer']
                    log_info(f"Tìm thấy khách hàng với ID chuỗi {customer_id}: {customer.get('name')}")
                else:
                    log_warning(f"Không tìm thấy khách hàng với cả ID số và chuỗi: {customer_id}")
                    return jsonify({
                        'success': False,
                        'message': f'Không tìm thấy khách hàng với ID {customer_id}'
                    }), 404
        except (ValueError, TypeError):
            log_info(f"ID không phải dạng số, thử với ID chuỗi: {customer_id}")

            query = """
            MATCH (c:Customer)
            WHERE c.id = $customer_id
            RETURN c {.*} as customer
            LIMIT 1
            """

            result = execute_query_with_semaphore(query, {'customer_id': str(customer_id)}, use_cache=False)

            if result and 'customer' in result[0]:
                customer = result[0]['customer']
                log_info(f"Tìm thấy khách hàng với ID chuỗi {customer_id}: {customer.get('name')}")
            else:
                log_warning(f"Không tìm thấy khách hàng với ID chuỗi: {customer_id}")
                return jsonify({
                    'success': False,
                    'message': f'Không tìm thấy khách hàng với ID {customer_id}'
                }), 404

        # Lấy thông tin đơn hàng của khách hàng
        from ..agents.customer_agent.customer_db import CustomerDB
        customer_db = CustomerDB()
        customer_orders = customer_db.get_customer_orders(customer.get('id'))

        log_info(f"Xác thực thủ công thành công cho khách hàng {customer.get('name')} (ID: {customer.get('id')})")

        return jsonify({
            'success': True,
            'customer_id': customer.get('id'),
            'customer_name': customer.get('name'),
            'customer_info': customer,
            'customer_orders': customer_orders
        })

    except Exception as e:
        log_error(f"Lỗi khi xác thực thủ công: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Đã xảy ra lỗi: {str(e)}'
        }), 500

@bp.route('/profile')
@log_request
def get_customer_profile():
    """Lấy thông tin hồ sơ khách hàng"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Bạn chưa đăng nhập'
        }), 401

    try:
        # Lấy thông tin khách hàng
        customer_agent = CustomerAgent()
        customer = customer_agent.get_customer_info(user_id)

        if customer:
            return jsonify({
                'success': True,
                'customer': customer
            })
        else:
            return jsonify({
                'success': False,
                'error': 'Không tìm thấy thông tin khách hàng'
            }), 404

    except Exception as e:
        log_error(f"Lỗi khi lấy thông tin khách hàng: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Đã xảy ra lỗi khi lấy thông tin khách hàng'
        }), 500

@bp.route('/orders')
@log_request
def get_customer_orders():
    """Lấy danh sách đơn hàng của khách hàng"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({
            'success': False,
            'error': 'Bạn chưa đăng nhập'
        }), 401

    try:
        # Lấy danh sách đơn hàng
        customer_agent = CustomerAgent()
        orders = customer_agent.get_customer_orders(user_id)

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

# Biến toàn cục để theo dõi thời gian xử lý frame cuối cùng
_last_frame_time = None
_min_frame_interval = 0.1  # Giảm khoảng thời gian giữa các frame xuống 100ms

# Socket.IO event handler for video frames
def handle_video_frame(data):
    """Xử lý frame video từ webcam với giới hạn tốc độ để tránh quá tải"""
    global _last_frame_time

    try:
        from flask import session

        if session.get('user_id') and not session.get('is_guest', True):
            log_info("Người dùng đã đăng nhập, dừng xử lý frame video")
            return

        log_info("📹 [SOCKET.IO] Nhận frame video từ client")
        import time
        current_time = time.time()

        if _last_frame_time and current_time - _last_frame_time < _min_frame_interval:
            log_info(f"⏭️ Bỏ qua frame: quá sớm ({current_time - _last_frame_time:.3f}s < {_min_frame_interval}s)")
            return

        _last_frame_time = current_time

        image_data = data.get('image')
        if not image_data:
            log_error("❌ Không có dữ liệu hình ảnh trong frame")
            return

        from ..agents.customer_agent.face_auth import face_auth_manager

        if not face_auth_manager.embeddings_loaded:
            from flask_socketio import emit
            emit('face_verification_result', {
                'success': False,
                'error': 'Đang tải dữ liệu nhận dạng khuôn mặt, vui lòng chờ...',
                'loading': True
            })
            return

        import base64
        import cv2
        import numpy as np

        try:
            if ',' in image_data:
                image_data = image_data.split(',')[1]

            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

            if image is None:
                raise ValueError("Không thể decode image")

            log_info(f"✅ Đã decode image thành công: shape={image.shape}")

        except Exception as e:
            log_error(f"❌ Lỗi decode image: {str(e)}")
            from flask_socketio import emit
            emit('face_verification_result', {
                'success': False,
                'error': 'Lỗi xử lý hình ảnh'
            })
            return

        result = face_auth_manager.verify_face_realtime(image)

        if result.get('processing'):
            return

        from flask_socketio import emit

        if not result.get('success'):
            emit('face_verification_result', {
                'success': False,
                'error': result.get('message', 'Lỗi xử lý frame'),
                'processing_time': result.get('frame_metrics', {}).get('total_processing_time', 0)
            })
            return

        # Use customer info from result to determine recognition
        customer = result.get('customer')
        if customer:
            log_info(f"✅ Nhận diện thành công: {customer.get('name')}")

            session['user_id'] = customer.get('id')
            session['user_name'] = customer.get('name')
            session['is_guest'] = False

            from ..agents.customer_agent.customer_db import CustomerDB
            customer_db = CustomerDB()
            customer_details = customer_db.get_customer_info(customer.get('id'))
            if customer_details:
                session['customer_details'] = customer_details

            session['orders'] = []

            from ..agents.core.agent_manager import agent_manager
            import asyncio
            try:
                # Create new event loop to avoid "cannot reuse already awaited coroutine"
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                agent_coro = agent_manager.get_agent('customer')
                agent = loop.run_until_complete(agent_coro)
                loop.close()
            except Exception as e:
                log_error(f"Error creating agent customer: {str(e)}")
                agent = None
            if agent:
                # Check if get_status and get_connection_info are coroutine functions
                import asyncio
                # Use hasattr to check if methods exist
                if hasattr(agent, 'get_status'):
                    if asyncio.iscoroutinefunction(agent.get_status):
                        agent_status = asyncio.run(agent.get_status())
                    else:
                        agent_status = agent.get_status()
                else:
                    agent_status = None

                if hasattr(agent, 'get_connection_info'):
                    if asyncio.iscoroutinefunction(agent.get_connection_info):
                        connection_info = asyncio.run(agent.get_connection_info())
                    else:
                        connection_info = agent.get_connection_info()
                else:
                    connection_info = None
            else:
                agent_status = None
                connection_info = None

            emit('face_verification_result', {
                'success': True,
                'customer_id': customer.get('id'),
                'customer_name': customer.get('name'),
                'similarity': float(customer.get('similarity', 0)),
                'user_info': customer,
                'customer_details': customer_details,
                'agent': {
                    'status': agent_status,
                    'connection': connection_info
                },
                'bbox': result.get('frame_metrics', {}).get('bbox'),
                'confidence': float(result.get('frame_metrics', {}).get('confidence', 0)),
                'landmarks': result.get('frame_metrics', {}).get('landmarks', []),
                'processing_time': float(result.get('frame_metrics', {}).get('total_processing_time', 0)),
                'redirect': '/recommend/chat'
            })

            _last_frame_time = None
        else:
            emit('face_verification_result', {
                'success': False,
                'error': result.get('message', 'Không nhận diện được khuôn mặt'),
                'bbox': result.get('frame_metrics', {}).get('bbox'),
                'confidence': result.get('frame_metrics', {}).get('confidence'),
                'landmarks': result.get('frame_metrics', {}).get('landmarks', []),
                'processing_time': result.get('frame_metrics', {}).get('total_processing_time', 0)
            })

    except Exception as e:
        log_error(f"Lỗi khi xử lý frame video: {str(e)}")
        from flask_socketio import emit
        emit('face_verification_result', {
            'success': False,
            'error': str(e)
        })

@bp.route('/phobert-status', methods=['GET'])
def phobert_status():
    """Kiểm tra trạng thái PhoBERT model"""
    try:
        from ..models.phobert_manager import get_phobert_manager
        phobert_manager = get_phobert_manager()

        model_info = phobert_manager.get_model_info()
        cache_stats = phobert_manager.get_cache_stats()

        return jsonify({
            'success': True,
            'model_info': model_info,
            'cache_stats': cache_stats,
            'message': 'Trạng thái PhoBERT model'
        })

    except Exception as e:
        log_error(f"Lỗi khi kiểm tra trạng thái PhoBERT: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500

@bp.route('/phobert-test', methods=['POST'])
def phobert_test():
    """Test PhoBERT embedding với văn bản"""
    try:
        data = request.get_json()
        text = data.get('text', 'test embedding')

        from ..models.phobert_manager import get_phobert_manager
        phobert_manager = get_phobert_manager()

        if not phobert_manager.is_loaded:
            return jsonify({
                'success': False,
                'message': 'PhoBERT model chưa được tải'
            }), 503

        # Tạo embedding
        embedding = phobert_manager.get_embedding(text)

        return jsonify({
            'success': True,
            'text': text,
            'embedding_shape': embedding.shape,
            'embedding_sample': embedding[:5].tolist(),  # 5 giá trị đầu
            'message': 'Test embedding thành công'
        })

    except Exception as e:
        log_error(f"Lỗi khi test PhoBERT: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500

@bp.route('/phobert-dashboard')
def phobert_dashboard():
    """Hiển thị dashboard PhoBERT status"""
    return render_template('phobert_status.html')

@bp.route('/models-status', methods=['GET'])
def models_status():
    """Kiểm tra trạng thái tất cả models"""
    try:
        from ..models.model_manager import model_manager
        from ..agents.customer_agent.face_auth import face_auth_manager

        # Model manager status
        model_status = model_manager.get_loading_status()

        # Face auth manager status
        face_auth_stats = face_auth_manager.get_performance_stats()

        return jsonify({
            'success': True,
            'models': model_status,
            'face_auth': face_auth_stats,
            'message': 'Trạng thái tất cả models'
        })

    except Exception as e:
        log_error(f"Lỗi khi kiểm tra trạng thái models: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500
