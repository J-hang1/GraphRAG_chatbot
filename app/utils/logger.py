import os
import json
import uuid
import sys
import datetime
from flask import current_app, request

# Đảm bảo terminal có thể hiển thị tiếng Việt
if sys.platform == 'win32':
    # Đối với Windows
    import ctypes
    kernel32 = ctypes.windll.kernel32
    kernel32.SetConsoleCP(65001)
    kernel32.SetConsoleOutputCP(65001)

# Đảm bảo stdout sử dụng UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Màu sắc cho terminal
class TerminalColors:
    HEADER = '\033[95m'
    INFO = '\033[94m'
    SUCCESS = '\033[92m'
    WARNING = '\033[93m'
    ERROR = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def setup_logger(app):
    """
    Thiết lập logger cho ứng dụng (giờ chỉ in ra terminal)

    Args:
        app: Thể hiện của ứng dụng Flask
    """
    # Tạo thư mục logs nếu nó không tồn tại (vẫn giữ lại để tương thích)
    logs_dir = os.path.join(app.root_path, '..', 'logs')
    if not os.path.exists(logs_dir):
        os.makedirs(logs_dir)

    print(f"{TerminalColors.SUCCESS}[SYSTEM] Chatbot khởi động thành công{TerminalColors.ENDC}")

def get_trace_id():
    """Lấy trace ID từ request hoặc tạo mới"""
    try:
        if hasattr(request, 'trace_id'):
            return request.trace_id
    except RuntimeError:
        # Xử lý trường hợp không có request context
        pass
    return str(uuid.uuid4())

def format_log(message, context=None):
    """Format log message với context"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    trace_id = get_trace_id()

    if context:
        context_str = f" | Context: {json.dumps(context, ensure_ascii=False)}"
    else:
        context_str = ""

    return f"[{timestamp}] [{trace_id}] {message}{context_str}"

def log_chat(user_id, message, response):
    """
    In log tương tác chat

    Args:
        user_id: ID người dùng
        message: Tin nhắn người dùng
        response: Phản hồi của hệ thống
    """
    log_message = format_log(
        message=f"💬 CHAT | User: {user_id}",
        context={
            'message': message,
            'response': response[:100] + '...' if len(response) > 100 else response
        }
    )
    print(f"{TerminalColors.INFO}{log_message}{TerminalColors.ENDC}")

def log_error(error, context=None):
    """
    In log lỗi

    Args:
        error: Thông báo lỗi hoặc ngoại lệ
        context: Thông tin ngữ cảnh bổ sung
    """
    # Xử lý các ký tự đặc biệt trong chuỗi error
    error_str = str(error)
    error_str = error_str.replace("%", "%%")

    log_message = format_log(
        message=f"❌ ERROR | {error_str}",
        context=context
    )
    print(f"{TerminalColors.ERROR}{log_message}{TerminalColors.ENDC}")

def log_warning(warning, context=None):
    """
    In log cảnh báo

    Args:
        warning: Thông báo cảnh báo
        context: Thông tin ngữ cảnh bổ sung
    """
    log_message = format_log(
        message=f"⚠️ WARNING | {warning}",
        context=context
    )
    print(f"{TerminalColors.WARNING}{log_message}{TerminalColors.ENDC}")

def log_info(message, context=None):
    """
    In log thông tin

    Args:
        message: Thông báo thông tin
        context: Thông tin ngữ cảnh bổ sung
    """
    # Xử lý các ký tự đặc biệt trong chuỗi message
    # Đặc biệt là ký tự % được sử dụng trong các hàm định dạng chuỗi
    if isinstance(message, str):
        message = message.replace("%", "%%")

    log_message = format_log(
        message=f"ℹ️ INFO | {message}",
        context=context
    )
    print(f"{TerminalColors.INFO}{log_message}{TerminalColors.ENDC}")
