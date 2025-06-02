from flask import redirect, url_for, session
from . import create_blueprint

# Tạo blueprint cho trang chủ
bp = create_blueprint('main')

@bp.route('/')
def index():
    """Hiển thị trang chủ"""
    # Nếu người dùng đã đăng nhập, chuyển hướng đến trang chat
    if session.get('user_id'):
        return redirect(url_for('recommend.chat_page'))

    # Nếu chưa đăng nhập, chuyển hướng đến trang xác thực khuôn mặt
    return redirect('/customer')

@bp.route('/logout')
def logout():
    """Đăng xuất người dùng và xóa lịch sử chat (giữ lại models cache)"""
    try:
        # Lấy session_id (sử dụng user_id nếu đã xác thực, hoặc session id)
        user_id = session.get('user_id', 'guest')
        session_id = user_id if user_id != 'guest' else session.sid if hasattr(session, 'sid') else 'default'
        is_authenticated = user_id != 'guest' and user_id is not None

        # Xóa lịch sử chat từ ChatHistoryAgent
        try:
            from ..agents.chathistory_agent.logic import ChatHistoryAgent
            chathistory_agent = ChatHistoryAgent()
            chathistory_agent.reset_session(session_id)

            # Nếu đã xác thực, cũng xóa lịch sử chat từ session_manager
            if is_authenticated:
                from ..agents.chathistory_agent.session_manager import chat_session_manager
                chat_session_manager.reset_session(session_id)
        except Exception as e:
            from ..utils.logger import log_error
            log_error(f"Lỗi khi xóa lịch sử chat từ ChatHistoryAgent: {str(e)}")

        # Xóa thông tin người dùng khỏi phiên
        session.pop('user_id', None)
        session.pop('user_name', None)
        session.pop('is_guest', None)

        # Xóa lịch sử chat khỏi session
        session.pop('chat_history', None)

        # Xóa toàn bộ phiên NHƯNG GIỮ LẠI MODELS CACHE
        session.clear()

        # Kiểm tra và hiển thị thống kê cache models
        try:
            from ..models.model_persistence import model_persistence
            cache_stats = model_persistence.get_cache_stats()
            from ..utils.logger import log_info
            log_info(f"📊 Models cache sau logout: {cache_stats}")
        except Exception as e:
            from ..utils.logger import log_warning
            log_warning(f"⚠️ Không thể kiểm tra cache stats: {str(e)}")

        from ..utils.logger import log_info
        log_info(f"Đã đăng xuất và xóa lịch sử chat cho người dùng {user_id} (giữ lại models cache)")
    except Exception as e:
        from ..utils.logger import log_error
        log_error(f"Lỗi khi đăng xuất: {str(e)}")

    # Chuyển hướng về trang chủ
    return redirect(url_for('main.index'))
