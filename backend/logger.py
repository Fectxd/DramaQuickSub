"""
日志系统 - 用于exe无控制台模式
"""
import sys
import os
from datetime import datetime

class Logger:
    def __init__(self, log_file):
        self.log_file = log_file
        self.terminal = sys.stdout
        
    def write(self, message):
        if message.strip():  # 忽略空行
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            formatted = f"[{timestamp}] {message}"
            # 写入文件
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(formatted)
                if not message.endswith('\n'):
                    f.write('\n')
            # 同时输出到终端（如果有）
            if self.terminal:
                try:
                    self.terminal.write(message)
                except:
                    pass
    
    def flush(self):
        if self.terminal:
            try:
                self.terminal.flush()
            except:
                pass
    
    def isatty(self):
        """uvicorn需要此方法"""
        return False

def setup_logging():
    """设置日志输出到文件"""
    if getattr(sys, 'frozen', False):
        # 打包后：日志文件在exe目录
        log_dir = os.path.dirname(sys.executable)
    else:
        # 开发环境：日志在项目根目录
        log_dir = os.path.dirname(os.path.dirname(__file__))
    
    log_file = os.path.join(log_dir, 'app.log')
    
    # 清空旧日志
    if os.path.exists(log_file):
        try:
            os.remove(log_file)
        except:
            pass
    
    # 重定向标准输出和错误输出
    sys.stdout = Logger(log_file)
    sys.stderr = Logger(log_file)
    
    print(f"=== Application started at {datetime.now()} ===")
    print(f"Log file: {log_file}")
    print(f"sys.frozen: {getattr(sys, 'frozen', False)}")
    print(f"sys.executable: {sys.executable}")
