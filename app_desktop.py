"""
桌面应用主入口 - 集成 PyWebView 和 FastAPI
"""
import webview
import uvicorn
import threading
import os
import sys
from pathlib import Path

# 设置日志系统（必须在最开始，在任何导入之前）
try:
    from backend.logger import setup_logging
    setup_logging()
except Exception as e:
    print(f"Failed to setup logging: {e}")

# 确定资源路径（支持打包后的 exe）
if getattr(sys, 'frozen', False):
    # 打包后的 exe 运行 - 临时解压目录
    RESOURCE_DIR = Path(sys._MEIPASS)
    # exe 所在目录 - 用于 uploads 等运行时文件
    WORK_DIR = Path(sys.executable).parent
else:
    # 开发环境
    RESOURCE_DIR = Path(__file__).parent
    WORK_DIR = Path(__file__).parent

# 设置工作目录为 exe 所在目录（让 uploads 在 exe 旁边）
os.chdir(WORK_DIR)

# 添加资源目录到 Python 路径
sys.path.insert(0, str(RESOURCE_DIR))

from backend.main import app

# 全局变量
server_thread = None
should_stop = False

def start_backend():
    """在后台线程启动 FastAPI"""
    config = uvicorn.Config(
        app, 
        host="127.0.0.1", 
        port=8000, 
        log_level="error",  # 减少日志输出
        access_log=False
    )
    server = uvicorn.Server(config)
    server.run()

def on_closing():
    """窗口关闭时的回调"""
    global should_stop
    should_stop = True
    os._exit(0)  # 强制退出所有线程

def main():
    """主函数"""
    global server_thread
    
    # 启动后端服务器（后台线程）
    server_thread = threading.Thread(target=start_backend, daemon=True)
    server_thread.start()
    
    # 等待服务器启动 - 通过实际检测而不是固定等待
    import time
    import requests
    max_wait = 20  # 最多等待20秒
    wait_interval = 0.2
    total_waited = 0
    
    print("等待后端服务器启动...")
    while total_waited < max_wait:
        try:
            response = requests.get("http://127.0.0.1:8000", timeout=1)
            print("后端服务器已就绪")
            break
        except:
            time.sleep(wait_interval)
            total_waited += wait_interval
    else:
        print("警告: 后端服务器启动超时，但继续启动GUI...")
    
    # 获取屏幕尺寸并计算居中位置
    import tkinter as tk
    root = tk.Tk()
    screen_width = root.winfo_screenwidth()
    screen_height = root.winfo_screenheight()
    root.destroy()
    
    # 窗口尺寸
    window_width = 1275
    window_height = 780
    
    # 计算居中位置
    x = (screen_width - window_width) // 2
    y = (screen_height - window_height) // 2
    
    # 创建窗口
    window = webview.create_window(
        title='双语字幕编辑器',
        url='http://127.0.0.1:8000',
        width=window_width,
        height=window_height,
        x=x,
        y=y,
        resizable=True,
        min_size=(1000, 600)
    )
    
    # 设置窗口关闭回调
    window.events.closing += on_closing
    
    # 启动 GUI（阻塞直到窗口关闭）
    webview.start()

if __name__ == '__main__':
    main()
