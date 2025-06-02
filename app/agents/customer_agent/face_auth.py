"""
Face authentication module for Customer agent - Optimized for real-time detection
"""
import os
import numpy as np
import json
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed
import multiprocessing

from ...utils.logger import log_info, log_error, log_warning
from ...neo4j_client.connection import execute_query_with_semaphore
from .customer_db import CustomerDB
from ...utils.cv2_wrapper import cv2
from insightface.model_zoo import get_model
from insightface.model_zoo.arcface_onnx import ArcFaceONNX
from insightface.utils.face_align import norm_crop
from insightface.app.common import Face
from insightface.model_zoo.retinaface import RetinaFace

# Thư mục gốc của dự án
BASE_DIR = Path(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__))))).resolve()
# Thư mục chứa các mô hình
MODELS_DIR = BASE_DIR / 'app' / 'models'

class DetectedFace:
    def __init__(self, bbox, landmarks=None, confidence=None):
        self.bbox = bbox
        self.landmarks = landmarks
        self.confidence = confidence

class ArcFaceRecognizer:
    def __init__(self):
        model_dir = MODELS_DIR
        recog_model_path = os.path.join(model_dir, 'w600k_r50.onnx')
        self._recognizer = ArcFaceONNX(recog_model_path)
        self._recognizer.prepare(ctx_id=0)  # Use GPU if available

    def _convert_input_face(self, face: DetectedFace) -> Face:
        """Convert DetectedFace to InsightFace Face object"""
        try:
            kps = np.array([ 
                face.landmarks["left_eye"], 
                face.landmarks["right_eye"], 
                face.landmarks["nose"], 
                face.landmarks["left_mouth"], 
                face.landmarks["right_mouth"]
            ], dtype=np.float32)
            
            return Face(
                bbox=np.array([ 
                    face.bbox["x"], 
                    face.bbox["y"], 
                    face.bbox["x"] + face.bbox["w"], 
                    face.bbox["y"] + face.bbox["h"]
                ]),
                kps=kps,
                det_score=face.confidence
            )
        except Exception as e:
            log_error(f"❌ Error converting face: {str(e)}")
            return None

    def infer(self, image: np.ndarray, face: DetectedFace) -> Optional[np.ndarray]:
        """Extract face embedding from image"""
        try:
            converted_face = self._convert_input_face(face)
            if converted_face is None:
                return None

            aligned_face = norm_crop(image, converted_face.kps)
            if aligned_face is None:
                return None

            features = self._recognizer.get_feat(aligned_face)
            if features is not None and len(features.shape) == 2 and features.shape[0] == 1:
                features = features.squeeze(0)
            return features

        except Exception as e:
            log_error(f"❌ Error in face recognition: {str(e)}")
            return None

class FaceAuthManager:
    """
    Quản lý xác thực khuôn mặt sử dụng mô hình InsightFace
    Sử dụng mẫu Singleton để đảm bảo chỉ tải model một lần
    """
    _instance = None
    _loading_lock = threading.Lock()
    _detection_pool = ThreadPoolExecutor(max_workers=1)  # Chỉ xử lý 1 frame tại một thời điểm

    def __new__(cls):
        if cls._instance is None:
            log_info("🟢 Tạo instance mới của FaceAuthManager...")
            cls._instance = super(FaceAuthManager, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, '_initialized', False):
            return

        log_info("🟢 Đang khởi tạo FaceAuthManager...")
        
        # Khởi tạo các thuộc tính cơ bản
        self.models_ready = False
        self.use_real_model = False
        self.face_detector = None
        self.face_recognizer = None
        self.customer_db = None
        
        # Tối ưu các ngưỡng cho xác thực thời gian thực
        self.detection_confidence_threshold = 0.15  # Giảm ngưỡng phát hiện để dễ nhận diện hơn
        self.recognition_threshold = 0.25  # Giảm ngưỡng nhận dạng
        self.max_faces_per_frame = 1  # Chỉ xử lý 1 khuôn mặt

        # Cache và throttling settings
        self._last_detection_time = 0
        self._detection_cache = None
        self._detection_cache_ttl = 0.1  # 100ms giữa các lần phát hiện
        self._frame_skip_count = 0
        self._process_every_n_frames = 2  # Xử lý 1 frame trong mỗi 2 frame để giảm tải

        # Session tracking
        self._last_auth_attempt = {}
        self._auth_attempt_timeout = 15  # Thời gian tối thiểu giữa các lần thử
        self._guest_mode_timeout = 15  # Chuyển chế độ khách sau 15 giây không xác thực được
        self._max_auth_attempts = 5  # Số lần thử xác thực tối đa
        self._auth_attempts = {}

        # Performance tracking
        self.last_detection_time = 0.0
        self.total_detection_time = 0.0
        self.detection_count = 0
        self._cache_hits = 0
        self._cache_misses = 0
        self._detection_errors = 0
        self._recognition_errors = 0

        # Cache cho embeddings
        self.all_customer_embeddings = []
        self.embeddings_loaded = False
        self._loading_embeddings = False
        self._loading_lock = threading.Lock()
        self._last_embedding_load_time = None
        self._embedding_cache_ttl = 300  # 5 minutes

        # Frame processing metrics
        self._frame_count = 0
        self._processed_frames = 0
        self._skipped_frames = 0
        self._frame_processing_times = []
        self._last_frame_time = None
        self._frame_interval = 0.1  # 100ms between frames
        self._min_processing_time = float('inf')
        self._max_processing_time = 0
        self._total_processing_time = 0
        
        # Session tracking
        self._last_auth_attempt = {}  # Track last auth attempt per session
        self._auth_attempt_timeout = 30  # 30 seconds between auth attempts
        self._guest_mode_timeout = 180  # 3 minutes before allowing guest mode
        self._max_auth_attempts = 3  # Maximum number of authentication attempts
        self._auth_attempts = {}  # Track number of attempts per session
        
        try:
            # Khởi tạo customer database
            self.customer_db = CustomerDB()
            
            # Khởi tạo models trong thread riêng
            self._initialize_models_async()
            
            self._initialized = True
            log_info("✅ FaceAuthManager initialized with basic settings")

        except Exception as e:
            log_error(f"❌ Lỗi khởi tạo FaceAuthManager: {str(e)}")
            self._initialized = False
            raise

    def _initialize_models_async(self):
        """Khởi tạo models trong thread riêng"""
        def init_models():
            try:
                log_info("🚀 Bắt đầu khởi tạo models...")
                self._initialize_models()
                self.models_ready = True
                self.use_real_model = True
                log_info("✅ Models khởi tạo thành công")
                
                # Preload embeddings sau khi models đã sẵn sàng
                log_info("🚀 Bắt đầu preload face embeddings...")
                self._preload_embeddings_sync()
                
            except Exception as e:
                log_error(f"❌ Lỗi khởi tạo models: {str(e)}")
                self.models_ready = False
                self.use_real_model = False

        # Chạy trong thread riêng
        threading.Thread(target=init_models, daemon=True).start()

    def _initialize_models(self):
        """Khởi tạo models từ model_manager"""
        try:
            model_dir = MODELS_DIR
            det_model_path = os.path.join(model_dir, 'det_10g.onnx')
            
            if not os.path.exists(det_model_path):
                raise FileNotFoundError(f"Detection model not found at {det_model_path}")
            
            log_info(f"📦 Loading RetinaFace model from {det_model_path}")
            
            # Initialize RetinaFace model with optimized settings
            self.face_detector = get_model(det_model_path)
            if self.face_detector is None:
                raise RuntimeError("Failed to initialize face detector")
                
            # Prepare model với cấu hình tối ưu
            self.face_detector.prepare(
                ctx_id=-1, 
                input_size=(640, 640), 
                det_thresh=self.detection_confidence_threshold
            )
            log_info("✅ RetinaFace loaded successfully")

            # Khởi tạo face recognizer
            recog_model_path = os.path.join(model_dir, 'w600k_r50.onnx')
            if not os.path.exists(recog_model_path):
                raise FileNotFoundError(f"Recognition model not found at {recog_model_path}")
            
            self.face_recognizer = ArcFaceRecognizer()
            if self.face_recognizer is None:
                raise RuntimeError("Failed to initialize face recognizer")

            log_info("✅ Face recognition models initialized successfully")

        except Exception as e:
            log_error(f"❌ Error initializing models: {str(e)}")
            raise

    def recognize_face(self, frame):
        """Detect and recognize face in a single frame."""
        result = {'match': None, 'bbox': None, 'confidence': None, 'embedding': None}

        if frame is None:
            return result

        # Kiểm tra thời gian giữa các lần xử lý
        current_time = time.time()
        if current_time - self._last_detection_time < self._detection_cache_ttl:
            return result
        self._last_detection_time = current_time

        try:
            # Detect faces using RetinaFace
            bboxes, landmarks = self.face_detector.detect(frame, max_num=1, metric='default')
            
            if len(bboxes) == 0:
                return result  # Không phát hiện được khuôn mặt

            # Lấy khuôn mặt có độ tin cậy cao nhất
            bbox = bboxes[0]
            x1, y1, x2, y2, conf = bbox
            
            if conf < self.detection_confidence_threshold:
                return result  # Độ tin cậy quá thấp

            # Extract the bounding box and landmarks
            x1, y1, x2, y2 = bbox[:4].astype(int)
            result['bbox'] = [int(x1), int(y1), int(x2), int(y2)]
            result['confidence'] = float(conf)

            # Create a DetectedFace object with landmarks and bbox
            landmarks = landmarks[0]
            if landmarks.ndim == 2:
                landmarks = landmarks.flatten()

            try:
                face = DetectedFace(
                    bbox={"x": float(x1), "y": float(y1), "w": float(x2 - x1), "h": float(y2 - y1)},
                    landmarks={
                        "left_eye": (float(landmarks[0]), float(landmarks[1])),
                        "right_eye": (float(landmarks[2]), float(landmarks[3])),
                        "nose": (float(landmarks[4]), float(landmarks[5])),
                        "left_mouth": (float(landmarks[6]), float(landmarks[7])),
                        "right_mouth": (float(landmarks[8]), float(landmarks[9])),
                    },
                    confidence=float(conf)
                )

            except Exception as e:
                log_error(f"❌ Lỗi khi tạo landmark cho ảnh: {str(e)}")
                return result

            # Extract features using ArcFace
            embedding = self.face_recognizer.infer(frame, face)
            
            if embedding is not None and len(embedding.shape) == 2 and embedding.shape[0] == 1:
                embedding = embedding.squeeze(0)

            # Kiểm tra embedding hợp lệ
            if embedding is None or embedding.ndim != 1 or np.linalg.norm(embedding) == 0:
                log_error("❌ Embedding từ frame không hợp lệ.")
                result['match'] = False
                return result

            # Lưu embedding vào kết quả
            result['embedding'] = embedding

            # Compare with database
            match_info = self._find_matching_face_optimized(embedding)
            result['match'] = match_info if match_info else False

            return result

        except Exception as e:
            log_error(f"❌ Error during face recognition: {str(e)}")
            return result

    def verify_face_realtime(self, image, session_id: str = None, threshold=None):
        """Xác thực khuôn mặt thời gian thực với session tracking"""
        log_info(f"🔍 Starting face verification for session {session_id}")
        frame_start_time = time.time()
        self._frame_count += 1
        
        # Validate input
        if image is None:
            log_error("❌ Input image is None")
            return {
                'success': False,
                'message': 'Không có hình ảnh đầu vào',
                'can_switch_guest': False,
                'frame_metrics': {
                    'frame_number': self._frame_count,
                    'error': 'No input image'
                }
            }

        # Log frame interval
        if self._last_frame_time is not None:
            frame_interval = frame_start_time - self._last_frame_time
            log_info(f"⏱️ Frame interval: {frame_interval*1000:.1f}ms")
        self._last_frame_time = frame_start_time

        if threshold is None:
            threshold = self.recognition_threshold
            log_info(f"📊 Using default recognition threshold: {threshold}")

        # Kiểm tra thời gian giữa các lần xử lý
        current_time = time.time()
        if current_time - self._last_detection_time < self._detection_cache_ttl:
            self._skipped_frames += 1
            log_info(f"⏭️ Skipping frame {self._frame_count} (processing previous frame, cache TTL: {self._detection_cache_ttl*1000:.1f}ms)")
            return {
                'success': False,
                'message': 'Đang xử lý frame trước đó',
                'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                'frame_metrics': {
                    'frame_number': self._frame_count,
                    'skipped': True,
                    'processing_time': 0,
                    'cache_ttl': self._detection_cache_ttl
                }
            }
        self._last_detection_time = current_time

        # Ghi lại thời điểm thử xác thực nếu có session_id
        if session_id:
            self.record_auth_attempt(session_id)
            log_info(f"📝 Recorded auth attempt for session {session_id}")

        try:
            # Validate model readiness
            if not self.models_ready:
                log_error("❌ Face detection models not ready")
                return {
                    'success': False,
                    'message': 'Hệ thống nhận diện khuôn mặt chưa sẵn sàng',
                    'can_switch_guest': False,
                    'frame_metrics': {
                        'frame_number': self._frame_count,
                        'error': 'Models not ready'
                    }
                }

            # Detect faces using RetinaFace with optimized settings
            detection_start = time.time()
            log_info(f"🔍 Starting face detection on image shape: {image.shape}")
            bboxes, landmarks = self.face_detector.detect(image, max_num=1, metric='default')
            detection_time = time.time() - detection_start
            log_info(f"🔍 Face detection completed in {detection_time*1000:.1f}ms")
            
            if len(bboxes) == 0:
                processing_time = time.time() - frame_start_time
                self._update_processing_metrics(processing_time)
                log_info("❌ No faces detected in frame")
                return {
                    'success': False,
                    'message': 'Không phát hiện khuôn mặt',
                    'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                    'frame_metrics': {
                        'frame_number': self._frame_count,
                        'detection_time': detection_time,
                        'processing_time': processing_time
                    }
                }

            # Lấy khuôn mặt có độ tin cậy cao nhất
            bbox = bboxes[0]
            x1, y1, x2, y2, conf = bbox
            log_info(f"🎯 Detected face with confidence: {conf:.3f}")
            
            if conf < self.detection_confidence_threshold:
                processing_time = time.time() - frame_start_time
                self._update_processing_metrics(processing_time)
                log_info(f"❌ Face confidence {conf:.3f} below threshold {self.detection_confidence_threshold}")
                return {
                    'success': False,
                    'message': 'Khuôn mặt không đủ rõ ràng',
                    'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                    'frame_metrics': {
                        'frame_number': self._frame_count,
                        'detection_time': detection_time,
                        'processing_time': processing_time,
                        'confidence': conf,
                        'threshold': self.detection_confidence_threshold
                    }
                }

            # Extract the bounding box and landmarks
            x1, y1, x2, y2 = bbox[:4].astype(int)
            landmarks = landmarks[0]
            if landmarks.ndim == 2:
                landmarks = landmarks.flatten()

            # Tạo DetectedFace object với landmarks và bbox
            try:
                face = DetectedFace(
                    bbox={"x": float(x1), "y": float(y1), "w": float(x2 - x1), "h": float(y2 - y1)},
                    landmarks={
                        "left_eye": (float(landmarks[0]), float(landmarks[1])),
                        "right_eye": (float(landmarks[2]), float(landmarks[3])),
                        "nose": (float(landmarks[4]), float(landmarks[5])),
                        "left_mouth": (float(landmarks[6]), float(landmarks[7])),
                        "right_mouth": (float(landmarks[8]), float(landmarks[9])),
                    },
                    confidence=float(conf)
                )
                log_info(f"✅ Created DetectedFace object with bbox: {face.bbox}")
            except Exception as e:
                log_error(f"❌ Error creating DetectedFace object: {str(e)}")
                processing_time = time.time() - frame_start_time
                self._update_processing_metrics(processing_time)
                return {
                    'success': False,
                    'message': 'Lỗi xử lý khuôn mặt',
                    'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                    'frame_metrics': {
                        'frame_number': self._frame_count,
                        'detection_time': detection_time,
                        'processing_time': processing_time,
                        'error': str(e)
                    }
                }

            # Extract embedding
            recognition_start = time.time()
            log_info("🔍 Starting face recognition")
            embedding = self.face_recognizer.infer(image, face)
            recognition_time = time.time() - recognition_start
            log_info(f"🔍 Face recognition completed in {recognition_time*1000:.1f}ms")

            if embedding is not None and len(embedding.shape) == 2 and embedding.shape[0] == 1:
                embedding = embedding.squeeze(0)

            if embedding is None or embedding.ndim != 1 or np.linalg.norm(embedding) == 0:
                processing_time = time.time() - frame_start_time
                self._update_processing_metrics(processing_time)
                log_error("❌ Invalid face embedding extracted")
                return {
                    'success': False,
                    'message': 'Không thể trích xuất đặc trưng khuôn mặt',
                    'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                    'frame_metrics': {
                        'frame_number': self._frame_count,
                        'detection_time': detection_time,
                        'recognition_time': recognition_time,
                        'processing_time': processing_time
                    }
                }

            # Compare with database
            matching_start = time.time()
            log_info("🔍 Starting face matching")
            match_info = self._find_matching_face_optimized(embedding, threshold)
            matching_time = time.time() - matching_start
            log_info(f"🔍 Face matching completed in {matching_time*1000:.1f}ms")

            processing_time = time.time() - frame_start_time
            self._update_processing_metrics(processing_time)
            self._processed_frames += 1

            result = {
                'success': bool(match_info),
                'customer': match_info if match_info else None,
                'can_switch_guest': False if match_info else self.can_switch_to_guest(session_id) if session_id else False,
                'frame_metrics': {
                    'frame_number': self._frame_count,
                    'detection_time': detection_time,
                    'recognition_time': recognition_time,
                    'matching_time': matching_time,
                    'total_processing_time': processing_time,
                    'confidence': conf
                }
            }

            if match_info:
                log_info(f"✅ Face authentication successful: {match_info}")
            else:
                log_info("❌ No matching face found in database")
                result['message'] = 'Không tìm thấy khách hàng khớp'

            return result

        except Exception as e:
            log_error(f"❌ Error in real-time face verification: {str(e)}")
            processing_time = time.time() - frame_start_time
            self._update_processing_metrics(processing_time)
            return {
                'success': False,
                'message': 'Lỗi xử lý khuôn mặt',
                'can_switch_guest': self.can_switch_to_guest(session_id) if session_id else False,
                'frame_metrics': {
                    'frame_number': self._frame_count,
                    'processing_time': processing_time,
                    'error': str(e)
                }
            }

    def _update_processing_metrics(self, processing_time: float):
        """Cập nhật các metrics xử lý frame"""
        self._frame_processing_times.append(processing_time)
        self._min_processing_time = min(self._min_processing_time, processing_time)
        self._max_processing_time = max(self._max_processing_time, processing_time)
        self._total_processing_time += processing_time

        # Log metrics mỗi 10 frames
        if self._frame_count % 10 == 0:
            avg_time = self._total_processing_time / max(1, self._processed_frames)
            log_info(f"""
📊 Frame Processing Metrics:
- Total frames: {self._frame_count}
- Processed frames: {self._processed_frames}
- Skipped frames: {self._skipped_frames}
- Min processing time: {self._min_processing_time*1000:.1f}ms
- Max processing time: {self._max_processing_time*1000:.1f}ms
- Average processing time: {avg_time*1000:.1f}ms
- Processing rate: {self._processed_frames/max(1, self._frame_count)*100:.1f}%
""")

    def get_frame_metrics(self) -> Dict[str, Any]:
        """Lấy thống kê về xử lý frame"""
        avg_time = self._total_processing_time / max(1, self._processed_frames)
        return {
            'total_frames': self._frame_count,
            'processed_frames': self._processed_frames,
            'skipped_frames': self._skipped_frames,
            'min_processing_time': self._min_processing_time,
            'max_processing_time': self._max_processing_time,
            'average_processing_time': avg_time,
            'processing_rate': self._processed_frames/max(1, self._frame_count)*100
        }

    def _find_matching_face_optimized(self, embedding, threshold=0.35):
        """Tìm khuôn mặt khớp trong database với tối ưu hóa"""
        if not self.embeddings_loaded:
            self.load_all_embeddings()

        best_match_info = None
        max_similarity = -1.0

        try:
            for customer in self.all_customer_embeddings:
                for db_embedding in customer['embeddings']:
                    if db_embedding.ndim != 1 or db_embedding.size == 0:
                        continue

                    if embedding.shape != db_embedding.shape:
                        continue

                    similarity = np.dot(embedding, db_embedding) / (
                        np.linalg.norm(embedding) * np.linalg.norm(db_embedding)
                    )
                    similarity = float(similarity)

                    if similarity > max_similarity:
                        max_similarity = similarity
                        best_match_info = {
                            'name': customer['customer_name'],
                            'id': customer['customer_id'],
                            'similarity': similarity
                        }

            if best_match_info and max_similarity >= threshold:
                log_info(f"🎯 Match found: {best_match_info['name']} (ID: {best_match_info['id']}), Similarity: {max_similarity:.4f}")
                return {'name': best_match_info['name'], 'id': best_match_info['id']}

            return None

        except Exception as e:
            log_error(f"❌ Error finding matching face: {str(e)}")
            return None

    def get_face_embedding(self, image, return_detection_info=False):
        """
        Trích xuất vector đặc trưng khuôn mặt từ hình ảnh - Optimized version

        Args:
            image: Hình ảnh đầu vào (numpy.ndarray từ camera)
            return_detection_info: Có trả về thông tin detection (bbox, confidence) không

        Returns:
            numpy.ndarray hoặc tuple:
            - Nếu return_detection_info=False: Vector đặc trưng khuôn mặt hoặc None
            - Nếu return_detection_info=True: (embedding, detection_info) hoặc (None, None)
        """
        start_time = time.time()

        try:
            log_info(f"🔍 get_face_embedding: use_real_model={self.use_real_model}, image_shape={image.shape if image is not None else 'None'}")

            if not self.use_real_model or self.face_detector is None:
                log_warning("⚠️ Sử dụng mô hình giả lập - không có mô hình thực!")
                # Sử dụng vector giả lập nếu không có mô hình thực
                embedding = np.random.rand(512).astype(np.float32)
                embedding = embedding / np.linalg.norm(embedding)

                if return_detection_info:
                    # Tạo bounding box giả lập cho demo
                    h, w = image.shape[:2] if image is not None else (480, 640)
                    fake_bbox = [w//4, h//4, 3*w//4, 3*h//4]  # Giả lập bbox ở giữa
                    detection_info = {
                        'bbox': fake_bbox,
                        'confidence': 0.95,
                        'landmarks': None
                    }
                    log_info(f"🎭 Tạo fake detection: bbox={fake_bbox}, confidence=0.95")
                    return embedding, detection_info
                return embedding

            # Phát hiện khuôn mặt với model tối ưu
            detected_faces = self._detect_faces_optimized(image)

            if not detected_faces:
                log_warning("❌ Không phát hiện khuôn mặt trong hình ảnh")
                if return_detection_info:
                    return None, None
                return None

            # Lấy khuôn mặt có độ tin cậy cao nhất
            best_face = detected_faces[0]
            bbox = best_face['bbox']
            confidence = best_face['confidence']
            landmarks = best_face.get('landmarks', [])

            log_info(f"✅ Phát hiện khuôn mặt: bbox={bbox}, confidence={confidence:.3f}")

            # Chuẩn bị thông tin detection để trả về
            detection_info = {
                'bbox': bbox,  # [x1, y1, x2, y2]
                'confidence': confidence,
                'landmarks': landmarks
            }

            # Trích xuất embedding từ face region
            embedding = self._extract_embedding_optimized(image, bbox)

            # Update performance metrics
            detection_time = time.time() - start_time
            self.last_detection_time = detection_time
            self.detection_count += 1
            self.total_detection_time += detection_time

            if return_detection_info:
                return embedding, detection_info
            return embedding

        except Exception as e:
            log_error(f"❌ Lỗi khi trích xuất đặc trưng khuôn mặt: {str(e)}")
            if return_detection_info:
                return None, None
            return None

    def _detect_faces_optimized(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """
        Phát hiện khuôn mặt tối ưu với ONNX model - Improved version
        """
        try:
            if self.face_detector is None:
                log_warning("⚠️ Face detector is None")
                return []

            log_info(f"🔍 Starting face detection on image shape: {image.shape}")

            # Check if we can use cached result
            current_time = time.time()
            if (self._detection_cache is not None and
                current_time - self._last_detection_time < self._detection_cache_ttl):
                self._cache_hits = getattr(self, '_cache_hits', 0) + 1
                log_info(f"📋 Using cached detection result (age: {(current_time - self._last_detection_time)*1000:.1f}ms)")
                return self._detection_cache

            self._cache_misses = getattr(self, '_cache_misses', 0) + 1

            # Run detection directly on the image
            try:
                faces = self._run_detection(image, 1.0, 1.0, image.shape)

                # Enhanced face filtering
                valid_faces = []
                for face in faces:
                    if face['confidence'] > self.detection_confidence_threshold:
                        valid_faces.append(face)

                # Sort by confidence
                valid_faces.sort(key=lambda x: x['confidence'], reverse=True)

                # Limit max faces
                valid_faces = valid_faces[:self.max_faces_per_frame]

                # Cache result
                self._detection_cache = valid_faces
                self._last_detection_time = current_time

                log_info(f"🎯 Detection complete: {len(valid_faces)} high-quality faces found")
                return valid_faces

            except Exception as detection_error:
                log_error(f"❌ Detection execution error: {str(detection_error)}")
                self._detection_errors = getattr(self, '_detection_errors', 0) + 1
                return self._detection_cache or []

        except Exception as e:
            log_error(f"❌ Face detection error: {str(e)}")
            import traceback
            log_error(f"❌ Traceback: {traceback.format_exc()}")
            self._detection_errors = getattr(self, '_detection_errors', 0) + 1
            return []

    def _run_detection(self, processed_image: np.ndarray, scale_x: float, scale_y: float,
                      original_shape: Tuple[int, int, int]) -> List[Dict[str, Any]]:
        """Helper method to run actual detection in thread"""
        try:
            # Use the detect method instead of run
            bboxes, kpss = self.face_detector.detect(processed_image, max_num=self.max_faces_per_frame)
            
            faces = []
            if bboxes.shape[0] > 0:
                for i in range(bboxes.shape[0]):
                    bbox = bboxes[i, 0:4]
                    confidence = float(bboxes[i, 4])
                    
                    # Scale bbox back to original image coordinates
                    x1 = int(bbox[0] / scale_x)
                    y1 = int(bbox[1] / scale_y)
                    x2 = int(bbox[2] / scale_x)
                    y2 = int(bbox[3] / scale_y)
                    
                    # Clamp coordinates
                    h, w = original_shape[:2]
                    x1 = max(0, min(x1, w-1))
                    y1 = max(0, min(y1, h-1))
                    x2 = max(0, min(x2, w-1))
                    y2 = max(0, min(y2, h-1))
                    
                    if x2 <= x1 or y2 <= y1:
                        continue
                        
                    # Extract landmarks if available
                    landmarks = []
                    if kpss is not None and i < kpss.shape[0]:
                        kps = kpss[i]
                        for j in range(kps.shape[0]):
                            lx = int(kps[j, 0] / scale_x)
                            ly = int(kps[j, 1] / scale_y)
                            landmarks.append([lx, ly])
                    
                    face_info = {
                        'bbox': [x1, y1, x2, y2],
                        'confidence': confidence,
                        'landmarks': landmarks,
                        'area': (x2 - x1) * (y2 - y1)
                    }
                    
                    faces.append(face_info)
            
            return faces
            
        except Exception as e:
            log_error(f"❌ Error in _run_detection: {str(e)}")
            return []

    def _extract_embedding_optimized(self, image: np.ndarray, bbox: List[int]) -> Optional[np.ndarray]:
        """
        Extract embedding từ face region tối ưu
        """
        try:
            if self.face_recognizer is None:
                log_error("❌ Face recognizer is not initialized")
                return None

            # Extract face region with margin
            face_region = self._extract_face_region(image, bbox)
            if face_region is None or face_region.size == 0:
                log_error("❌ Failed to extract face region")
                return None

            # Create DetectedFace object with bbox
            detected_face = DetectedFace(
                bbox={
                    'x': bbox[0],
                    'y': bbox[1],
                    'w': bbox[2] - bbox[0],
                    'h': bbox[3] - bbox[1]
                }
            )

            # Get embedding using face recognizer
            try:
                embedding = self.face_recognizer.infer(image, detected_face)
                if embedding is None:
                    log_error("❌ Face recognizer returned None embedding")
                    return None

                # Normalize embedding
                embedding = embedding / np.linalg.norm(embedding)
                return embedding

            except Exception as e:
                log_error(f"❌ Error during face recognition: {str(e)}")
                return None

        except Exception as e:
            log_error(f"❌ Error in _extract_embedding_optimized: {str(e)}")
            return None

    def _extract_face_region(self, image: np.ndarray, bbox: List[int], margin: float = 0.2) -> Optional[np.ndarray]:
        """
        Extract face region từ image với margin
        """
        try:
            x1, y1, x2, y2 = bbox
            h, w = image.shape[:2]

            # Add margin
            face_w = x2 - x1
            face_h = y2 - y1
            margin_w = int(face_w * margin)
            margin_h = int(face_h * margin)

            # Expand bbox with margin
            x1_exp = max(0, x1 - margin_w)
            y1_exp = max(0, y1 - margin_h)
            x2_exp = min(w, x2 + margin_w)
            y2_exp = min(h, y2 + margin_h)

            # Extract face region
            face_region = image[y1_exp:y2_exp, x1_exp:x2_exp]

            return face_region

        except Exception as e:
            log_error(f"❌ Lỗi _extract_face_region: {str(e)}")
            return None

    def _preprocess_face(self, face_image: np.ndarray) -> np.ndarray:
        """
        Preprocess face image cho recognition model
        """
        # Resize to model input size
        resized = cv2.resize(face_image, (112, 112))

        # Convert to RGB
        rgb_image = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

        # Normalize to [-1, 1]
        normalized = (rgb_image.astype(np.float32) - 127.5) / 127.5

        # Transpose to CHW format and add batch dimension
        input_tensor = np.transpose(normalized, (2, 0, 1))[np.newaxis, ...]

        return input_tensor

    def can_switch_to_guest(self, session_id: str) -> bool:
        """Kiểm tra xem có thể chuyển sang guest mode không"""
        if not session_id:
            return False  # Không cho phép chuyển guest mode nếu không có session_id
            
        if session_id not in self._last_auth_attempt:
            return False  # Không cho phép chuyển guest mode nếu chưa có lần thử nào
            
        last_attempt = self._last_auth_attempt[session_id]
        time_since_attempt = time.time() - last_attempt
        
        # Kiểm tra số lần thử xác thực
        attempts = self._auth_attempts.get(session_id, 0)
        if attempts >= self._max_auth_attempts:
            log_info(f"✅ Cho phép chuyển guest mode sau {attempts} lần thử")
            return True
            
        # Chỉ cho phép chuyển guest mode sau khi đã đợi đủ thời gian
        if time_since_attempt >= self._guest_mode_timeout:
            log_info(f"✅ Cho phép chuyển guest mode sau {time_since_attempt:.1f}s")
            return True
            
        log_info(f"⏳ Chưa đủ điều kiện chuyển guest mode: {time_since_attempt:.1f}s < {self._guest_mode_timeout}s")
        return False

    def record_auth_attempt(self, session_id: str):
        """Ghi lại thời điểm thử xác thực"""
        if not session_id:
            return
            
        current_time = time.time()
        self._last_auth_attempt[session_id] = current_time
        self._auth_attempts[session_id] = self._auth_attempts.get(session_id, 0) + 1
        
        log_info(f"📝 Ghi nhận lần thử xác thực {self._auth_attempts[session_id]} cho session {session_id}")

    def get_performance_stats(self) -> Dict[str, Any]:
        """Lấy thống kê hiệu suất"""
        return {
            'total_detections': self.detection_count,
            'avg_detection_time': self.total_detection_time / max(1, self.detection_count),
            'cache_hits': self._cache_hits,
            'cache_misses': self._cache_misses,
            'detection_errors': self._detection_errors,
            'recognition_errors': self._recognition_errors,
            'embeddings_loaded': self.embeddings_loaded,
            'total_customers': len(self.all_customer_embeddings)
        }

    def _preload_embeddings_sync(self):
        """Tải embedding đồng bộ ngay khi khởi tạo"""
        try:
            success = self.load_all_embeddings(force_reload=True)
            if success:
                log_info(f"✅ Preload thành công {len(self.all_customer_embeddings)} customer embeddings")
            else:
                log_warning("⚠️ Preload embeddings thất bại, sẽ tải lazy khi cần")
        except Exception as e:
            log_error(f"❌ Lỗi khi preload embeddings: {str(e)}")

    def get_embeddings_stats(self):
        """Lấy thống kê về embeddings đã tải"""
        if not self.embeddings_loaded:
            return {
                'loaded': False,
                'total_customers': 0,
                'total_embeddings': 0,
                'load_time': None
            }

        total_embeddings = sum(len(customer['embeddings']) for customer in self.all_customer_embeddings)
        return {
            'loaded': True,
            'total_customers': len(self.all_customer_embeddings),
            'total_embeddings': total_embeddings,
            'load_time': self._last_embedding_load_time,
            'cache_ttl': self._embedding_cache_ttl
        }

    def preload_embeddings_async(self):
        """Preload face embeddings asynchronously"""
        try:
            # Chỉ load face detection model nếu chưa được load
            from app.models.model_manager import ModelManager
            model_manager = ModelManager()
            if not model_manager.face_detection_model:
                model_manager._load_face_detection_model()
                log_info("✅ Face detection model loaded successfully")
            
            # Load face embeddings
            self._load_face_embeddings()
            log_info("✅ Face embeddings loaded successfully")
        except Exception as e:
            log_error(f"❌ Error preloading face embeddings: {str(e)}")
            import traceback
            log_error(f"Error details: {traceback.format_exc()}")

    def load_all_embeddings(self, force_reload=False):
        """
        Tải tất cả embedding của khách hàng từ Neo4j
        Sử dụng lock để đảm bảo chỉ một thread tải embedding tại một thời điểm
        Sử dụng cache để tránh tải lại embedding quá thường xuyên

        Args:
            force_reload: Buộc tải lại embedding ngay cả khi cache còn hiệu lực

        Returns:
            bool: True nếu tải thành công, False nếu có lỗi
        """
        # Kiểm tra xem có thread khác đang tải embedding không
        if self._loading_embeddings:
            log_info("⏳ Đang có thread khác tải embedding, chờ hoàn thành...")
            # Chờ tối đa 5 giây
            start_time = time.time()
            while self._loading_embeddings and time.time() - start_time < 5:
                time.sleep(0.1)

            # Nếu đã tải xong, trả về kết quả
            if self.embeddings_loaded:
                return True
            else:
                log_warning("⏳ Chờ quá lâu cho thread khác tải embedding, tiếp tục với thread hiện tại")

        # Kiểm tra cache nếu không buộc tải lại
        if not force_reload and self.embeddings_loaded and self._last_embedding_load_time:
            # Kiểm tra xem cache có còn hiệu lực không
            cache_age = (datetime.now() - self._last_embedding_load_time).total_seconds()
            if cache_age < self._embedding_cache_ttl:
                log_info(f"✅ Sử dụng cache embedding (tuổi: {cache_age:.1f}s < TTL: {self._embedding_cache_ttl}s)")
                return True

        # Sử dụng lock để đảm bảo chỉ một thread tải embedding tại một thời điểm
        with self._loading_lock:
            # Kiểm tra lại sau khi có lock (có thể thread khác đã tải xong)
            if not force_reload and self.embeddings_loaded and self._last_embedding_load_time:
                cache_age = (datetime.now() - self._last_embedding_load_time).total_seconds()
                if cache_age < self._embedding_cache_ttl:
                    log_info(f"✅ Sử dụng cache embedding sau khi có lock (tuổi: {cache_age:.1f}s)")
                    return True

            # Đánh dấu đang tải embedding
            self._loading_embeddings = True

            try:
                log_info("📦 Đang tải tất cả embedding của khách hàng từ Neo4j...")

                # Query để lấy face embeddings thực tế từ database
                query = """
                MATCH (c:Customer)
                WHERE c.embedding IS NOT NULL
                RETURN c.id as id, c.name as name, c.embedding as embedding
                """

                log_info("🔍 Đang truy vấn face embeddings từ Neo4j...")
                result = execute_query_with_semaphore(
                    query,
                    use_cache=True,
                    max_retries=5,
                    retry_delay=2,
                    semaphore_timeout=30
                )

                if not result:
                    log_warning("❌ Không tìm thấy khách hàng nào có embedding trong cơ sở dữ liệu")
                    self.embeddings_loaded = False
                    return False

                log_info(f"✅ Tìm thấy {len(result)} khách hàng có embedding")

                # Xóa cache cũ
                self.all_customer_embeddings = []

                # Xử lý kết quả truy vấn
                for customer in result:
                    customer_id = customer['id']
                    customer_name = customer['name']

                    log_info(f"🔍 Xử lý khách hàng: {customer_name} (ID: {customer_id})")
                    log_info(f"📋 Dữ liệu khách hàng: {list(customer.keys())}")

                    # Kiểm tra format mới trước (4 embedding riêng biệt)
                    if 'embedding1' in customer:
                        log_info(f"📦 Tìm thấy format mới (4 embedding riêng biệt) cho {customer_name}")
                        embeddings = []
                        for i in range(1, 5):
                            emb_key = f'embedding{i}'
                            if customer.get(emb_key):
                                try:
                                    emb_data = json.loads(customer[emb_key])
                                    embeddings.append(np.array(emb_data, dtype=np.float32))
                                    log_info(f"✅ Tải embedding {i} cho {customer_name}")
                                except Exception as e:
                                    log_warning(f"❌ Lỗi tải embedding {i} cho {customer_name}: {str(e)}")
                                    continue

                        if embeddings:
                            self.all_customer_embeddings.append({
                                'customer_id': customer_id,
                                'customer_name': customer_name,
                                'embeddings': embeddings
                            })
                            log_info(f"✅ Tải {len(embeddings)} embedding cho khách hàng {customer_name}")
                        else:
                            log_warning(f"⚠️ Không có embedding hợp lệ nào cho {customer_name}")
                        continue

                    # Xử lý format cũ (embedding array)
                    embedding_data = customer.get('embedding')
                    if not embedding_data:
                        log_warning(f"❌ Không tìm thấy embedding của khách hàng {customer_name} (ID: {customer_id})")
                        continue

                    try:
                        # Debug: In ra format của embedding_data
                        log_info(f"🔍 Debug embedding format cho {customer_name}: type={type(embedding_data)}, len={len(embedding_data) if hasattr(embedding_data, '__len__') else 'N/A'}")
                        if hasattr(embedding_data, '__len__') and len(embedding_data) > 0:
                            log_info(f"🔍 First element type: {type(embedding_data[0])}, sample: {str(embedding_data[0])[:100]}...")

                        # Xử lý embedding data
                        parsed_embeddings = None

                        if isinstance(embedding_data, str):
                            # Embedding được lưu dưới dạng JSON string, cần parse
                            log_info(f"📝 Parsing JSON string embedding cho {customer_name}")
                            try:
                                parsed_embeddings = json.loads(embedding_data)
                                log_info(f"✅ Parse JSON thành công: type={type(parsed_embeddings)}, len={len(parsed_embeddings) if hasattr(parsed_embeddings, '__len__') else 'N/A'}")
                            except json.JSONDecodeError as e:
                                log_error(f"❌ Lỗi parse JSON cho {customer_name}: {str(e)}")
                                continue
                        elif isinstance(embedding_data, list):
                            # Embedding đã là list
                            parsed_embeddings = embedding_data
                            log_info(f"✅ Embedding đã là list cho {customer_name}")
                        else:
                            log_warning(f"❌ Format embedding không hỗ trợ cho {customer_name}: type={type(embedding_data)}")
                            continue

                        # Chuyển đổi embedding thành numpy array
                        if isinstance(parsed_embeddings, list) and len(parsed_embeddings) > 0:
                            numpy_embeddings = []
                            for i, emb in enumerate(parsed_embeddings):
                                if isinstance(emb, list) and len(emb) > 0:
                                    numpy_embedding = np.array(emb, dtype=np.float32)
                                    numpy_embeddings.append(numpy_embedding)
                                    log_info(f"✅ Tải embedding {i+1} cho {customer_name} (shape: {numpy_embedding.shape})")

                            if numpy_embeddings:
                                # Lưu thông tin khách hàng và embedding vào cache
                                self.all_customer_embeddings.append({
                                    'customer_id': customer_id,
                                    'customer_name': customer_name,
                                    'embeddings': numpy_embeddings
                                })
                                log_info(f"✅ Tải {len(numpy_embeddings)} embedding cho khách hàng {customer_name}")
                            else:
                                log_warning(f"⚠️ Không có embedding hợp lệ nào cho {customer_name}")
                        else:
                            log_warning(f"❌ Parsed embedding không phải list hợp lệ cho {customer_name}: type={type(parsed_embeddings)}")
                            continue

                    except Exception as e:
                        log_error(f"❌ Lỗi khi xử lý embedding của khách hàng {customer_name} (ID: {customer_id}): {str(e)}")
                        continue

                log_info(f"✅ Đã tải thành công embedding của {len(self.all_customer_embeddings)} khách hàng")
                self.embeddings_loaded = True
                self._last_embedding_load_time = datetime.now()
                return True

            except Exception as e:
                log_error(f"❌ Lỗi khi tải embedding của khách hàng: {str(e)}")
                self.embeddings_loaded = False
                return False
            finally:
                # Đảm bảo reset trạng thái đang tải
                self._loading_embeddings = False

    def verify_face(self, image, threshold=0.01, return_top_matches=True):
        """
        Xác minh khuôn mặt trong hình ảnh với cơ sở dữ liệu

        Args:
            image: Hình ảnh đầu vào (numpy.ndarray hoặc đường dẫn file)
            threshold: Ngưỡng độ tương đồng để xác định khớp
            return_top_matches: Trả về danh sách các khuôn mặt khớp nhất

        Returns:
            dict: Kết quả xác minh khuôn mặt bao gồm thông tin detection
        """
        # Kiểm tra xem đã tải embedding chưa (đã preload khi khởi tạo)
        if not self.embeddings_loaded:
            log_warning("❌ Embeddings chưa được preload, hệ thống chưa sẵn sàng")
            return {
                'success': False,
                'message': 'Hệ thống nhận diện khuôn mặt chưa sẵn sàng'
            }

        # Kiểm tra xem có embedding nào không
        if not self.all_customer_embeddings:
            log_warning("❌ Không có khách hàng nào có dữ liệu khuôn mặt trong cơ sở dữ liệu")
            return {
                'success': False,
                'message': 'Không có khách hàng nào có dữ liệu khuôn mặt trong cơ sở dữ liệu'
            }

        # Trích xuất đặc trưng khuôn mặt với thông tin detection
        embedding, detection_info = self.get_face_embedding(image, return_detection_info=True)
        if embedding is None:
            log_warning("❌ Không phát hiện khuôn mặt trong hình ảnh")
            return {
                'success': False,
                'message': 'Không phát hiện khuôn mặt trong hình ảnh',
                'bbox': None,
                'confidence': None
            }

        # So sánh với cơ sở dữ liệu
        result = self._find_matching_face(embedding, threshold)

        if result['success']:
            # Lấy thông tin chi tiết của khách hàng
            customer_id = result['customer_id']

            # Sử dụng cache cho thông tin khách hàng và đơn hàng
            try:
                customer_info = self.customer_db.get_customer_info(customer_id)
                customer_orders = self.customer_db.get_customer_orders(customer_id)
            except Exception as e:
                log_error(f"❌ Lỗi khi lấy thông tin khách hàng: {str(e)}")
                customer_info = None
                customer_orders = []

            log_info(f"✅ Xác minh khuôn mặt thành công: {result['customer_name']} (ID: {customer_id}, Similarity: {result['similarity']:.4f})")
            return {
                'success': True,
                'customer_id': customer_id,
                'customer_name': result['customer_name'],
                'similarity': result['similarity'],
                'customer_info': customer_info,
                'customer_orders': customer_orders,
                'top_matches': result.get('top_matches', []),
                # Thêm thông tin detection
                'bbox': detection_info['bbox'] if detection_info else None,
                'confidence': detection_info['confidence'] if detection_info else None,
                'landmarks': detection_info.get('landmarks') if detection_info else None
            }
        else:
            log_warning(f"❌ Xác minh khuôn mặt thất bại: {result['message']}")
            return {
                'success': False,
                'message': result['message'],
                'similarity': result.get('similarity'),
                'top_matches': result.get('top_matches', []),
                # Thêm thông tin detection ngay cả khi thất bại (để hiển thị bbox)
                'bbox': detection_info['bbox'] if detection_info else None,
                'confidence': detection_info['confidence'] if detection_info else None,
                'landmarks': detection_info.get('landmarks') if detection_info else None
            }

    def _find_matching_face(self, embedding, threshold=0.01):
        """
        Tìm khuôn mặt khớp trong cơ sở dữ liệu

        Args:
            embedding: Vector đặc trưng khuôn mặt
            threshold: Ngưỡng độ tương đồng

        Returns:
            dict: Kết quả tìm kiếm
        """
        # Giả định rằng embeddings đã được tải trước khi gọi phương thức này
        # Phương thức verify_face đã kiểm tra và tải embedding nếu cần

        # Kiểm tra xem có embedding nào không
        if not self.all_customer_embeddings:
            log_warning("❌ Không có khách hàng nào có dữ liệu khuôn mặt trong cơ sở dữ liệu")
            return {
                'success': False,
                'message': 'Không có khách hàng nào có dữ liệu khuôn mặt trong cơ sở dữ liệu'
            }

        best_match = None
        max_similarity = -1
        all_matches = []  # Danh sách tất cả các kết quả khớp

        # So sánh với tất cả embedding đã tải
        log_info(f"🔍 Bắt đầu so sánh với {len(self.all_customer_embeddings)} khách hàng trong database")

        for customer in self.all_customer_embeddings:
            customer_id = customer['customer_id']
            customer_name = customer['customer_name']
            customer_embeddings = customer['embeddings']

            for i, db_embedding in enumerate(customer_embeddings):
                # Tính độ tương đồng cosine
                similarity = np.dot(embedding, db_embedding) / (
                    np.linalg.norm(embedding) * np.linalg.norm(db_embedding)
                )

                log_info(f"📊 So sánh với {customer_name} (embedding {i+1}): similarity={float(similarity):.4f}")

                # Lưu kết quả khớp
                all_matches.append({
                    'customer_id': customer_id,
                    'customer_name': customer_name,
                    'similarity': float(similarity)
                })

                # Cập nhật kết quả khớp tốt nhất
                if similarity > max_similarity:
                    max_similarity = similarity
                    best_match = {
                        'customer_id': customer_id,
                        'customer_name': customer_name,
                        'similarity': float(similarity)
                    }
                    log_info(f"🎯 Tìm thấy match tốt hơn: {customer_name} với similarity={float(similarity):.4f}")

        # Sắp xếp tất cả kết quả khớp theo độ tương đồng giảm dần
        all_matches = sorted(all_matches, key=lambda x: x['similarity'], reverse=True)

        log_info(f"🏆 Kết quả so sánh: max_similarity={float(max_similarity):.4f}, threshold={threshold}")
        log_info(f"📋 Top 3 matches: {all_matches[:3]}")

        if best_match and max_similarity >= threshold:
            log_info(f"✅ Tìm thấy khách hàng khớp: {best_match['customer_name']} với similarity={float(max_similarity):.4f}")
            return {
                'success': True,
                'customer_id': best_match['customer_id'],
                'customer_name': best_match['customer_name'],
                'similarity': best_match['similarity'],
                'top_matches': all_matches[:5]  # Trả về 5 kết quả khớp tốt nhất
            }
        else:
            log_warning(f"❌ Không tìm thấy khách hàng khớp (max_similarity={float(max_similarity):.4f} < threshold={threshold})")
            return {
                'success': False,
                'message': 'Không tìm thấy khách hàng khớp với khuôn mặt này',
                'similarity': float(max_similarity) if max_similarity > -1 else None,
                'top_matches': all_matches[:5]  # Trả về 5 kết quả khớp tốt nhất
            }

    def update_settings(self, settings: Dict[str, Any]):
        """
        Cập nhật settings của face authentication
        """
        if 'detection_confidence_threshold' in settings:
            self.detection_confidence_threshold = settings['detection_confidence_threshold']
            log_info(f"✅ Updated detection_confidence_threshold: {self.detection_confidence_threshold}")

        if 'recognition_threshold' in settings:
            self.recognition_threshold = settings['recognition_threshold']
            log_info(f"✅ Updated recognition_threshold: {self.recognition_threshold}")

        if 'process_every_n_frames' in settings:
            self._process_every_n_frames = settings['process_every_n_frames']
            log_info(f"✅ Updated process_every_n_frames: {self._process_every_n_frames}")

        if 'detection_cache_ttl' in settings:
            self._detection_cache_ttl = settings['detection_cache_ttl']
            log_info(f"✅ Updated detection_cache_ttl: {self._detection_cache_ttl}")

        if 'max_faces_per_frame' in settings:
            self.max_faces_per_frame = settings['max_faces_per_frame']
            log_info(f"✅ Updated max_faces_per_frame: {self.max_faces_per_frame}")

        log_info(f"✅ FaceAuthManager settings updated: {settings}")

# Tạo singleton instance khi module được import
face_auth_manager = FaceAuthManager()
