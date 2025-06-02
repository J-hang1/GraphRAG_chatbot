"""Monitoring utilities for tracking system performance and health"""
# Phần còn lại của file được chuyển từ app\services\monitoring_service.py
import time
from collections import defaultdict
from threading import Lock
from typing import Dict, Any, List

from .logger import log_error, log_info

class HealthStatus:
    """Định nghĩa các trạng thái health check"""
    OK = "ok"
    WARNING = "warning"
    ERROR = "error"

class ComponentStatus:
    """Đối tượng theo dõi trạng thái của một component"""
    def __init__(self, name: str):
        self.name = name
        self.status = HealthStatus.OK
        self.last_check = time.time()
        self.error_count = 0
        self.last_error = None
        self.metrics = {}

    def update(self, status: str, error: Exception = None, metrics: Dict = None):
        """Cập nhật trạng thái component"""
        self.status = status
        self.last_check = time.time()

        if error:
            self.error_count += 1
            self.last_error = str(error)

        if metrics:
            self.metrics.update(metrics)

    def to_dict(self) -> Dict:
        """Chuyển đổi trạng thái thành dictionary"""
        return {
            'name': self.name,
            'status': self.status,
            'last_check': self.last_check,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'metrics': self.metrics
        }

class MonitoringService:
    """Service theo dõi hiệu năng của GraphRAG Agent"""

    def __init__(self):
        # Existing metrics
        self.metrics = {
            'query_times': [],
            'neo4j_times': [],
            'llm_times': [],
            'cache_hits': 0,
            'cache_misses': 0,
            'errors': []
        }
        self.error_groups = defaultdict(list)
        self._lock = Lock()

        # Component health tracking
        self.components = {
            'neo4j': ComponentStatus('neo4j'),
            'llm': ComponentStatus('llm'),
            'cache': ComponentStatus('cache'),
            'database': ComponentStatus('database')
        }

        # Monitoring service metrics
        self._metrics = {
            'neo4j': {
                'total_queries': 0,
                'failed_queries': 0,
                'total_time': 0,
                'avg_time': 0
            },
            'llm': {
                'total_calls': 0,
                'failed_calls': 0,
                'total_tokens': 0,
                'total_time': 0,
                'avg_time': 0
            },
            'cache': {
                'hits': 0,
                'misses': 0,
                'hit_rate': 0,
                'size': 0,
                'evictions': 0
            },
            'errors': []
        }
        self._start_time = time.time()

    def update_component_health(self,
                              component: str,
                              status: str = HealthStatus.OK,
                              error: Exception = None,
                              metrics: Dict = None):
        """Cập nhật trạng thái health của một component"""
        with self._lock:
            if component in self.components:
                self.components[component].update(status, error, metrics)

                # Log significant status changes
                if status != HealthStatus.OK:
                    log_error(f"Component {component} health changed to {status}", {
                        'error': str(error) if error else None,
                        'metrics': metrics
                    })
                else:
                    log_info(f"Component {component} health is OK")

    def get_system_health(self) -> Dict[str, Any]:
        """Get tổng quan về health của hệ thống"""
        with self._lock:
            component_status = {
                name: component.to_dict()
                for name, component in self.components.items()
            }

            # Determine overall system status
            status = HealthStatus.OK
            if any(c.status == HealthStatus.ERROR for c in self.components.values()):
                status = HealthStatus.ERROR
            elif any(c.status == HealthStatus.WARNING for c in self.components.values()):
                status = HealthStatus.WARNING

            return {
                'status': status,
                'components': component_status,
                'timestamp': time.time(),
                'errors': self.get_recent_errors(5)
            }

    def check_component_health(self, component: str) -> bool:
        """Kiểm tra health của một component cụ thể"""
        with self._lock:
            if component not in self.components:
                return False

            component_status = self.components[component]

            # Xác định health dựa trên các metrics
            if component == 'cache':
                hit_rate = self._calculate_cache_hit_rate()
                if hit_rate < 0.5:  # Less than 50% hit rate
                    component_status.update(
                        HealthStatus.WARNING,
                        metrics={'hit_rate': hit_rate}
                    )
                else:
                    component_status.update(
                        HealthStatus.OK,
                        metrics={'hit_rate': hit_rate}
                    )

            elif component == 'neo4j':
                # Check Neo4j response times
                neo4j_times = self.metrics['neo4j_times']
                if neo4j_times:
                    avg_time = sum(t['duration'] for t in neo4j_times) / len(neo4j_times)
                    if avg_time > 1.0:  # More than 1 second average
                        component_status.update(
                            HealthStatus.WARNING,
                            metrics={'avg_response_time': avg_time}
                        )
                    else:
                        component_status.update(
                            HealthStatus.OK,
                            metrics={'avg_response_time': avg_time}
                        )

            return component_status.status == HealthStatus.OK

    def get_recent_errors(self, limit=10, error_type=None):
        """Lấy danh sách các lỗi gần đây"""
        with self._lock:
            if error_type:
                errors = self.error_groups.get(error_type, [])[:limit]
            else:
                errors = self.metrics['errors'][:limit]
            return errors

    def get_error_summary(self):
        """Lấy tóm tắt các lỗi theo loại"""
        with self._lock:
            return {
                error_type: len(errors)
                for error_type, errors in self.error_groups.items()
            }

    def get_performance_metrics(self):
        """Lấy metrics hiệu năng"""
        with self._lock:
            return {
                'uptime': time.time() - self._start_time,
                'neo4j': self._metrics['neo4j'],
                'llm': self._metrics['llm'],
                'cache': self._metrics['cache']
            }

    def clear_metrics(self):
        """Xóa tất cả metrics"""
        with self._lock:
            self.metrics = {
                'query_times': [],
                'neo4j_times': [],
                'llm_times': [],
                'cache_hits': 0,
                'cache_misses': 0,
                'errors': []
            }
            self.error_groups = defaultdict(list)
            self._start_time = time.time()

    def _calculate_cache_hit_rate(self):
        """Tính tỷ lệ cache hit"""
        hits = self.metrics['cache_hits']
        misses = self.metrics['cache_misses']
        total = hits + misses

        if total == 0:
            return 0

        return hits / total

# Singleton instance
monitoring_service = MonitoringService()
