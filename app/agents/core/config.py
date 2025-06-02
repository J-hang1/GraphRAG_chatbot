from typing import Dict, Any
import yaml
import os
from pathlib import Path

class AgentConfig:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
        
    def __init__(self):
        if self._initialized:
            return
            
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._initialized = True
        
    def _load_config(self):
        """Load configuration from YAML file"""
        config_path = Path(__file__).parent / 'config.yaml'
        if config_path.exists():
            with open(config_path, 'r') as f:
                self._config = yaml.safe_load(f)
        else:
            # Default configuration
            self._config = {
                'message_bus': {
                    'max_queue_size': 1000,
                    'cache_ttl': 3600,
                    'priorities': ['default', 'high_priority'],
                    'rate_limit': {
                        'max_calls': 100,
                        'time_window': 1.0
                    }
                },
                'context': {
                    'ttl': 3600,
                    'max_size': 10000,
                    'cleanup_interval': 300
                },
                'agents': {
                    'graphrag': {
                        'cache_ttl': 3600,
                        'timeout': 30,
                        'max_retries': 3,
                        'batch_size': 100
                    },
                    'recommend': {
                        'cache_ttl': 1800,
                        'timeout': 15,
                        'max_retries': 3,
                        'preference_update_interval': 300
                    }
                },
                'logging': {
                    'level': 'INFO',
                    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                    'handlers': ['console', 'file'],
                    'log_file': 'agent.log',
                    'max_file_size': 10485760,  # 10MB
                    'backup_count': 5
                },
                'performance': {
                    'max_workers': 4,
                    'worker_timeout': 300,
                    'memory_limit': 1024,  # MB
                    'gc_interval': 3600
                }
            }
            
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        keys = key.split('.')
        value = self._config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
        
    def set(self, key: str, value: Any):
        """Set configuration value"""
        keys = key.split('.')
        config = self._config
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
        config[keys[-1]] = value
        
    def save(self):
        """Save configuration to YAML file"""
        config_path = Path(__file__).parent / 'config.yaml'
        with open(config_path, 'w') as f:
            yaml.dump(self._config, f)

# Global instance
agent_config = AgentConfig()

# Export config for backward compatibility
config = agent_config 