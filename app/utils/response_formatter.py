from typing import Any, Dict, Optional
from flask import jsonify
from time import time
from collections import defaultdict
import threading

class RateLimiter:
    """Rate limiter implementation"""
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.requests = defaultdict(list)
        self._lock = threading.Lock()

    def is_allowed(self, user_id: str) -> bool:
        """Kiểm tra xem request có bị rate limit không"""
        now = time()
        minute_ago = now - 60

        with self._lock:
            # Xóa requests cũ hơn 1 phút
            self.requests[user_id] = [
                req_time for req_time in self.requests[user_id]
                if req_time > minute_ago
            ]

            # Kiểm tra số lượng requests trong phút vừa qua
            if len(self.requests[user_id]) >= self.requests_per_minute:
                return False

            # Thêm request mới
            self.requests[user_id].append(now)
            return True

class ResponseFormatter:
    """Formatter chuẩn hóa response"""
    
    @staticmethod
    def success(data: Any = None, message: Optional[str] = None) -> tuple:
        """Format successful response"""
        response = {
            'success': True
        }
        
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
            
        return jsonify(response), 200

    @staticmethod
    def error(message: str, 
             status_code: int = 400, 
             error_code: Optional[str] = None, 
             details: Optional[Dict] = None) -> tuple:
        """Format error response"""
        response = {
            'success': False,
            'error': {
                'message': message,
                'code': error_code or status_code
            }
        }
        
        if details:
            response['error']['details'] = details
            
        return jsonify(response), status_code

    @staticmethod
    def rate_limited(wait_time: int) -> tuple:
        """Format rate limit response"""
        return ResponseFormatter.error(
            message='Quá nhiều yêu cầu, vui lòng thử lại sau',
            status_code=429,
            error_code='RATE_LIMITED',
            details={'wait_seconds': wait_time}
        )

    @staticmethod
    def validation_error(errors: Dict) -> tuple:
        """Format validation error response"""
        return ResponseFormatter.error(
            message='Dữ liệu đầu vào không hợp lệ',
            status_code=400,
            error_code='VALIDATION_ERROR',
            details={'fields': errors}
        )

    @staticmethod
    def unauthorized(message: str = 'Unauthorized') -> tuple:
        """Format unauthorized response"""
        return ResponseFormatter.error(
            message=message,
            status_code=401,
            error_code='UNAUTHORIZED'
        )

    @staticmethod
    def forbidden(message: str = 'Forbidden') -> tuple:
        """Format forbidden response"""
        return ResponseFormatter.error(
            message=message,
            status_code=403,
            error_code='FORBIDDEN'
        )

    @staticmethod
    def not_found(resource: str = 'Resource') -> tuple:
        """Format not found response"""
        return ResponseFormatter.error(
            message=f'{resource} không tồn tại',
            status_code=404,
            error_code='NOT_FOUND'
        )

# Global instances
rate_limiter = RateLimiter()
formatter = ResponseFormatter()