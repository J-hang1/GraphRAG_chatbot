"""Scheduler utilities for managing scheduled tasks"""
# Phần còn lại của file được chuyển từ app\services\scheduler_service.py
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from flask import current_app
from .backup import backup_service
from .monitoring import monitoring_service, HealthStatus
from .logger import log_info, log_error

class SchedulerService:
    """Service quản lý các scheduled tasks"""

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.setup_jobs()

    def setup_jobs(self):
        """Setup các scheduled jobs"""
        # Backup database hàng ngày lúc 2 giờ sáng
        self.scheduler.add_job(
            func=self._scheduled_backup,
            trigger=CronTrigger(hour=2),
            id='daily_backup',
            name='Daily Database Backup'
        )

        # Cleanup old backups hàng tuần vào Chủ nhật lúc 3 giờ sáng
        self.scheduler.add_job(
            func=self._scheduled_cleanup,
            trigger=CronTrigger(day_of_week=6, hour=3),
            id='weekly_cleanup',
            name='Weekly Backup Cleanup'
        )

        # Health check mỗi 5 phút
        self.scheduler.add_job(
            func=self._scheduled_health_check,
            trigger='interval',
            minutes=5,
            id='health_check',
            name='System Health Check'
        )

    def start(self):
        """Start scheduler"""
        try:
            self.scheduler.start()
            log_info("Scheduler started successfully")
        except Exception as e:
            log_error(f"Failed to start scheduler: {str(e)}")

    def shutdown(self):
        """Shutdown scheduler"""
        try:
            # Kiểm tra xem scheduler đã được khởi động chưa
            if hasattr(self.scheduler, 'state') and self.scheduler.state != 0:  # STATE_STOPPED = 0
                self.scheduler.shutdown()
                log_info("Scheduler shutdown successfully")
            else:
                log_info("Scheduler is not running, no need to shutdown")
        except Exception as e:
            log_error(f"Failed to shutdown scheduler: {str(e)}")

    def _scheduled_backup(self):
        """Thực hiện scheduled database backup"""
        try:
            log_info("Starting scheduled database backup")

            # Backup Neo4j database
            neo4j_success = backup_service.backup_neo4j()

            if neo4j_success:
                log_info("Scheduled backup completed successfully")
            else:
                log_error("Neo4j backup failed during scheduled backup")

        except Exception as e:
            log_error(f"Error during scheduled backup: {str(e)}")

    def _scheduled_cleanup(self):
        """Thực hiện scheduled cleanup"""
        try:
            log_info("Starting scheduled backup cleanup")
            days_to_keep = current_app.config.get('BACKUP_RETENTION_DAYS', 7)

            if backup_service.cleanup_old_backups(days_to_keep):
                log_info("Scheduled cleanup completed successfully")
            else:
                log_error("Scheduled cleanup failed")

        except Exception as e:
            log_error(f"Error during scheduled cleanup: {str(e)}")

    def _scheduled_health_check(self):
        """Thực hiện scheduled health check"""
        try:
            log_info("Starting scheduled health check")
            health = monitoring_service.get_system_health()

            if health['status'] != HealthStatus.OK:
                log_error(f"System health check failed: {health['status']}", {
                    'components': health['components']
                })
            else:
                log_info("System health check passed")

        except Exception as e:
            log_error(f"Error during health check: {str(e)}")

    def get_jobs(self):
        """Get danh sách các scheduled jobs"""
        return [{
            'id': job.id,
            'name': job.name,
            'next_run': job.next_run_time.isoformat() if job.next_run_time else None,
            'trigger': str(job.trigger)
        } for job in self.scheduler.get_jobs()]

    def modify_job(self, job_id, **changes):
        """Modify một scheduled job"""
        try:
            job = self.scheduler.get_job(job_id)
            if job:
                job.modify(**changes)
                log_info(f"Modified job {job_id} successfully")
                return True
            return False
        except Exception as e:
            log_error(f"Error modifying job {job_id}: {str(e)}")
            return False

# Singleton instance
scheduler_service = SchedulerService()
