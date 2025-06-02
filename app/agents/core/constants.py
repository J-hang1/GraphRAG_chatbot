"""
Constants for the application
"""

# Error messages
ERROR_MESSAGES = {
    # Face detection errors
    "FACE_NOT_FOUND": "Không tìm thấy khuôn mặt trong ảnh",
    "MULTIPLE_FACES": "Phát hiện nhiều khuôn mặt trong ảnh",
    "FACE_TOO_SMALL": "Khuôn mặt quá nhỏ",
    "FACE_TOO_LARGE": "Khuôn mặt quá lớn",
    "FACE_BLURRY": "Khuôn mặt bị mờ",
    "FACE_ANGLE": "Góc khuôn mặt không phù hợp",
    
    # Face recognition errors
    "FACE_NOT_RECOGNIZED": "Không nhận diện được khuôn mặt",
    "FACE_MATCH_LOW_CONFIDENCE": "Độ tin cậy nhận diện quá thấp",
    "FACE_EMBEDDING_FAILED": "Không thể tạo face embedding",
    
    # Face authentication errors
    "AUTH_TIMEOUT": "Hết thời gian xác thực",
    "AUTH_MAX_RETRIES": "Đã vượt quá số lần thử",
    "AUTH_CANCELLED": "Xác thực bị hủy",
    "AUTH_SYSTEM_ERROR": "Lỗi hệ thống xác thực",
    
    # Database errors
    "DB_CONNECTION_ERROR": "Lỗi kết nối database",
    "DB_QUERY_ERROR": "Lỗi truy vấn database",
    "DB_UPDATE_ERROR": "Lỗi cập nhật database",
    
    # Model errors
    "MODEL_LOAD_ERROR": "Lỗi tải model",
    "MODEL_INFERENCE_ERROR": "Lỗi suy luận model",
    "MODEL_VERSION_MISMATCH": "Phiên bản model không tương thích",
    
    # System errors
    "SYSTEM_ERROR": "Lỗi hệ thống",
    "MEMORY_ERROR": "Lỗi bộ nhớ",
    "GPU_ERROR": "Lỗi GPU",
    "CAMERA_ERROR": "Lỗi camera",
}

# Success messages
SUCCESS_MESSAGES = {
    # Face detection success
    "FACE_DETECTED": "Đã phát hiện khuôn mặt",
    "FACE_QUALITY_GOOD": "Chất lượng khuôn mặt tốt",
    
    # Face recognition success
    "FACE_RECOGNIZED": "Đã nhận diện khuôn mặt",
    "FACE_MATCH_HIGH_CONFIDENCE": "Độ tin cậy nhận diện cao",
    "FACE_EMBEDDING_CREATED": "Đã tạo face embedding thành công",
    
    # Face authentication success
    "AUTH_SUCCESS": "Xác thực thành công",
    "AUTH_COMPLETED": "Hoàn tất xác thực",
    
    # Database success
    "DB_CONNECTED": "Kết nối database thành công",
    "DB_QUERY_SUCCESS": "Truy vấn database thành công",
    "DB_UPDATE_SUCCESS": "Cập nhật database thành công",
    
    # Model success
    "MODEL_LOADED": "Đã tải model thành công",
    "MODEL_INFERENCE_SUCCESS": "Suy luận model thành công",
    
    # System success
    "SYSTEM_READY": "Hệ thống đã sẵn sàng",
    "SYSTEM_STARTED": "Hệ thống đã khởi động",
    "SYSTEM_STOPPED": "Hệ thống đã dừng",
}

# Face recognition constants
FACE_RECOGNITION_MODEL_PATH = "models/face_recognition"
FACE_RECOGNITION_THRESHOLD = 0.6
FACE_RECOGNITION_BATCH_SIZE = 32

# Face authentication constants
FACE_AUTH_MAX_RETRIES = 3
FACE_AUTH_TIMEOUT = 30  # seconds
FACE_AUTH_MIN_FACE_SIZE = 100  # pixels
FACE_AUTH_MAX_FACE_SIZE = 1000  # pixels

# Face detection constants
FACE_DETECTION_CONFIDENCE = 0.7
FACE_DETECTION_MIN_SIZE = 20  # pixels
FACE_DETECTION_MAX_SIZE = 1000  # pixels

# Face alignment constants
FACE_ALIGNMENT_SIZE = 112  # pixels
FACE_ALIGNMENT_MARGIN = 0.1  # 10% margin around face

# Face embedding constants
FACE_EMBEDDING_SIZE = 512  # dimensions
FACE_EMBEDDING_NORMALIZE = True

# Face database constants
FACE_DB_PATH = "data/face_db"
FACE_DB_INDEX_PATH = "data/face_db/index"
FACE_DB_BACKUP_PATH = "data/face_db/backup"

# Face logging constants
FACE_LOG_PATH = "logs/face_auth"
FACE_LOG_LEVEL = "INFO"
FACE_LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
FACE_LOG_MAX_SIZE = 10 * 1024 * 1024  # 10MB
FACE_LOG_BACKUP_COUNT = 5

# Cache settings
CACHE_SETTINGS = {
    "ttl": 3600,      # Time to live in seconds
    "max_size": 1000  # Maximum number of cache entries
}

# Query templates
QUERY_TEMPLATES = {
    "product": """
        MATCH (p:Product)-[:BELONGS_TO_CATEGORY]->(c:Category)
        MATCH (v:Variant)-[:PRODUCT_ID]->(p)
        WHERE {conditions}
        RETURN p.id as product_id, p.name as product_name, p.descriptions as product_description,
               c.id as category_id, c.name_cat as category_name, c.description as category_description,
               v.id as variant_id, v.`Beverage Option` as beverage_option,
               v.price as price, v.sugars_g as sugar, v.caffeine_mg as caffeine,
               v.calories as calories, v.protein_g as protein, v.sales_rank as sales_rank
        ORDER BY v.sales_rank ASC
        LIMIT 10
    """
}

# Statistical patterns for product analysis
STATISTICAL_PATTERNS = {
    "price_ranges": {
        "low": {"max": 30000},
        "medium": {"min": 30000, "max": 60000},
        "high": {"min": 60000}
    },
    "sugar_levels": {
        "low": {"max": 10},
        "medium": {"min": 10, "max": 25},
        "high": {"min": 25}
    },
    "caffeine_levels": {
        "low": {"max": 50},
        "medium": {"min": 50, "max": 150},
        "high": {"min": 150}
    },
    "calorie_levels": {
        "low": {"max": 100},
        "medium": {"min": 100, "max": 300},
        "high": {"min": 300}
    },
    "sales_rank_thresholds": {
        "top": {"max": 10},
        "popular": {"min": 10, "max": 50},
        "average": {"min": 50, "max": 100},
        "low": {"min": 100}
    }
} 