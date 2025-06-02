"""Backup utilities for Neo4j database"""
# Phần còn lại của file được chuyển từ app\services\backup_service.py
import os
import time
import shutil
from datetime import datetime
from flask import current_app
from .logger import log_info, log_error
from .monitoring import monitoring_service, HealthStatus

class BackupService:
    """Service quản lý backup Neo4j database"""

    def __init__(self):
        self.backup_dir = None
        self.neo4j_backup_dir = None

    def _init_dirs(self):
        """Initialize backup directories lazily when app context is available"""
        if self.backup_dir is None:
            self.backup_dir = os.path.join(current_app.root_path, '..', 'backups')
            if not os.path.exists(self.backup_dir):
                os.makedirs(self.backup_dir)

            # Create subdirectory for Neo4j
            self.neo4j_backup_dir = os.path.join(self.backup_dir, 'neo4j')

            if not os.path.exists(self.neo4j_backup_dir):
                os.makedirs(self.neo4j_backup_dir)

    def backup_neo4j(self):
        """Backup Neo4j database"""
        try:
            self._init_dirs()
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_path = os.path.join(
                self.neo4j_backup_dir,
                f'neo4j_backup_{timestamp}'
            )

            # Get Neo4j connection info
            neo4j_uri = current_app.config['NEO4J_URI']
            neo4j_user = current_app.config['NEO4J_USERNAME']
            neo4j_password = current_app.config['NEO4J_PASSWORD']

            # Create backup using neo4j-admin backup
            os.system(
                f'neo4j-admin backup --from={neo4j_uri} '
                f'--backup-dir={backup_path} '
                f'--username={neo4j_user} --password={neo4j_password}'
            )

            if os.path.exists(backup_path):
                log_info(f"Neo4j backup created successfully: {backup_path}")
                monitoring_service.update_component_health(
                    'neo4j',
                    HealthStatus.OK,
                    metrics={'last_backup': timestamp}
                )
                return True
            else:
                raise Exception("Backup directory not created")

        except Exception as e:
            log_error(f"Neo4j backup failed: {str(e)}")
            monitoring_service.update_component_health(
                'neo4j',
                HealthStatus.ERROR,
                error=e
            )
            return False

    def cleanup_old_backups(self, days_to_keep=7):
        """Xóa các backup cũ hơn số ngày chỉ định"""
        try:
            self._init_dirs()
            current_time = time.time()
            max_age = days_to_keep * 86400  # Convert days to seconds

            for item in os.listdir(self.neo4j_backup_dir):
                item_path = os.path.join(self.neo4j_backup_dir, item)
                if os.path.getctime(item_path) < (current_time - max_age):
                    if os.path.isfile(item_path):
                        os.remove(item_path)
                    elif os.path.isdir(item_path):
                        shutil.rmtree(item_path)
                    log_info(f"Deleted old backup: {item_path}")

            return True

        except Exception as e:
            log_error(f"Cleanup failed: {str(e)}")
            return False

# Singleton instance
backup_service = BackupService()
