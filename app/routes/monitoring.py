from flask import Blueprint, request
from flask_login import login_required
from ..utils.monitoring import monitoring_service, HealthStatus
from ..neo4j_client.connection import get_metrics as neo4j_get_metrics
from ..utils.backup import backup_service
from ..utils.scheduler import scheduler_service
from ..utils.logger import log_error, log_info
from ..utils.response_formatter import formatter
from ..utils.middleware import log_request
import time

# Create blueprint
monitoring = Blueprint('monitoring', __name__)

@monitoring.route('/metrics', methods=['GET'])
@login_required
@log_request
def get_metrics():
    """API endpoint để lấy metrics hiệu năng"""
    try:
        # Lấy metrics từ các service
        performance_metrics = monitoring_service.get_performance_metrics()
        neo4j_metrics = neo4j_get_metrics()
        error_summary = monitoring_service.get_error_summary()

        response = {
            'performance': performance_metrics,
            'neo4j': neo4j_metrics,
            'errors': error_summary,
            'cache': {
                'hits': monitoring_service.metrics['cache_hits'],
                'misses': monitoring_service.metrics['cache_misses'],
                'hit_rate': monitoring_service._calculate_cache_hit_rate()
            }
        }

        return formatter.success(data=response)

    except Exception as e:
        log_error(f"Lỗi khi lấy metrics: {str(e)}")
        return formatter.error(
            message='Lỗi khi lấy metrics',
            status_code=500,
            error_code='METRICS_ERROR'
        )

@monitoring.route('/metrics/errors', methods=['GET'])
@login_required
@log_request
def get_error_metrics():
    """API endpoint để lấy error metrics"""
    try:
        error_type = request.args.get('type')
        limit = int(request.args.get('limit', 10))

        errors = monitoring_service.get_recent_errors(
            limit=limit,
            error_type=error_type
        )

        error_summary = monitoring_service.get_error_summary()

        response = {
            'recent_errors': errors,
            'summary': error_summary
        }

        return formatter.success(data=response)

    except Exception as e:
        log_error(f"Lỗi khi lấy error metrics: {str(e)}")
        return formatter.error(
            message='Lỗi khi lấy error metrics',
            status_code=500,
            error_code='ERROR_METRICS_ERROR'
        )

@monitoring.route('/metrics/neo4j', methods=['GET'])
@login_required
@log_request
def get_neo4j_metrics():
    """API endpoint để lấy Neo4j metrics"""
    try:
        metrics = neo4j_get_metrics()
        return formatter.success(data=metrics)

    except Exception as e:
        log_error(f"Lỗi khi lấy Neo4j metrics: {str(e)}")
        return formatter.error(
            message='Lỗi khi lấy Neo4j metrics',
            status_code=500,
            error_code='NEO4J_METRICS_ERROR'
        )

@monitoring.route('/metrics/performance', methods=['GET'])
@login_required
@log_request
def get_performance_metrics():
    """API endpoint để lấy performance metrics"""
    try:
        metrics = monitoring_service.get_performance_metrics()
        return formatter.success(data=metrics)

    except Exception as e:
        log_error(f"Lỗi khi lấy performance metrics: {str(e)}")
        return formatter.error(
            message='Lỗi khi lấy performance metrics',
            status_code=500,
            error_code='PERFORMANCE_METRICS_ERROR'
        )

@monitoring.route('/metrics/clear', methods=['POST'])
@login_required
@log_request
def clear_metrics():
    """API endpoint để reset metrics"""
    try:
        monitoring_service.clear_metrics()
        return formatter.success(message='Đã xóa metrics thành công')

    except Exception as e:
        log_error(f"Lỗi khi xóa metrics: {str(e)}")
        return formatter.error(
            message='Lỗi khi xóa metrics',
            status_code=500,
            error_code='CLEAR_METRICS_ERROR'
        )

@monitoring.route('/health', methods=['GET'])
@log_request
def health_check():
    """Health check endpoint để giám sát hệ thống"""
    try:
        # Get system health status
        health = monitoring_service.get_system_health()

        # Determine HTTP status code
        status_code = 200
        if health['status'] == HealthStatus.ERROR:
            status_code = 500
        elif health['status'] == HealthStatus.WARNING:
            status_code = 429

        return formatter.success(
            data=health,
            status_code=status_code
        )

    except Exception as e:
        log_error(f"Lỗi khi kiểm tra health: {str(e)}")
        return formatter.error(
            message='Lỗi khi kiểm tra health',
            status_code=500,
            error_code='HEALTH_CHECK_ERROR'
        )

@monitoring.route('/health/<component>', methods=['GET'])
@log_request
def component_health(component):
    """Health check cho một component cụ thể"""
    try:
        # Check component health
        is_healthy = monitoring_service.check_component_health(component)

        if is_healthy:
            return formatter.success(data={
                'status': HealthStatus.OK,
                'component': component
            })
        else:
            status = monitoring_service.components[component].status
            return formatter.error(
                message=f'Component {component} không healthy',
                status_code=500 if status == HealthStatus.ERROR else 429,
                error_code='COMPONENT_UNHEALTHY',
                details={
                    'component': component,
                    'status': status,
                    'metrics': monitoring_service.components[component].metrics
                }
            )

    except KeyError:
        return formatter.error(
            message=f'Component {component} không tồn tại',
            status_code=404,
            error_code='COMPONENT_NOT_FOUND'
        )
    except Exception as e:
        log_error(f"Lỗi khi kiểm tra component health: {str(e)}")
        return formatter.error(
            message='Lỗi khi kiểm tra component health',
            status_code=500,
            error_code='COMPONENT_HEALTH_ERROR'
        )

@monitoring.route('/backup/database', methods=['POST'])
@login_required
@log_request
def backup_database():
    """API endpoint để trigger database backup"""
    try:
        db_type = request.args.get('type', 'all')
        success = False

        if db_type == 'all' or db_type == 'postgres':
            postgres_success = backup_service.backup_postgres()
            success = success or postgres_success

        if db_type == 'all' or db_type == 'neo4j':
            neo4j_success = backup_service.backup_neo4j()
            success = success or neo4j_success

        if success:
            return formatter.success(message='Database backup completed successfully')
        else:
            return formatter.error(
                message='Database backup failed',
                status_code=500,
                error_code='BACKUP_ERROR'
            )

    except Exception as e:
        log_error(f"Lỗi khi backup database: {str(e)}")
        return formatter.error(
            message='Lỗi khi thực hiện backup',
            status_code=500,
            error_code='BACKUP_ERROR',
            details={'error': str(e)}
        )

@monitoring.route('/backup/cleanup', methods=['POST'])
@login_required
@log_request
def cleanup_backups():
    """API endpoint để cleanup old backups"""
    try:
        days = int(request.args.get('days', 7))
        if backup_service.cleanup_old_backups(days):
            return formatter.success(
                message=f'Đã xóa các backup cũ hơn {days} ngày'
            )
        else:
            return formatter.error(
                message='Lỗi khi xóa backup cũ',
                status_code=500,
                error_code='CLEANUP_ERROR'
            )

    except ValueError:
        return formatter.validation_error({
            'days': 'Số ngày phải là một số nguyên'
        })
    except Exception as e:
        log_error(f"Lỗi khi cleanup backups: {str(e)}")
        return formatter.error(
            message='Lỗi khi xóa backup cũ',
            status_code=500,
            error_code='CLEANUP_ERROR',
            details={'error': str(e)}
        )

@monitoring.route('/jobs', methods=['GET'])
@login_required
@log_request
def get_scheduled_jobs():
    """API endpoint để lấy danh sách scheduled jobs"""
    try:
        jobs = scheduler_service.get_jobs()
        return formatter.success(data={'jobs': jobs})
    except Exception as e:
        log_error(f"Lỗi khi lấy danh sách jobs: {str(e)}")
        return formatter.error(
            message='Lỗi khi lấy danh sách jobs',
            status_code=500,
            error_code='JOB_LIST_ERROR'
        )

@monitoring.route('/jobs/<job_id>', methods=['PUT'])
@login_required
@log_request
def modify_job(job_id):
    """API endpoint để modify một scheduled job"""
    try:
        data = request.get_json()
        if not data:
            return formatter.validation_error({
                'message': 'Missing request body'
            })

        success = scheduler_service.modify_job(job_id, **data)

        if success:
            return formatter.success(
                message=f'Job {job_id} đã được cập nhật thành công'
            )
        else:
            return formatter.error(
                message=f'Không tìm thấy job {job_id}',
                status_code=404,
                error_code='JOB_NOT_FOUND'
            )

    except Exception as e:
        log_error(f"Lỗi khi cập nhật job: {str(e)}")
        return formatter.error(
            message='Lỗi khi cập nhật job',
            status_code=500,
            error_code='JOB_UPDATE_ERROR',
            details={'error': str(e)}
        )

@monitoring.route('/phobert/status', methods=['GET'])
@log_request
def phobert_status():
    """API endpoint để kiểm tra trạng thái PhoBERT"""
    try:
        # Import PhoBERT manager
        from ..models.phobert_manager import get_phobert_manager
        phobert_manager = get_phobert_manager()

        # Lấy thông tin trạng thái
        status = {
            'is_loaded': phobert_manager.is_loaded,
            'is_loading': phobert_manager.is_loading,
            'device': str(phobert_manager.device) if hasattr(phobert_manager, '_device') and phobert_manager._device is not None else None,
            'load_error': str(phobert_manager.load_error) if phobert_manager.load_error else None,
            'cache_stats': phobert_manager.get_cache_stats() if phobert_manager.is_loaded else None,
            'timestamp': time.time()
        }

        # Thêm thông tin về thời gian tải và sử dụng nếu có
        if hasattr(phobert_manager, '_init_time') and phobert_manager._init_time:
            status['init_time'] = phobert_manager._init_time
            status['load_duration'] = phobert_manager._init_time - getattr(phobert_manager, '_loading_start_time', phobert_manager._init_time)

        if hasattr(phobert_manager, '_last_used_time') and phobert_manager._last_used_time:
            status['last_used_time'] = phobert_manager._last_used_time
            status['idle_time'] = time.time() - phobert_manager._last_used_time

        if hasattr(phobert_manager, '_usage_count'):
            status['usage_count'] = phobert_manager._usage_count

        log_info(f"PhoBERT status: {status}")
        return formatter.success(data=status)

    except Exception as e:
        log_error(f"Lỗi khi kiểm tra trạng thái PhoBERT: {str(e)}")
        return formatter.error(
            message='Lỗi khi kiểm tra trạng thái PhoBERT',
            status_code=500,
            error_code='PHOBERT_STATUS_ERROR',
            details={'error': str(e)}
        )

@monitoring.route('/phobert/reload', methods=['POST'])
@login_required
@log_request
def reload_phobert():
    """API endpoint để tải lại PhoBERT"""
    try:
        # Import PhoBERT manager
        from ..models.phobert_manager import get_phobert_manager
        phobert_manager = get_phobert_manager()

        # Kiểm tra xem PhoBERT đang được tải không
        if phobert_manager.is_loading:
            return formatter.error(
                message='PhoBERT đang được tải, vui lòng thử lại sau',
                status_code=409,
                error_code='PHOBERT_LOADING'
            )

        # Giải phóng bộ nhớ nếu đã tải
        if phobert_manager.is_loaded:
            # Giải phóng bộ nhớ
            phobert_manager._model = None
            phobert_manager._tokenizer = None
            phobert_manager.clear_cache()
            log_info("Đã giải phóng bộ nhớ PhoBERT")

        # Tải lại PhoBERT
        phobert_manager.load_model_async()
        log_info("Đã bắt đầu tải lại PhoBERT")

        return formatter.success(
            message='Đã bắt đầu tải lại PhoBERT',
            data={'is_loading': True}
        )

    except Exception as e:
        log_error(f"Lỗi khi tải lại PhoBERT: {str(e)}")
        return formatter.error(
            message='Lỗi khi tải lại PhoBERT',
            status_code=500,
            error_code='PHOBERT_RELOAD_ERROR',
            details={'error': str(e)}
        )

@monitoring.route('/phobert/cache/clear', methods=['POST'])
@login_required
@log_request
def clear_phobert_cache():
    """API endpoint để xóa cache PhoBERT"""
    try:
        # Import PhoBERT manager
        from ..models.phobert_manager import get_phobert_manager
        phobert_manager = get_phobert_manager()

        # Kiểm tra xem PhoBERT đã được tải chưa
        if not phobert_manager.is_loaded:
            return formatter.error(
                message='PhoBERT chưa được tải',
                status_code=400,
                error_code='PHOBERT_NOT_LOADED'
            )

        # Lấy thông tin cache trước khi xóa
        cache_stats_before = phobert_manager.get_cache_stats()

        # Xóa cache
        phobert_manager.clear_cache()
        log_info("Đã xóa cache PhoBERT")

        # Lấy thông tin cache sau khi xóa
        cache_stats_after = phobert_manager.get_cache_stats()

        return formatter.success(
            message='Đã xóa cache PhoBERT',
            data={
                'before': cache_stats_before,
                'after': cache_stats_after
            }
        )

    except Exception as e:
        log_error(f"Lỗi khi xóa cache PhoBERT: {str(e)}")
        return formatter.error(
            message='Lỗi khi xóa cache PhoBERT',
            status_code=500,
            error_code='PHOBERT_CACHE_CLEAR_ERROR',
            details={'error': str(e)}
        )