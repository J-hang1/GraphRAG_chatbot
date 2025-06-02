from functools import wraps
from flask import request, session, g
from .response_formatter import rate_limiter, formatter
from .logger import log_info, log_warning

def require_auth(f):
    """Middleware kiểm tra authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            return formatter.unauthorized('Vui lòng đăng nhập để tiếp tục')
        return f(*args, **kwargs)
    return decorated

def rate_limit(f):
    """Middleware áp dụng rate limiting"""
    @wraps(f)
    def decorated(*args, **kwargs):
        user_id = session.get('user_id', request.remote_addr)
        
        if not rate_limiter.is_allowed(user_id):
            log_warning(f"Rate limit exceeded for user {user_id}")
            return formatter.rate_limited(60)
            
        return f(*args, **kwargs)
    return decorated

def log_request(f):
    """Middleware log request details"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Log request info
        log_info(f"Request to {request.path}", {
            'method': request.method,
            'path': request.path,
            'user_id': session.get('user_id'),
            'ip': request.remote_addr
        })
        
        return f(*args, **kwargs)
    return decorated

def init_request_context(f):
    """Middleware khởi tạo request context"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Set trace ID for request tracing
        request_id = request.headers.get('X-Request-ID')
        g.trace_id = request_id if request_id else None
        
        # Set user info in context
        g.user_id = session.get('user_id')
        g.is_authenticated = bool(g.user_id)
        
        return f(*args, **kwargs)
    return decorated