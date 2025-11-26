import queue
import threading
from rtsp_processor import rtsp_processor
from frame_analyzer import frame_analyzer
from alarm_handler import alarm_handler
from config_manager import load_config
from logger_setup import get_logger

def main():
    logger = get_logger(__name__)
    # 初始化队列（设置最大长度防止内存溢出）
    cfg = load_config()
    frame_queue = queue.Queue(maxsize=cfg.get("frame_queue_size", 100))    # 帧队列（缓存最多100帧）
    alarm_queue = queue.Queue(maxsize=cfg.get("alarm_queue_size", 200))    # 报警队列（缓存最多200条报警）
    record_cmd_queue = queue.Queue()
    
    # 线程停止信号（所有模块共享）
    stop_event = threading.Event()
    rtsp_url = cfg.get("rtsp_url", "rtsp://your-rtsp-url")
    fps = cfg.get("fps", 2)
    
    # 启动RTSP流处理线程
    rtsp_thread = threading.Thread( 
        target=rtsp_processor,
        args=(rtsp_url, frame_queue, stop_event),
        kwargs={
            "record_cmd_queue": record_cmd_queue,
            "fps": fps
        },
        daemon=True
    )
    
    # 启动帧分析线程
    analyzer_thread = threading.Thread(
        target=frame_analyzer,
        args=(frame_queue, alarm_queue, stop_event),
        daemon=True
    )
    
    # 启动报警处理线程
    alarm_thread = threading.Thread(
        target=alarm_handler,
        args=(alarm_queue, stop_event, record_cmd_queue),
        daemon=True
    )
    
    # 启动所有线程
    rtsp_thread.start()
    analyzer_thread.start()
    alarm_thread.start()
    logger.info("所有模块启动完成，按Ctrl+C退出")
    
    try:
        # 主线程阻塞等待退出信号
        while not stop_event.is_set():
            threading.Event().wait(1)  # 等待1秒，减少CPU占用
    except KeyboardInterrupt:
        logger.info("收到退出信号，正在停止所有模块...")
        stop_event.set()  # 通知所有线程停止
        
        # 等待所有线程结束
        rtsp_thread.join()
        analyzer_thread.join()
        alarm_thread.join()
        logger.info("所有模块已停止")

if __name__ == "__main__":
    main()