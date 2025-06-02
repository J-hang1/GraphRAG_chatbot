"""
Recommendation routes for product recommendations and chat
"""
import os
from datetime import datetime
from flask import request, render_template, current_app, session, jsonify, redirect
from werkzeug.utils import secure_filename
from . import create_blueprint, APIError
from ..utils.logger import log_info, log_error, log_warning
from ..utils.middleware import rate_limit, log_request, init_request_context
from ..agents.routing_agent.logic import RouterAgent
from ..utils.response_formatter import formatter

# Create blueprint
bp = create_blueprint('recommend')

# Đăng ký route trực tiếp với Flask
from flask import current_app

def register_routes(app):
    """Đăng ký route trực tiếp với Flask app"""
    # Không cần đăng ký lại các route đã được đăng ký thông qua blueprint
    # Các route này sẽ được tự động đăng ký với tiền tố '/recommend' khi blueprint được đăng ký
    pass

@bp.route('/chat')
@log_request
def chat_page():
    """Hiển thị trang chatbot"""
    # Log thông tin session để debug
    from flask import session, request
    log_info(f"Session data in chat_page: user_id={session.get('user_id')}, user_name={session.get('user_name')}, is_guest={session.get('is_guest')}")

    # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
    user_id = session.get('user_id')
    session_id = user_id if user_id and user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'
    
    # Kiểm tra trạng thái đăng nhập
    is_guest = session.get('is_guest', True)
    is_authenticated = not is_guest and user_id and user_id != 'guest'

    # Kiểm tra xem có phải là tải lại trang không
    is_page_reload = request.headers.get('Cache-Control') == 'max-age=0' or request.headers.get('Pragma') == 'no-cache'

    # Nếu không có session và không phải là tải lại trang, chuyển hướng về trang xác thực
    if not is_authenticated and not is_guest and not is_page_reload:
        log_info("Không có session hợp lệ, chuyển hướng về trang xác thực")
        return redirect('/customer')

    # Xử lý tải lại trang
    if is_page_reload:
        log_info(f"Phát hiện tải lại trang cho người dùng {user_id} (authenticated={is_authenticated}, guest={is_guest})")

        try:
            # Nếu là khách ẩn danh, reset toàn bộ memory
            if is_guest:
                log_info("Khách ẩn danh tải lại trang, reset toàn bộ memory")

                # Reset phiên chat
                from ..agents.chathistory_agent.logic import ChatHistoryAgent
                chathistory_agent = ChatHistoryAgent()
                chathistory_agent.reset_session(session_id)

                # Xóa lịch sử chat khỏi session
                session.pop('chat_history', None)
            else:
                # Nếu đã xác thực, chỉ xóa lịch sử chat, giữ lại thông tin khách hàng
                log_info("Người dùng đã xác thực tải lại trang, chỉ xóa lịch sử chat")

                # Xóa lịch sử chat
                from ..agents.chathistory_agent.logic import ChatHistoryAgent
                chathistory_agent = ChatHistoryAgent()
                chathistory_agent.reset_session(session_id)

                # Xóa lịch sử chat khỏi session
                session.pop('chat_history', None)
        except Exception as e:
            log_error(f"Lỗi khi xử lý tải lại trang: {str(e)}")

    return render_template('chatbot.html')

@bp.route('/api/test', methods=['POST', 'GET'])
def test_endpoint():
    """Endpoint test đơn giản để kiểm tra kết nối"""
    log_info("=== TEST ENDPOINT CALLED ===")
    log_info(f"Request method: {request.method}")
    log_info(f"Request headers: {dict(request.headers)}")
    log_info(f"Request URL: {request.url}")
    log_info(f"Request path: {request.path}")
    log_info(f"Request content type: {request.content_type}")
    log_info(f"Request data: {request.get_data(as_text=True)}")

    if request.method == 'GET':
        return "Test endpoint is working!"

    if request.is_json:
        data = request.get_json()
        log_info(f"JSON data: {data}")
        return {"success": True, "message": "Received JSON data", "data": data}
    else:
        form_data = dict(request.form)
        log_info(f"Form data: {form_data}")
        return {"success": True, "message": "Received form data", "data": form_data}

@bp.route('/api/chat', methods=['POST'])
@log_request
@rate_limit
@init_request_context
def chat():
    """Xử lý tương tác với chatbot"""
    try:
        log_info("=== STARTING NEW CHAT REQUEST ===")
        log_info(f"Request method: {request.method}")
        log_info(f"Request headers: {dict(request.headers)}")
        log_info(f"Request URL: {request.url}")
        log_info(f"Request path: {request.path}")
        log_info(f"Request content type: {request.content_type}")
        log_info(f"Request data: {request.get_data(as_text=True)}")

        # Xử lý file hình ảnh nếu có
        image_path = None
        if 'image' in request.files:
            file = request.files['image']
            if file and file.filename and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                upload_folder = current_app.config['UPLOAD_FOLDER']
                image_path = os.path.join(upload_folder, filename)
                file.save(image_path)
                log_info(f"Đã lưu hình ảnh tải lên: {image_path}")

        # Lấy tin nhắn từ form data hoặc JSON
        if request.is_json:
            log_info("Processing JSON request")
            try:
                # Đảm bảo request.get_json() sử dụng force=True để xử lý các trường hợp content-type không chính xác
                data = request.get_json(force=True)
                log_info(f"Request JSON data: {data}")

                # Xử lý tin nhắn, đảm bảo mã hóa UTF-8 cho tiếng Việt
                user_message = data.get('message', '')
                if isinstance(user_message, str):
                    # Đảm bảo tin nhắn là chuỗi UTF-8 hợp lệ
                    try:
                        # Thử encode và decode để đảm bảo chuỗi UTF-8 hợp lệ
                        user_message = user_message.encode('utf-8', errors='ignore').decode('utf-8')
                    except Exception as e:
                        log_error(f"Error encoding/decoding message: {str(e)}")

                user_id = data.get('user_id', 'guest')
                log_info(f"Extracted message: '{user_message}', user_id: '{user_id}'")
            except Exception as json_error:
                log_error(f"Error parsing JSON: {str(json_error)}")

                # Thử phân tích dữ liệu thô
                try:
                    raw_data = request.get_data(as_text=True)
                    log_info(f"Raw request data: {raw_data}")

                    # Thử phân tích dữ liệu thô theo cách thủ công
                    import json
                    try:
                        manual_data = json.loads(raw_data)
                        log_info(f"Manually parsed JSON: {manual_data}")
                        user_message = manual_data.get('message', '')
                        user_id = manual_data.get('user_id', 'guest')
                        log_info(f"Manually extracted: message='{user_message}', user_id='{user_id}'")
                    except json.JSONDecodeError:
                        log_error("Failed to manually parse JSON")
                        return formatter.error(
                            message='Lỗi khi xử lý dữ liệu JSON',
                            status_code=400,
                            error_code='JSON_PARSE_ERROR'
                        )
                except Exception as raw_error:
                    log_error(f"Error processing raw data: {str(raw_error)}")
                    return formatter.error(
                        message='Lỗi khi xử lý dữ liệu JSON',
                        status_code=400,
                        error_code='JSON_PARSE_ERROR'
                    )
        else:
            log_info("Processing form data request")
            user_message = request.form.get('message', '')
            # Đảm bảo tin nhắn là chuỗi UTF-8 hợp lệ
            if isinstance(user_message, str):
                try:
                    user_message = user_message.encode('utf-8', errors='ignore').decode('utf-8')
                except Exception as e:
                    log_error(f"Error encoding/decoding form message: {str(e)}")

            user_id = request.form.get('user_id', 'guest')
            log_info(f"Form data - message: '{user_message}', user_id: '{user_id}'")

        # Validate input
        if not user_message and not image_path:
            log_error("Missing message and image")
            return formatter.validation_error({
                'message': 'Thiếu tin nhắn hoặc hình ảnh'
            })

        # Sử dụng routing agent để xử lý tin nhắn
        router = RouterAgent(agent_id='router')
        log_info(f"Xử lý tin nhắn từ người dùng {user_id}: {user_message}")

        # Xử lý tin nhắn và lấy phản hồi
        try:
            log_info(f"[STEP 1] Bắt đầu xử lý tin nhắn: {user_message}")
            log_info(f"[STEP 1.1] Image path: {image_path}")
            log_info(f"[STEP 1.2] User ID: {user_id}")

            # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
            session_id = user_id if user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'

            # Tạo context với thông tin khách hàng đầy đủ
            context = {
                "user_id": user_id,
                "session_id": session_id
            }

            try:
                # Lấy instance của GraphRAG agent trực tiếp
                from ..agents.graphrag_agent.logic import GraphRAGAgent
                graphrag_agent = GraphRAGAgent(agent_id='graphrag')
                log_info(f"[DEBUG] GraphRAG agent initialized successfully")

                # Nếu người dùng đã đăng nhập, thêm thông tin khách hàng vào context
                if user_id and user_id != 'guest':
                    try:
                        # Import CustomerAgent để lấy thông tin khách hàng
                        from ..agents.customer_agent.logic import CustomerAgent
                        customer_agent = CustomerAgent()
                        customer_info = customer_agent.get_customer_info(user_id)

                        if customer_info:
                            # Chỉ lấy thông tin cơ bản của khách hàng, loại bỏ embedding
                            basic_customer_info = {
                                'id': customer_info.get('id'),
                                'name': customer_info.get('name'),
                                'sex': customer_info.get('sex'),
                                'age': customer_info.get('age'),
                                'location': customer_info.get('location')
                            }
                            # Thêm thông tin khách hàng vào context
                            context["customer_info"] = basic_customer_info
                            log_info(f"Đã thêm thông tin cơ bản của khách hàng vào context: {user_id}")
                    except Exception as e:
                        log_error(f"Lỗi khi lấy thông tin khách hàng: {str(e)}")

                # Lấy lịch sử chat từ ChatHistoryAgent
                try:
                    from ..agents.chathistory_agent.logic import ChatHistoryAgent
                    chathistory_agent = ChatHistoryAgent()
                    chat_history = chathistory_agent.get_chat_history(session_id)

                    if chat_history:
                        context['chat_history'] = chat_history
                        log_info(f"Đã tải {len(chat_history)} tin nhắn từ ChatHistoryAgent")

                        # Thêm thông tin về tin nhắn gần nhất
                        if len(chat_history) > 0:
                            last_message = chat_history[-1]
                            log_info(f"Tin nhắn gần nhất: {str(last_message)[:200]}...")

                            # Thêm thông tin về sản phẩm được chọn gần nhất nếu có
                            if 'selected_product_list' in last_message:
                                context['selected_product_list'] = last_message.get('selected_product_list', [])
                                log_info(f"Đã tìm thấy sản phẩm được chọn trong tin nhắn gần nhất: {context['selected_product_list']}")

                            # Thêm thông tin về structured_query nếu có
                            if 'structured_query' in last_message:
                                context['last_structured_query'] = last_message.get('structured_query', {})
                                log_info(f"Đã tìm thấy structured_query trong tin nhắn gần nhất: {str(context['last_structured_query'])[:200]}...")

                        # Trích xuất ngữ cảnh từ lịch sử chat
                        try:
                            chat_context = chathistory_agent.extract_context_from_history(session_id, user_message)
                            if chat_context:
                                context['chat_context'] = chat_context
                                log_info(f"Đã trích xuất ngữ cảnh từ lịch sử chat: {str(chat_context)[:200]}...")
                        except Exception as e:
                            log_error(f"Lỗi khi trích xuất ngữ cảnh từ lịch sử chat: {str(e)}")
                    else:
                        log_info("Không có lịch sử chat để truyền đến GraphRAG agent")
                except Exception as e:
                    log_error(f"Lỗi khi tải lịch sử chat từ ChatHistoryAgent: {str(e)}")

                # Gọi trực tiếp Recommend agent và truyền GraphRAG agent đã khởi tạo
                log_info(f"[STEP 2] Gọi trực tiếp Recommend agent với tin nhắn: {user_message}")
                log_info(f"Context keys: {', '.join(context.keys())}")
                from ..agents.recommend_agent.logic import RecommendAgent
                recommend_agent = RecommendAgent(agent_id='recommend')

                # Truyền GraphRAG agent đã khởi tạo vào Recommend agent
                recommend_agent.graphrag_agent = graphrag_agent
                log_info(f"[DEBUG] Đã truyền GraphRAG agent đã khởi tạo vào Recommend agent")

                # Thêm thông tin vào context để biết GraphRAG agent đã được khởi tạo
                context['graphrag_agent_initialized'] = True

                # Sử dụng asyncio để chạy async code
                import asyncio
                response = asyncio.run(recommend_agent.process_message(user_message, context))
                log_info(f"[STEP 3] Nhận được phản hồi từ Recommend agent: {response[:100]}...")
            except Exception as recommend_error:
                log_error(f"[ERROR] Lỗi khi gọi trực tiếp Recommend agent: {str(recommend_error)}")
                # Fallback về router
                log_info(f"[STEP 2-ALT] Fallback về router agent")
                response = asyncio.run(router.process_message(user_message, image_path))

            log_info(f"[STEP 6] Phản hồi từ agent: {response[:100]}...")
            log_info(f"[STEP 7] Trả về phản hồi cho client")
        except Exception as agent_error:
            log_error(f"[ERROR] Lỗi khi xử lý tin nhắn với agent: {str(agent_error)}")
            response = "Xin lỗi, tôi không thể trả lời câu hỏi của bạn lúc này. Vui lòng thử lại sau."

        # Lưu lịch sử chat vào ChatHistoryAgent
        try:
            # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
            user_id = session.get('user_id', 'guest')
            session_id = user_id if user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'

            # Lưu tin nhắn vào ChatHistoryAgent
            from ..agents.chathistory_agent.logic import ChatHistoryAgent
            chathistory_agent = ChatHistoryAgent()

            # Tạo query_details nếu có thông tin từ GraphRAG agent
            query_details = {}

            # Thêm tin nhắn vào lịch sử chat
            chathistory_agent.add_message(session_id, user_message, response, query_details)

            # Lấy số lượng tin nhắn hiện tại
            chat_history = chathistory_agent.get_chat_history(session_id)
            log_info(f"Đã lưu lịch sử chat vào ChatHistoryAgent (hiện có {len(chat_history)} tin nhắn)")

            # Không cần lưu vào memory service nữa vì đã loại bỏ module này
            pass
        except Exception as e:
            log_error(f"Lỗi khi lưu lịch sử chat vào ChatHistoryAgent: {str(e)}")

            # Fallback về session nếu ChatHistoryAgent gặp lỗi
            try:
                # Tạo đối tượng tin nhắn mới
                message = {
                    'user_message': user_message,
                    'bot_response': response,
                    'timestamp': datetime.now().isoformat()
                }

                # Lưu vào session
                if 'chat_history' not in session:
                    session['chat_history'] = []

                session['chat_history'].append(message)
                log_info(f"Đã lưu lịch sử chat vào session (fallback)")
            except Exception as e2:
                log_error(f"Lỗi khi lưu lịch sử chat vào session (fallback): {str(e2)}")

        log_info(f"[FINAL] Returning response: {response[:100]}...")
        return formatter.success(data={'response': response})

    except Exception as e:
        log_error(f"Lỗi khi xử lý tin nhắn: {str(e)}")
        return formatter.error(
            message='Đã xảy ra lỗi khi xử lý yêu cầu',
            status_code=500,
            error_code='CHAT_ERROR',
            details={'error': str(e)}
        )

@bp.route('/api/clear-history', methods=['POST'])
@log_request
def clear_history():
    """Xóa lịch sử chat trong phiên hiện tại"""
    try:
        # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
        user_id = session.get('user_id', 'guest')
        session_id = user_id if user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'

        # Xóa lịch sử chat từ ChatHistoryAgent
        try:
            from ..agents.chathistory_agent.logic import ChatHistoryAgent
            chathistory_agent = ChatHistoryAgent()
            chathistory_agent.reset_session(session_id)
            log_info(f"Đã xóa lịch sử chat từ ChatHistoryAgent cho session {session_id}")
        except Exception as e1:
            log_error(f"Lỗi khi xóa lịch sử chat từ ChatHistoryAgent: {str(e1)}")

        # Không cần xóa memory service nữa vì đã loại bỏ module này
        pass

        # Xóa lịch sử chat khỏi session (để đảm bảo tương thích)
        session.pop('chat_history', None)
        log_info(f"Đã xóa lịch sử chat khỏi session cho session {session_id}")

        log_info("Đã xóa lịch sử chat thành công")
        return formatter.success(message="Đã xóa lịch sử chat thành công")
    except Exception as e:
        log_error(f"Lỗi khi xóa lịch sử chat: {str(e)}")
        return formatter.error(
            message="Lỗi khi xóa lịch sử chat",
            status_code=500,
            error_code="CLEAR_HISTORY_ERROR"
        )

@bp.route('/api/recommendations', methods=['GET'])
@log_request
def get_recommendations():
    """Lấy gợi ý sản phẩm cho người dùng"""
    # Kiểm tra xem người dùng đã đăng nhập chưa
    user_id = session.get('user_id')

    try:
        # Lấy tham số từ query string
        category = request.args.get('category')
        price_range = request.args.get('price_range')
        limit = request.args.get('limit', 10, type=int)

        # Sử dụng routing agent để lấy gợi ý
        router = RouterAgent()
        recommendations = router.get_recommendations(user_id, category, price_range, limit)

        return formatter.success(data={'recommendations': recommendations})

    except Exception as e:
        log_error(f"Lỗi khi lấy gợi ý sản phẩm: {str(e)}")
        return formatter.error(
            message='Đã xảy ra lỗi khi lấy gợi ý sản phẩm',
            status_code=500,
            error_code='RECOMMENDATION_ERROR'
        )

@bp.route('/api/reset-session', methods=['POST'])
@log_request
def reset_session():
    """Reset session khi người dùng tải lại trang"""
    try:
        # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
        user_id = session.get('user_id', 'guest')
        session_id = user_id if user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'
        is_authenticated = user_id != 'guest' and user_id is not None
        is_guest = session.get('is_guest', True)

        log_info(f"Yêu cầu reset session cho người dùng {user_id} (authenticated={is_authenticated}, guest={is_guest})")

        try:
            # Nếu là khách ẩn danh, reset toàn bộ memory
            if is_guest:
                log_info("Khách ẩn danh tải lại trang, reset toàn bộ memory")

                # Reset phiên chat
                from ..agents.chathistory_agent.logic import ChatHistoryAgent
                chathistory_agent = ChatHistoryAgent()
                chathistory_agent.reset_session(session_id)

                # Xóa lịch sử chat khỏi session
                session.pop('chat_history', None)
            else:
                # Nếu đã xác thực, chỉ xóa lịch sử chat, giữ lại thông tin khách hàng
                log_info("Người dùng đã xác thực tải lại trang, chỉ xóa lịch sử chat")

                # Xóa lịch sử chat
                from ..agents.chathistory_agent.logic import ChatHistoryAgent
                chathistory_agent = ChatHistoryAgent()
                chathistory_agent.reset_session(session_id)

                # Xóa lịch sử chat khỏi session
                session.pop('chat_history', None)

            return formatter.success(message="Đã reset session thành công")
        except Exception as e:
            log_error(f"Lỗi khi reset session: {str(e)}")
            return formatter.error(
                message="Lỗi khi reset session",
                status_code=500,
                error_code="RESET_SESSION_ERROR"
            )
    except Exception as e:
        log_error(f"Lỗi khi xử lý yêu cầu reset session: {str(e)}")
        return formatter.error(
            message="Lỗi khi xử lý yêu cầu reset session",
            status_code=500,
            error_code="RESET_SESSION_ERROR"
        )

def allowed_file(filename):
    """Kiểm tra xem file có phần mở rộng được cho phép không"""
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
