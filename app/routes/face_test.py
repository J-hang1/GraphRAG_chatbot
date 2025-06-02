"""
Route for testing face recognition
"""
import os
import numpy as np
import json
from flask import Blueprint, render_template, request, jsonify, current_app
from ..agents.customer_agent.face_auth import face_auth_manager
from ..agents.customer_agent.customer_db import CustomerDB
from ..utils.logger import log_info, log_error, log_warning
# Import cv2 thông qua wrapper để tránh vấn đề đệ quy
from ..utils.cv2_wrapper import cv2

# Tạo blueprint
face_test_bp = Blueprint('face_test', __name__)

@face_test_bp.route('/test-face-recognition', methods=['GET'])
def test_face_recognition_page():
    """Hiển thị trang test nhận diện khuôn mặt"""
    # Tải tất cả embedding từ Neo4j trước khi hiển thị trang
    success = face_auth_manager.load_all_embeddings()
    if success:
        log_info("✅ Đã tải tất cả embedding từ Neo4j thành công")
    else:
        log_warning("❌ Không thể tải embedding từ Neo4j")

    return render_template('face_test.html')

@face_test_bp.route('/api/test-face-recognition', methods=['POST'])
def test_face_recognition_api():
    """API test nhận diện khuôn mặt"""
    try:
        # Lấy dữ liệu hình ảnh từ request
        if 'image' not in request.files:
            return jsonify({
                'success': False,
                'message': 'Không có hình ảnh được gửi lên'
            }), 400

        image_file = request.files['image']

        # Đọc hình ảnh
        image_data = image_file.read()
        nparr = np.frombuffer(image_data, np.uint8)
        image = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

        if image is None:
            return jsonify({
                'success': False,
                'message': 'Không thể đọc hình ảnh'
            }), 400

        # Sử dụng phương thức verify_face đã được cải tiến
        # Phương thức này sẽ tự động tải embedding nếu chưa được tải
        result = face_auth_manager.verify_face(image, threshold=0.01)

        # Trả về kết quả
        if result['success']:
            return jsonify({
                'success': True,
                'customer_id': result['customer_id'],
                'customer_name': result['customer_name'],
                'similarity': result['similarity'],
                'top_matches': result['top_matches']
            })
        else:
            return jsonify({
                'success': False,
                'message': result['message'],
                'similarity': result.get('similarity'),
                'top_matches': result.get('top_matches', [])
            })

    except Exception as e:
        log_error(f"Lỗi khi test nhận diện khuôn mặt: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'Lỗi: {str(e)}'
        }), 500
