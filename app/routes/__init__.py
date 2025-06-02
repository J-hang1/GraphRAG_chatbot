"""
Routes package initialization
"""
from flask import Blueprint, jsonify
from ..utils.logger import log_error

class APIError(Exception):
    """Custom exception cho API errors"""
    def __init__(self, message, status_code=400, error_code=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code or status_code

def create_blueprint(name):
    """Create blueprint với error handling"""
    bp = Blueprint(name, __name__)

    @bp.errorhandler(APIError)
    def handle_api_error(error):
        log_error(f"API Error: {str(error)}", {
            'status_code': error.status_code,
            'error_code': error.error_code
        })
        return jsonify({
            'success': False,
            'error': {
                'message': str(error),
                'code': error.error_code
            }
        }), error.status_code

    @bp.errorhandler(Exception)
    def handle_generic_error(error):
        log_error(f"Unexpected error: {str(error)}")
        return jsonify({
            'success': False,
            'error': {
                'message': 'Đã xảy ra lỗi không mong muốn',
                'code': 500
            }
        }), 500

    return bp

# Import routes to make them available
from . import customer_routes
from . import order_routes
from . import recommend_routes
from . import face_test
