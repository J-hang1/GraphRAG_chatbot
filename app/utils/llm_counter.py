"""
Module để theo dõi số lần gọi LLM
"""
from colorama import init, Fore, Style
from functools import wraps
import time

# Khởi tạo colorama
init()

class LLMCounter:
    """Lớp theo dõi số lần gọi LLM"""
    
    def __init__(self):
        """Khởi tạo bộ đếm"""
        self.reset()
    
    def reset(self):
        """Reset bộ đếm"""
        self.count = 0
        self.total_time = 0
        self.calls = []
    
    def increment(self, function_name, args=None, kwargs=None, time_taken=0):
        """Tăng bộ đếm"""
        self.count += 1
        self.total_time += time_taken
        self.calls.append({
            'function': function_name,
            'args': args or [],
            'kwargs': kwargs or {},
            'time': time_taken
        })
    
    def get_count(self):
        """Lấy số lần gọi LLM"""
        return self.count
    
    def get_total_time(self):
        """Lấy tổng thời gian gọi LLM"""
        return self.total_time
    
    def get_average_time(self):
        """Lấy thời gian trung bình gọi LLM"""
        if self.count == 0:
            return 0
        return self.total_time / self.count
    
    def get_calls(self):
        """Lấy danh sách các lần gọi LLM"""
        return self.calls
    
    def print_stats(self):
        """In thống kê về số lần gọi LLM"""
        print(f"\n{Fore.CYAN}THỐNG KÊ GỌI LLM:{Style.RESET_ALL}")
        print(f"- Số lần gọi LLM: {self.count}")
        print(f"- Tổng thời gian: {self.total_time:.2f}s")
        if self.count > 0:
            print(f"- Thời gian trung bình: {self.get_average_time():.2f}s")
        
        if self.calls:
            print(f"\n{Fore.CYAN}CHI TIẾT CÁC LẦN GỌI LLM:{Style.RESET_ALL}")
            for i, call in enumerate(self.calls, 1):
                print(f"{i}. {call['function']} - {call['time']:.2f}s")
                if 'prompt' in call['kwargs']:
                    prompt_preview = call['kwargs']['prompt'][:100] + "..." if len(call['kwargs']['prompt']) > 100 else call['kwargs']['prompt']
                    print(f"   Prompt: {prompt_preview}")

# Tạo instance toàn cục của LLMCounter
llm_counter = LLMCounter()

def count_llm_call(func):
    """Decorator để đếm số lần gọi LLM"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        result = func(*args, **kwargs)
        end_time = time.time()
        time_taken = end_time - start_time
        
        # Tăng bộ đếm
        llm_counter.increment(
            function_name=func.__name__,
            args=args,
            kwargs=kwargs,
            time_taken=time_taken
        )
        
        return result
    return wrapper
