import sys
import traceback

def preload_models():
    """Preload tất cả models trước khi khởi động server"""
    print("[SYSTEM] 🚀 Bắt đầu preload models...")

    try:
        from app.models.model_manager import ModelManager
        model_manager = ModelManager()
        # Chỉ load face recognition model
        model_manager._load_face_recognition_model()
        print("[SYSTEM] ✅ Face recognition model preloaded successfully")

        # Initialize face authentication manager
        try:
            from app.agents.customer_agent.face_auth import face_auth_manager
            # Face auth manager tự động khởi tạo khi import
            stats = face_auth_manager.get_performance_stats()
            if stats['models_ready'] and stats['embeddings_loaded']:
                print("[SYSTEM] ✅ Face authentication manager đã sẵn sàng!")
            else:
                print(f"[SYSTEM] ⚠️ Face auth manager: models_ready={stats['models_ready']}, embeddings_loaded={stats['embeddings_loaded']}")
        except Exception as e:
            print(f"[SYSTEM] ⚠️ Lỗi khởi tạo face authentication manager: {str(e)}")

        return True

    except Exception as e:
        print(f"[SYSTEM] ❌ Lỗi preload models: {str(e)}")
        traceback.print_exc(file=sys.stdout)
        return False

print("[SYSTEM] Bắt đầu khởi tạo ứng dụng...")

try:
    from app import create_app, socketio
    print("[SYSTEM] Import thành công")

    # Preload models trước khi tạo app (optional, không fail nếu lỗi)
    try:
        preload_models()
    except Exception as e:
        print(f"[SYSTEM] ⚠️ Lỗi preload models: {str(e)}")
        print("[SYSTEM] Tiếp tục khởi động server...")

    print("[SYSTEM] Đang tạo app...")
    app = create_app()
    print("[SYSTEM] App đã được tạo thành công")

except Exception as e:
    print(f"[SYSTEM ERROR] Lỗi khi khởi tạo app: {str(e)}")
    traceback.print_exc(file=sys.stdout)
    input("Nhấn Enter để thoát...")
    sys.exit(1)

if __name__ == '__main__':
    try:
        print("[SYSTEM] Chatbot khởi động thành công")
        print("[SYSTEM] 🎉 Hệ thống đã sẵn sàng với tất cả models được preload!")

        # Run with SocketIO instead of app.run
        # Sử dụng cổng 5001 thay vì cổng mặc định 5000
        # Tắt chế độ debug để tránh khởi động lại liên tục
        socketio.run(app, debug=False, port=5001, use_reloader=False)
    except Exception as e:
        print(f"[SYSTEM ERROR] {str(e)}")
        traceback.print_exc(file=sys.stdout)
        input("Nhấn Enter để thoát...")