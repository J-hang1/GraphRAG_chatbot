"""
Simple performance monitoring utilities
"""
import time
import functools
from typing import Dict, Any, Callable
from datetime import datetime
from .logger import log_info, log_error


class SimplePerformanceMonitor:
    """Simple performance monitor for agents"""
    
    def __init__(self):
        self.metrics = {
            'agent_calls': {},
            'response_times': {},
            'error_counts': {}
        }
    
    def record_call(self, agent_name: str, response_time: float, success: bool = True):
        """Record agent call metrics"""
        # Initialize if not exists
        if agent_name not in self.metrics['agent_calls']:
            self.metrics['agent_calls'][agent_name] = 0
            self.metrics['response_times'][agent_name] = []
            self.metrics['error_counts'][agent_name] = 0
        
        # Record metrics
        self.metrics['agent_calls'][agent_name] += 1
        self.metrics['response_times'][agent_name].append(response_time)
        
        if not success:
            self.metrics['error_counts'][agent_name] += 1
        
        # Keep only last 50 response times
        if len(self.metrics['response_times'][agent_name]) > 50:
            self.metrics['response_times'][agent_name] = \
                self.metrics['response_times'][agent_name][-50:]
    
    def get_agent_stats(self, agent_name: str) -> Dict[str, Any]:
        """Get statistics for specific agent"""
        if agent_name not in self.metrics['agent_calls']:
            return {}
        
        response_times = self.metrics['response_times'][agent_name]
        if not response_times:
            return {}
        
        total_calls = self.metrics['agent_calls'][agent_name]
        error_count = self.metrics['error_counts'][agent_name]
        
        return {
            'total_calls': total_calls,
            'error_count': error_count,
            'success_rate': ((total_calls - error_count) / total_calls * 100) if total_calls > 0 else 0,
            'avg_response_time': sum(response_times) / len(response_times),
            'min_response_time': min(response_times),
            'max_response_time': max(response_times),
            'recent_calls': len(response_times)
        }
    
    def get_all_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all agents"""
        return {
            agent_name: self.get_agent_stats(agent_name)
            for agent_name in self.metrics['agent_calls'].keys()
        }
    
    def print_summary(self):
        """Print performance summary"""
        stats = self.get_all_stats()
        
        if not stats:
            print("📊 No performance data available")
            return
        
        print("\n" + "="*60)
        print("📊 AGENT PERFORMANCE SUMMARY")
        print("="*60)
        
        for agent_name, agent_stats in stats.items():
            if not agent_stats:
                continue
                
            print(f"\n🤖 {agent_name.upper()}:")
            print(f"   Total Calls: {agent_stats['total_calls']}")
            print(f"   Success Rate: {agent_stats['success_rate']:.1f}%")
            print(f"   Avg Response: {agent_stats['avg_response_time']:.2f}s")
            print(f"   Min/Max: {agent_stats['min_response_time']:.2f}s / {agent_stats['max_response_time']:.2f}s")
            
            # Status indicator
            avg_time = agent_stats['avg_response_time']
            if avg_time > 5.0:
                status = "🔴 SLOW"
            elif avg_time > 2.0:
                status = "🟡 NORMAL"
            else:
                status = "🟢 FAST"
            print(f"   Status: {status}")
        
        print("="*60)


# Global monitor instance
monitor = SimplePerformanceMonitor()


def performance_timer(agent_name: str):
    """Decorator to measure agent performance"""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True
            
            try:
                result = func(*args, **kwargs)
                return result
            except Exception as e:
                success = False
                raise
            finally:
                end_time = time.time()
                response_time = end_time - start_time
                
                # Record performance
                monitor.record_call(agent_name, response_time, success)
                
                # Log performance
                status = "✅" if success else "❌"
                log_info(f"{status} {agent_name}: {response_time:.2f}s")
        
        return wrapper
    return decorator


def record_performance(agent_name: str, response_time: float, success: bool = True):
    """Manually record performance metrics"""
    monitor.record_call(agent_name, response_time, success)


def get_performance_stats(agent_name: str = None) -> Dict[str, Any]:
    """Get performance statistics"""
    if agent_name:
        return monitor.get_agent_stats(agent_name)
    else:
        return monitor.get_all_stats()


def print_performance_summary():
    """Print performance summary"""
    monitor.print_summary()


def measure_time(func: Callable) -> tuple:
    """Measure execution time of a function"""
    start_time = time.time()
    try:
        result = func()
        success = True
        return result, time.time() - start_time, success
    except Exception as e:
        success = False
        return None, time.time() - start_time, success


# Context manager for measuring performance
class PerformanceContext:
    """Context manager for measuring performance"""
    
    def __init__(self, agent_name: str, operation: str = ""):
        self.agent_name = agent_name
        self.operation = operation
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        if self.operation:
            log_info(f"🚀 Starting {self.agent_name}: {self.operation}")
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is None:
            return
        
        response_time = time.time() - self.start_time
        success = exc_type is None
        
        # Record performance
        monitor.record_call(self.agent_name, response_time, success)
        
        # Log result
        status = "✅" if success else "❌"
        operation_text = f": {self.operation}" if self.operation else ""
        log_info(f"{status} {self.agent_name}{operation_text} - {response_time:.2f}s")


# Usage examples:
# 
# # Using decorator
# @performance_timer('recommend')
# def process_recommendation(message):
#     # Your code here
#     pass
#
# # Using context manager
# with PerformanceContext('graphrag', 'execute_query'):
#     # Your code here
#     pass
#
# # Manual recording
# start = time.time()
# # Your code here
# record_performance('router', time.time() - start, success=True)
