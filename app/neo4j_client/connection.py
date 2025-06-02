"""
Neo4j connection management - Tối ưu hóa với một file duy nhất
Cung cấp các chức năng kết nối, truy vấn và xử lý lỗi cho Neo4j
Thêm cơ chế semaphore, caching và tối ưu hóa connection pool
Tối ưu để tránh trường hợp nhiều yêu cầu kết nối đồng thời gây lỗi
"""
import os
import time
import random
import threading
import functools
import hashlib
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Callable
from neo4j import GraphDatabase, exceptions
from flask import current_app
from ..utils.logger import log_info, log_error, log_warning

# Global driver instance with lock for thread safety
_driver = None
_driver_lock = threading.Lock()
_session_pool = []
_session_pool_lock = threading.Lock()
_driver_initialized = False  # Biến theo dõi trạng thái khởi tạo
_initialization_in_progress = False  # Biến theo dõi quá trình khởi tạo
_initialization_time = None  # Thời điểm khởi tạo kết nối
_initialization_lock = threading.Lock()  # Lock cho quá trình khởi tạo

# Connection pool configuration
_max_connection_pool_size = 50  # Tăng số lượng kết nối tối đa để xử lý nhiều request đồng thời
_connection_acquisition_timeout = 60  # Tăng thời gian chờ để tránh timeout
_max_transaction_retry_time = 30  # Tăng thời gian tối đa để thử lại transaction (giây)
_connection_timeout = 30  # Tăng thời gian timeout cho kết nối (giây)
_max_session_pool_size = 20  # Tăng số lượng session tối đa trong pool
_connection_liveness_check_timeout = 10  # Thời gian kiểm tra kết nối còn sống (giây)
_connection_max_lifetime = 3600  # Thời gian sống tối đa của kết nối (giây)
_connection_warmup_count = 5  # Tăng số lượng kết nối khởi tạo sẵn khi startup
_max_initialization_wait_time = 60  # Tăng thời gian tối đa chờ khởi tạo (giây)

# Semaphore để giới hạn số lượng truy vấn đồng thời
_max_concurrent_queries = 20  # Tăng số lượng truy vấn đồng thời
_query_semaphore = threading.Semaphore(_max_concurrent_queries)
_query_timeout = 30  # Tăng thời gian chờ tối đa để lấy semaphore (giây)

# Circuit breaker configuration - tăng cường
_circuit_breaker_enabled = True
_circuit_breaker_threshold = 1  # Giảm ngưỡng để phát hiện lỗi sớm hơn
_circuit_breaker_timeout = 60  # Tăng thời gian chờ để tránh mở lại circuit quá sớm
_circuit_breaker_state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
_circuit_breaker_failure_count = 0
_circuit_breaker_last_failure_time = None
_circuit_breaker_lock = threading.Lock()
_circuit_breaker_reset_timeout = 120  # Tăng thời gian reset circuit breaker (giây)
_circuit_breaker_last_reset_time = None  # Thời điểm cuối cùng reset circuit breaker
_circuit_breaker_auto_reset = True  # Tự động reset circuit breaker sau một khoảng thời gian

# Health check configuration
_last_health_check = None
_health_check_interval = 15  # Kiểm tra sức khỏe kết nối thường xuyên hơn
_health_check_timeout = 5  # Thời gian timeout cho health check (giây)

# Simple cache configuration
_cache = {}  # {cache_key: (timestamp, data)}
_cache_lock = threading.Lock()
_cache_stats_lock = threading.Lock()  # Lock riêng cho việc cập nhật thống kê cache
_cache_ttl = 300  # Tăng thời gian sống của cache (giây)
_cache_enabled = True
_cache_size_limit = 500  # Tăng giới hạn số lượng mục trong cache
_cache_hit_count = 0  # Số lần cache hit
_cache_miss_count = 0  # Số lần cache miss

# Connection reuse configuration
_reuse_connection = True  # Tái sử dụng kết nối thay vì đóng và mở lại
_connection_reuse_count = 0  # Số lần tái sử dụng kết nối
_max_connection_reuse = 100  # Số lần tái sử dụng tối đa trước khi đóng kết nối

def get_neo4j_connection_params():
    """Get Neo4j connection parameters from config"""
    # Sử dụng giá trị mặc định nếu không tìm thấy trong config
    # Đảm bảo URI luôn có giá trị hợp lệ
    uri = 'bolt://localhost:7687'  # Giá trị mặc định

    # Thử lấy URI từ các nguồn khác nhau
    if current_app and current_app.config.get('NEO4J_URI'):
        uri = current_app.config.get('NEO4J_URI')
    elif os.environ.get('NEO4J_URI'):
        uri = os.environ.get('NEO4J_URI')

    # Đảm bảo username luôn có giá trị hợp lệ
    username = 'neo4j'  # Giá trị mặc định

    # Thử lấy username từ các nguồn khác nhau
    if current_app and current_app.config.get('NEO4J_USERNAME'):
        username = current_app.config.get('NEO4J_USERNAME')
    elif current_app and current_app.config.get('NEO4J_USER'):
        username = current_app.config.get('NEO4J_USER')
    elif os.environ.get('NEO4J_USERNAME'):
        username = os.environ.get('NEO4J_USERNAME')
    elif os.environ.get('NEO4J_USER'):
        username = os.environ.get('NEO4J_USER')

    log_info(f"Using Neo4j username: {username}")

    # Đảm bảo password luôn có giá trị hợp lệ
    password = '12345678'  # Giá trị mặc định

    # Thử lấy password từ các nguồn khác nhau
    if current_app and current_app.config.get('NEO4J_PASSWORD'):
        password = current_app.config.get('NEO4J_PASSWORD')
    elif os.environ.get('NEO4J_PASSWORD'):
        password = os.environ.get('NEO4J_PASSWORD')

    log_info(f"Neo4j connection parameters: URI={uri}, Username={username}")

    return {
        'uri': uri,
        'username': username,
        'password': password,
        # Không chỉ định database để sử dụng database mặc định
    }

def check_circuit_breaker():
    """Kiểm tra trạng thái circuit breaker"""
    global _circuit_breaker_state, _circuit_breaker_last_failure_time, _circuit_breaker_last_reset_time

    if not _circuit_breaker_enabled:
        return True

    with _circuit_breaker_lock:
        # Kiểm tra xem có cần auto reset không
        current_time = datetime.now()

        # Auto reset sau một khoảng thời gian dài không có lỗi
        if (_circuit_breaker_auto_reset and
            _circuit_breaker_last_reset_time is None and
            _circuit_breaker_state != "CLOSED"):
            _circuit_breaker_last_reset_time = current_time

        if (_circuit_breaker_auto_reset and
            _circuit_breaker_last_reset_time is not None and
            (current_time - _circuit_breaker_last_reset_time).total_seconds() > _circuit_breaker_reset_timeout):
            # Reset circuit breaker sau một khoảng thời gian
            _circuit_breaker_state = "CLOSED"
            _circuit_breaker_failure_count = 0
            _circuit_breaker_last_failure_time = None
            _circuit_breaker_last_reset_time = current_time
            log_info(f"Circuit breaker auto-reset to CLOSED after {_circuit_breaker_reset_timeout} seconds")
            return True

        # Nếu circuit đang đóng, cho phép thực hiện truy vấn
        if _circuit_breaker_state == "CLOSED":
            return True

        # Nếu circuit đang mở, kiểm tra xem đã đến thời gian thử lại chưa
        if _circuit_breaker_state == "OPEN":
            if _circuit_breaker_last_failure_time is None:
                _circuit_breaker_state = "CLOSED"
                return True

            elapsed = (current_time - _circuit_breaker_last_failure_time).total_seconds()
            if elapsed > _circuit_breaker_timeout:
                # Chuyển sang trạng thái half-open để thử lại
                _circuit_breaker_state = "HALF_OPEN"
                log_warning(f"Circuit breaker transitioning to HALF_OPEN after {elapsed:.1f} seconds")
                return True

            # Circuit vẫn đang mở, không cho phép thực hiện truy vấn
            log_warning(f"Circuit breaker is OPEN, will retry after {_circuit_breaker_timeout - elapsed:.1f} more seconds")
            return False

        # Nếu circuit đang ở trạng thái half-open, cho phép thực hiện truy vấn để kiểm tra
        return True

def record_success():
    """Ghi nhận thành công và reset circuit breaker nếu cần"""
    global _circuit_breaker_state, _circuit_breaker_failure_count, _circuit_breaker_last_failure_time, _circuit_breaker_last_reset_time, _circuit_breaker_timeout

    if not _circuit_breaker_enabled:
        return

    with _circuit_breaker_lock:
        # Giảm số lần lỗi liên tiếp khi có thành công
        if _circuit_breaker_failure_count > 0:
            _circuit_breaker_failure_count = max(0, _circuit_breaker_failure_count - 1)

        # Bắt đầu tính thời gian auto reset khi có thành công
        if _circuit_breaker_last_reset_time is None:
            _circuit_breaker_last_reset_time = datetime.now()

        if _circuit_breaker_state == "HALF_OPEN":
            # Nếu thành công trong trạng thái half-open, đóng circuit
            _circuit_breaker_state = "CLOSED"
            _circuit_breaker_failure_count = 0
            _circuit_breaker_last_failure_time = None

            # Reset thời gian timeout về giá trị ban đầu
            _circuit_breaker_timeout = 60

            log_info("Circuit breaker reset to CLOSED after successful operation in HALF_OPEN state")
        elif _circuit_breaker_state == "CLOSED":
            # Reset số lần lỗi
            _circuit_breaker_failure_count = 0

        # Nếu đã quá thời gian reset, reset circuit breaker
        if (_circuit_breaker_last_failure_time is not None and
            (datetime.now() - _circuit_breaker_last_failure_time).total_seconds() > _circuit_breaker_reset_timeout):
            if _circuit_breaker_state != "CLOSED":
                log_info(f"Circuit breaker reset to CLOSED after {_circuit_breaker_reset_timeout}s without failures")
            _circuit_breaker_state = "CLOSED"
            _circuit_breaker_failure_count = 0
            _circuit_breaker_last_failure_time = None

            # Reset thời gian timeout về giá trị ban đầu
            _circuit_breaker_timeout = 60

def record_failure():
    """Ghi nhận lỗi và cập nhật circuit breaker nếu cần"""
    global _circuit_breaker_state, _circuit_breaker_failure_count, _circuit_breaker_last_failure_time, _circuit_breaker_last_reset_time

    if not _circuit_breaker_enabled:
        return

    with _circuit_breaker_lock:
        _circuit_breaker_last_failure_time = datetime.now()
        _circuit_breaker_failure_count += 1

        # Reset thời gian auto reset khi có lỗi mới
        _circuit_breaker_last_reset_time = None

        # Log số lần lỗi liên tiếp
        log_warning(f"Neo4j connection failure count: {_circuit_breaker_failure_count}/{_circuit_breaker_threshold}")

        if _circuit_breaker_state == "HALF_OPEN":
            # Nếu lỗi trong trạng thái half-open, mở lại circuit
            _circuit_breaker_state = "OPEN"
            log_warning("Circuit breaker opened again after failure in HALF_OPEN state")

            # Tăng thời gian timeout khi có lỗi liên tiếp
            global _circuit_breaker_timeout
            _circuit_breaker_timeout = min(_circuit_breaker_timeout * 2, 300)  # Tối đa 5 phút
            log_warning(f"Circuit breaker timeout increased to {_circuit_breaker_timeout} seconds")

            # Xóa cache khi circuit breaker mở
            clear_cache()
            log_warning("Cache cleared due to circuit breaker opening")

        elif _circuit_breaker_state == "CLOSED":
            # Nếu vượt quá ngưỡng, mở circuit
            if _circuit_breaker_failure_count >= _circuit_breaker_threshold:
                _circuit_breaker_state = "OPEN"
                log_warning(f"Circuit breaker opened after {_circuit_breaker_failure_count} consecutive failures")

                # Xóa cache khi circuit breaker mở
                clear_cache()
                log_warning("Cache cleared due to circuit breaker opening")

def health_check():
    """Kiểm tra sức khỏe kết nối Neo4j"""
    global _last_health_check, _driver

    # Chỉ kiểm tra theo định kỳ
    current_time = datetime.now()
    if (_last_health_check is not None and
        (current_time - _last_health_check).total_seconds() < _health_check_interval):
        return True

    _last_health_check = current_time

    try:
        with _driver_lock:
            if _driver is None:
                return False

            # Kiểm tra kết nối bằng cách thực hiện truy vấn đơn giản
            with _driver.session() as session:
                result = session.run("RETURN 1 as n")
                record = result.single()
                if record and record["n"] == 1:
                    log_info("Neo4j health check passed")
                    return True
                else:
                    log_warning("Neo4j health check failed: unexpected result")
                    return False
    except Exception as e:
        log_error(f"Neo4j health check failed: {str(e)}")
        return False

def init_neo4j_connection():
    """Initialize Neo4j connection with advanced connection pooling and warmup"""
    global _driver, _driver_initialized, _initialization_in_progress, _initialization_time

    # Sử dụng lock riêng cho quá trình khởi tạo để tránh nhiều thread cùng khởi tạo
    with _initialization_lock:
        # Nếu đang trong quá trình khởi tạo, chờ một khoảng thời gian
        if _initialization_in_progress:
            log_info("Neo4j connection initialization already in progress, waiting...")
            # Trả về None để caller biết cần thử lại sau
            return None

        # Đánh dấu đang trong quá trình khởi tạo
        _initialization_in_progress = True
        _initialization_time = datetime.now()

    try:
        with _driver_lock:
            if _driver is not None:
                # Kiểm tra sức khỏe kết nối hiện tại
                if health_check():
                    _driver_initialized = True
                    _initialization_in_progress = False
                    return True
                else:
                    # Nếu kết nối không khỏe mạnh, đóng và tạo lại
                    log_warning("Unhealthy Neo4j connection detected, recreating...")
                    try:
                        _driver.close()
                    except Exception as e:
                        log_error(f"Error closing unhealthy Neo4j connection: {str(e)}")
                    _driver = None
                    _driver_initialized = False

            try:
                # Get connection parameters from config
                params = get_neo4j_connection_params()
                uri = params['uri']
                username = params['username']
                password = params['password']

                log_info(f"Creating Neo4j driver with connection pool size: {_max_connection_pool_size}")

                # Create driver instance with optimized connection pooling
                _driver = GraphDatabase.driver(
                    uri,
                    auth=(username, password),
                    max_connection_pool_size=_max_connection_pool_size,
                    connection_acquisition_timeout=_connection_acquisition_timeout,
                    max_transaction_retry_time=_max_transaction_retry_time,
                    connection_timeout=_connection_timeout,
                    max_connection_lifetime=_connection_max_lifetime
                    # Removed connection_liveness_check_timeout as it's not supported
                )

                # Verify connection with timeout
                log_info("Verifying Neo4j connectivity...")
                _driver.verify_connectivity()

                # Warmup connection pool - tạo sẵn một số kết nối để tránh lag khi có nhiều request đồng thời
                log_info(f"Warming up Neo4j connection pool with {_connection_warmup_count} connections...")
                warmup_sessions = []
                for i in range(_connection_warmup_count):
                    try:
                        session = _driver.session()
                        # Thực hiện một truy vấn đơn giản để đảm bảo kết nối hoạt động
                        result = session.run("RETURN 1 as n").single()
                        if result and result["n"] == 1:
                            warmup_sessions.append(session)
                            log_info(f"Warmup connection {i+1}/{_connection_warmup_count} successful")
                        else:
                            log_warning(f"Warmup connection {i+1}/{_connection_warmup_count} returned unexpected result")
                            session.close()
                    except Exception as e:
                        log_error(f"Error warming up connection {i+1}/{_connection_warmup_count}: {str(e)}")

                # Trả các session về pool để tái sử dụng
                for session in warmup_sessions:
                    return_session_to_pool(session)

                log_info(f"Added {len(warmup_sessions)} pre-warmed sessions to the pool")

                # Reset circuit breaker sau khi kết nối thành công
                record_success()

                # Cập nhật thời gian kiểm tra sức khỏe
                global _last_health_check
                _last_health_check = datetime.now()

                # Đánh dấu đã khởi tạo thành công
                _driver_initialized = True

                log_info(f"Connected to Neo4j at {uri} with optimized connection pooling (max pool size: {_max_connection_pool_size})")
                return True
            except Exception as e:
                log_error(f"Failed to connect to Neo4j: {str(e)}")
                _driver = None
                _driver_initialized = False

                # Ghi nhận lỗi cho circuit breaker
                record_failure()

                raise
    finally:
        # Đảm bảo reset trạng thái khởi tạo khi hoàn thành hoặc gặp lỗi
        _initialization_in_progress = False

def get_neo4j_driver():
    """Get the Neo4j driver instance with health check and initialization handling"""
    global _driver, _driver_initialized, _initialization_in_progress, _initialization_time

    # Kiểm tra circuit breaker trước
    if not check_circuit_breaker():
        log_warning("Circuit breaker is OPEN, preventing Neo4j connection")
        return None

    # Nếu đang trong quá trình khởi tạo bởi thread khác, chờ một khoảng thời gian
    if _initialization_in_progress:
        # Kiểm tra xem quá trình khởi tạo có bị treo không
        if _initialization_time is not None:
            elapsed = (datetime.now() - _initialization_time).total_seconds()
            if elapsed > _max_initialization_wait_time:
                log_warning(f"Neo4j initialization has been in progress for {elapsed:.1f}s, may be stuck")
                # Reset trạng thái khởi tạo nếu quá lâu
                with _initialization_lock:
                    if _initialization_in_progress and elapsed > _max_initialization_wait_time:
                        log_warning("Resetting stuck initialization state")
                        _initialization_in_progress = False
            else:
                log_info(f"Waiting for Neo4j initialization to complete (in progress for {elapsed:.1f}s)")
                # Trả về None để caller biết cần thử lại sau
                return None

    # Khởi tạo driver nếu cần
    if _driver is None or not _driver_initialized:
        try:
            # Thử khởi tạo kết nối với timeout
            init_result = init_neo4j_connection()

            # Nếu init_result là None, nghĩa là đang có thread khác đang khởi tạo
            if init_result is None:
                log_info("Another thread is initializing Neo4j connection, will retry later")
                return None

            # Nếu init_result là False, nghĩa là khởi tạo thất bại
            if not init_result:
                log_error("Failed to initialize Neo4j connection")
                return None
        except Exception as e:
            log_error(f"Failed to initialize Neo4j connection: {str(e)}")
            return None

    # Kiểm tra sức khỏe định kỳ - chỉ kiểm tra nếu đã khởi tạo thành công
    if _driver_initialized and not health_check():
        log_warning("Health check failed, reinitializing Neo4j connection")
        try:
            close_neo4j_connection()
            init_result = init_neo4j_connection()

            # Xử lý kết quả khởi tạo lại
            if init_result is None or not init_result:
                log_error("Failed to reinitialize Neo4j connection after health check")
                return None
        except Exception as e:
            log_error(f"Failed to reinitialize Neo4j connection after health check: {str(e)}")
            return None

    return _driver

def close_neo4j_connection():
    """Close Neo4j connection safely with session pool cleanup"""
    global _driver, _session_pool

    # Đóng tất cả các session trong pool
    with _session_pool_lock:
        for session in _session_pool:
            try:
                if session and not session.closed():
                    session.close()
            except Exception as e:
                log_error(f"Error closing session from pool: {str(e)}")
        _session_pool.clear()

    # Đóng driver
    with _driver_lock:
        if _driver is not None:
            try:
                _driver.close()
                log_info("Neo4j connection closed")
            except Exception as e:
                log_error(f"Error closing Neo4j connection: {str(e)}")
            finally:
                _driver = None

def get_session_from_pool():
    """Lấy session từ pool hoặc tạo mới nếu cần"""
    global _session_pool

    with _session_pool_lock:
        if _session_pool:
            return _session_pool.pop()

    # Nếu không có session trong pool, tạo mới
    driver = get_neo4j_driver()
    if driver:
        try:
            return driver.session()
        except Exception as e:
            log_error(f"Error creating new session: {str(e)}")

    return None

def return_session_to_pool(session):
    """Trả session về pool nếu còn sử dụng được"""
    global _session_pool

    if session is None or session.closed():
        return

    with _session_pool_lock:
        # Chỉ giữ lại số lượng session giới hạn trong pool
        if len(_session_pool) < _max_session_pool_size:
            _session_pool.append(session)
        else:
            try:
                session.close()
            except Exception as e:
                log_error(f"Error closing excess session: {str(e)}")

def add_jitter(delay):
    """Thêm jitter vào thời gian chờ để tránh thundering herd"""
    return delay * (0.5 + random.random())

def generate_cache_key(query, params=None):
    """Tạo cache key từ query và params"""
    if not _cache_enabled:
        return None

    # Chuẩn hóa params để tạo key nhất quán
    normalized_params = json.dumps(params or {}, sort_keys=True)
    # Tạo key bằng cách hash query và params
    key = hashlib.md5((query + normalized_params).encode()).hexdigest()
    return key

# Thêm biến để theo dõi cache hits/misses
_cache_hits = 0
_cache_misses = 0
_cache_stats_lock = threading.Lock()

def get_from_cache(key):
    """Lấy dữ liệu từ cache nếu còn hiệu lực"""
    global _cache_hits, _cache_misses

    if not _cache_enabled or key is None:
        with _cache_stats_lock:
            _cache_misses += 1
        return None

    with _cache_lock:
        if key not in _cache:
            with _cache_stats_lock:
                _cache_misses += 1
            return None

        timestamp, data = _cache[key]
        # Kiểm tra xem cache có còn hiệu lực không
        if (datetime.now() - timestamp).total_seconds() > _cache_ttl:
            # Cache đã hết hạn, xóa khỏi cache
            del _cache[key]
            with _cache_stats_lock:
                _cache_misses += 1
            return None

        # Cache hit
        with _cache_stats_lock:
            _cache_hits += 1
        return data

def store_in_cache(key, data):
    """Lưu dữ liệu vào cache"""
    if not _cache_enabled or key is None:
        return

    with _cache_lock:
        # Nếu cache đã đầy, xóa mục cũ nhất
        if len(_cache) >= _cache_size_limit:
            oldest_key = min(_cache.keys(), key=lambda k: _cache[k][0])
            del _cache[oldest_key]

        # Lưu dữ liệu mới vào cache
        _cache[key] = (datetime.now(), data)

def clear_cache():
    """Xóa toàn bộ cache"""
    with _cache_lock:
        _cache.clear()

def execute_query_with_semaphore(query, params=None, database=None, max_retries=3, retry_delay=1, use_cache=True, semaphore_timeout=None):
    """Execute a Cypher query with semaphore to limit concurrent queries"""
    # Sử dụng timeout mặc định nếu không được chỉ định
    if semaphore_timeout is None:
        semaphore_timeout = _query_timeout

    # Kiểm tra cache trước - ưu tiên cache để giảm tải cho database
    if use_cache:
        cache_key = generate_cache_key(query, params)
        cached_result = get_from_cache(cache_key)
        if cached_result is not None:
            global _cache_hit_count
            with _cache_stats_lock:
                _cache_hit_count += 1
            log_info(f"Cache hit for query: {query[:50]}...")
            return cached_result

    # Sử dụng semaphore để giới hạn số lượng truy vấn đồng thời
    acquired = False
    start_time = time.time()

    # Thêm jitter vào thời gian chờ để tránh thundering herd
    actual_timeout = semaphore_timeout * (0.8 + 0.4 * random.random())

    try:
        # Thử acquire semaphore với timeout
        log_info(f"Waiting for query semaphore (timeout: {actual_timeout:.1f}s)...")
        acquired = _query_semaphore.acquire(timeout=actual_timeout)

        if not acquired:
            log_warning(f"Failed to acquire query semaphore after {actual_timeout:.1f}s, too many concurrent queries")

            # Nếu không lấy được semaphore nhưng có kết quả trong cache, trả về kết quả cũ
            # Mở rộng thời gian cache TTL trong trường hợp quá tải
            if use_cache and cache_key in _cache:
                with _cache_lock:
                    if cache_key in _cache:
                        timestamp, data = _cache[cache_key]
                        cache_age = (datetime.now() - timestamp).total_seconds()
                        # Cho phép sử dụng cache cũ hơn trong trường hợp quá tải
                        extended_ttl = _cache_ttl * 2
                        if cache_age <= extended_ttl:
                            log_warning(f"Returning stale cache data due to semaphore timeout (age: {cache_age:.1f}s)")
                            return data
                        else:
                            log_warning(f"Cache data too old ({cache_age:.1f}s > {extended_ttl}s), cannot use")

            # Trả về kết quả rỗng nếu không có cache hoặc cache quá cũ
            return []

        wait_time = time.time() - start_time
        if wait_time > 1.0:  # Chỉ log nếu phải chờ đợi đáng kể
            log_info(f"Acquired query semaphore after waiting {wait_time:.2f}s")

        # Thực hiện truy vấn với số lần retry tăng dần nếu chờ lâu
        # Nếu đã chờ lâu để có semaphore, tăng số lần retry để đảm bảo thành công
        adjusted_max_retries = max_retries
        if wait_time > 5.0:
            adjusted_max_retries = max(max_retries, 5)
            log_info(f"Increasing max retries to {adjusted_max_retries} due to long semaphore wait time")

        # Thực hiện truy vấn
        result = _execute_query_internal(query, params, database, adjusted_max_retries, retry_delay)

        # Lưu kết quả vào cache
        if use_cache:
            if result:
                store_in_cache(cache_key, result)
            global _cache_miss_count
            with _cache_stats_lock:
                _cache_miss_count += 1

        return result
    except Exception as e:
        log_error(f"Error in execute_query_with_semaphore: {str(e)}")
        return []
    finally:
        # Đảm bảo release semaphore nếu đã acquire
        if acquired:
            _query_semaphore.release()
            log_info(f"Released query semaphore after {time.time() - start_time:.2f}s")

def _execute_query_internal(query, params=None, database=None, max_retries=3, retry_delay=1):
    """Execute a Cypher query with advanced retry mechanism and circuit breaker (internal implementation)"""
    # Kiểm tra circuit breaker
    if not check_circuit_breaker():
        log_warning("Circuit breaker is OPEN, skipping query execution")
        return []

    session = None
    last_error = None

    # Danh sách lỗi kết nối cần xử lý đặc biệt
    connection_errors = [
        "defunct connection",
        "connection reset",
        "connection refused",
        "connection timed out",
        "connection has been closed",
        "socket closed",
        "failed to read",
        "broken pipe",
        "existing exports of data",
        "address already in use",
        "too many open files",
        "database unavailable",
        "service unavailable",
        "timeout during discovery",
        "connection acquisition timed out"
    ]

    # Sử dụng backoff strategy thông minh hơn
    for attempt in range(max_retries):
        try:
            # Lấy driver và kiểm tra
            driver = get_neo4j_driver()
            if driver is None:
                log_error("No Neo4j connection available")
                record_failure()
                last_error = Exception("No Neo4j connection available")

                # Chờ trước khi thử lại với backoff strategy
                if attempt < max_retries - 1:
                    # Sử dụng exponential backoff với jitter
                    wait_time = add_jitter(retry_delay * (2 ** attempt))
                    log_info(f"Retrying to get driver in {wait_time:.2f} seconds... (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                continue

            # Lấy session từ pool hoặc tạo mới
            session = get_session_from_pool()
            if session is None:
                log_error("Failed to get Neo4j session")
                record_failure()
                last_error = Exception("Failed to get Neo4j session")

                # Chờ trước khi thử lại
                if attempt < max_retries - 1:
                    wait_time = add_jitter(retry_delay * (2 ** attempt))
                    log_info(f"Retrying to get session in {wait_time:.2f} seconds... (attempt {attempt+1}/{max_retries})")
                    time.sleep(wait_time)
                continue

            # Thực hiện truy vấn với timeout và xử lý lỗi tốt hơn
            try:
                if database:
                    # Nếu có chỉ định database, sử dụng database đó
                    log_info(f"Using specified database: {database}")
                    result = session.run(f"USE {database}; {query}", params or {})
                else:
                    result = session.run(query, params or {})

                # Tiêu thụ kết quả ngay lập tức để tránh lỗi defunct connection
                # Sử dụng timeout để tránh treo khi tiêu thụ kết quả
                records = []
                start_consume = time.time()
                for record in result:
                    # Kiểm tra timeout khi tiêu thụ kết quả
                    if time.time() - start_consume > _connection_timeout:
                        log_warning(f"Timeout while consuming query results after {_connection_timeout}s")
                        raise Exception(f"Timeout while consuming query results after {_connection_timeout}s")
                    records.append(record.data())

                # Ghi nhận thành công cho circuit breaker
                record_success()

                # Trả session về pool để tái sử dụng
                return_session_to_pool(session)
                session = None

                return records
            except Exception as e:
                # Xử lý lỗi khi thực hiện truy vấn
                error_message = str(e)
                log_error(f"Error executing Neo4j query (attempt {attempt+1}/{max_retries}): {error_message}")
                last_error = e

                # Đóng session lỗi thay vì trả về pool
                if session is not None:
                    try:
                        session.close()
                    except:
                        pass
                    session = None

                # Ghi nhận lỗi cho circuit breaker
                record_failure()

                # Nếu lỗi liên quan đến kết nối, thử khởi tạo lại driver
                if any(err in error_message.lower() for err in connection_errors):
                    log_warning(f"Connection issue detected, reinitializing driver...")
                    close_neo4j_connection()

                raise  # Re-raise để xử lý ở ngoài

        except Exception as e:
            error_message = str(e)
            log_error(f"Error in execute_query (attempt {attempt+1}/{max_retries}): {error_message}")
            last_error = e

            # Ghi nhận lỗi cho circuit breaker
            record_failure()

            if attempt < max_retries - 1:
                # Chờ trước khi thử lại với jitter để tránh thundering herd
                # Sử dụng exponential backoff với jitter
                wait_time = add_jitter(retry_delay * (2 ** attempt))

                # Tăng thời gian chờ nếu lỗi liên quan đến kết nối
                if any(err in error_message.lower() for err in connection_errors):
                    wait_time = min(wait_time * 2, 30)  # Tối đa 30 giây
                    log_warning(f"Connection issue detected, increasing wait time to {wait_time:.2f}s")

                log_info(f"Retrying in {wait_time:.2f} seconds... (attempt {attempt+1}/{max_retries})")
                time.sleep(wait_time)
            else:
                log_error(f"Query failed after {max_retries} attempts: {query}")
                if params:
                    log_error(f"Params: {params}")
                if last_error:
                    log_error(f"Last error: {str(last_error)}")
                return []

    # Đảm bảo session được đóng nếu vẫn còn mở
    if session is not None:
        try:
            session.close()
        except:
            pass

    return []

def execute_query(query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """
    Execute a Cypher query and return the results

    Args:
        query: Cypher query to execute
        params: Parameters for the query

    Returns:
        List[Dict]: Query results
    """
    try:
        # Use semaphore and caching
        result = execute_query_with_semaphore(query, params, use_cache=True)
        return result
    except Exception as e:
        log_error(f"Error executing query: {str(e)}")
        return []

def get_product_by_id(product_id: str) -> Optional[Dict]:
    """Lấy thông tin sản phẩm theo ID"""
    query = """
    MATCH (p:product)
    WHERE p.id = $product_id OR p.Id = $product_id
    RETURN p {.*} as product
    LIMIT 1
    """

    try:
        # Sử dụng cơ chế semaphore và caching
        result = execute_query_with_semaphore(query, {'product_id': product_id}, use_cache=True)
        return result[0]['product'] if result else None
    except Exception as e:
        log_error(f"Error getting product by id: {str(e)}")
        return None

def get_metrics():
    """Lấy metrics của Neo4j"""
    try:
        # Thực hiện truy vấn để lấy metrics - không sử dụng cache vì metrics cần luôn mới nhất
        query = """
        CALL dbms.listQueries() YIELD query, elapsedTimeMillis
        RETURN
            count(*) as activeQueries,
            avg(elapsedTimeMillis) as avgQueryTime,
            max(elapsedTimeMillis) as maxQueryTime
        """

        result = execute_query_with_semaphore(query, max_retries=2, use_cache=False)

        if result and len(result) > 0:
            metrics = result[0]
        else:
            metrics = {
                'activeQueries': 0,
                'avgQueryTime': 0,
                'maxQueryTime': 0
            }

        # Thêm thông tin về database size
        size_query = """
        CALL dbms.database.size() YIELD totalSize, totalTransactionLogSize
        RETURN totalSize, totalTransactionLogSize
        """

        size_result = execute_query_with_semaphore(size_query, max_retries=2, use_cache=False)

        if size_result and len(size_result) > 0:
            metrics.update(size_result[0])

        # Thêm thông tin về cache
        with _cache_lock:
            metrics['cacheSize'] = len(_cache)
            metrics['cacheEnabled'] = _cache_enabled
            metrics['cacheTTL'] = _cache_ttl

        # Thêm thông tin về circuit breaker
        with _circuit_breaker_lock:
            metrics['circuitBreakerState'] = _circuit_breaker_state
            metrics['circuitBreakerFailureCount'] = _circuit_breaker_failure_count

        # Thêm thông tin về semaphore
        metrics['maxConcurrentQueries'] = _max_concurrent_queries
        metrics['availableQuerySlots'] = _query_semaphore._value

        return metrics

    except Exception as e:
        log_error(f"Error getting Neo4j metrics: {str(e)}")
        return {
            'error': str(e),
            'activeQueries': 0,
            'avgQueryTime': 0,
            'maxQueryTime': 0
        }

def cache_stats():
    """Lấy thống kê về cache"""
    with _cache_lock:
        stats = {
            'cacheSize': len(_cache),
            'cacheEnabled': _cache_enabled,
            'cacheTTL': _cache_ttl,
            'cacheSizeLimit': _cache_size_limit
        }

    # Lấy số lượng cache hit/miss
    with _cache_stats_lock:
        stats['cacheHits'] = _cache_hits
        stats['cacheMisses'] = _cache_misses
        total = _cache_hits + _cache_misses
        stats['cacheHitRatio'] = _cache_hits / total if total > 0 else 0
        stats['cacheHitRatioPercent'] = f"{stats['cacheHitRatio'] * 100:.2f}%"

    return stats
