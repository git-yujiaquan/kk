import cv2
import time
import queue
import os
from datetime import datetime
from logger_setup import get_logger
from collections import deque
from config_manager import load_config

def rtsp_processor(rtsp_url, frame_queue, stop_event, fps=2, resize_size=(640, 640),
                   record_cmd_queue=None, clip_dir="outputs/clips", clip_duration_sec=60):
    """
    读取RTSP流：
    - 抽帧：按 original_fps / fps 的间隔将帧放入 frame_queue
    - 录制：使用 RTSP 原始帧率 original_fps 持续录制到本地
    """
    logger = get_logger(__name__)
    cap = None
    writer = None
    recording_end_ts = 0.0
    pending_start = False
    pending_duration = float(clip_duration_sec)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    # 预录缓冲：从配置读取缓冲时间（秒），默认0表示不启用
    try:
        _cfg = load_config()
    except Exception:
        _cfg = {}
    _rt = _cfg.get("record_trigger", {}) if isinstance(_cfg, dict) else {}
    try:
        _buffer_sec = float(_rt.get("record_buffer_sec", 0))
    except Exception:
        _buffer_sec = 0.0
    _frame_buffer = deque()  # 存 (ts, frame)
    def _ensure_rtsp_tcp(url: str) -> str:
        try:
            if url.startswith("rtsp://") and "rtsp_transport=" not in url:
                sep = "&" if "?" in url else "?"
                return f"{url}{sep}rtsp_transport=tcp"
        except Exception:
            pass
        return url

    def _augment_rtsp_url(url: str) -> str:
        """为 RTSP URL 补充常用的 FFmpeg 可靠性参数（若未显式设置）。"""
        try:
            if not url.startswith("rtsp://"):
                return url
            q = "?" in url
            def add_param(u: str, k: str, v: str) -> str:
                return u if (k+"=") in u else (f"{u}{'&' if q or ('?' in u) else '?'}{k}={v}")
            u = url
            u = add_param(u, "rtsp_transport", "tcp")
            u = add_param(u, "stimeout", "5000000")  # 连接/首包超时(微秒)
            u = add_param(u, "rw_timeout", "5000000") # 读写超时(微秒)
            u = add_param(u, "probesize", "32768")
            u = add_param(u, "analyzeduration", "1000000")
            u = add_param(u, "reorder_queue_size", "0")
            u = add_param(u, "max_delay", "0")
            return u
        except Exception:
            return url

    while not stop_event.is_set():
        # 初始化或重连RTSP流
        if not cap or not cap.isOpened():
            # 设置一次 FFmpeg 捕获选项，进一步约束超时（若外部未设置）
            os.environ.setdefault(
                "OPENCV_FFMPEG_CAPTURE_OPTIONS",
                "rtsp_transport;tcp|stimeout;5000000|rw_timeout;5000000"
            )

            # 仅使用增强后的 URL + FFmpeg 后端
            robust_url = _augment_rtsp_url(rtsp_url)
            attempts = [
                (robust_url, cv2.CAP_FFMPEG, "ffmpeg_tcp"),
            ]
            cap = None
            used_mode = None
            for url, backend, mode in attempts:
                try:
                    c = cv2.VideoCapture(url) if backend is None else cv2.VideoCapture(url, backend)
                except Exception:
                    c = None
                if c is not None and c.isOpened():
                    # 打开后尽量设置读超时，避免长时间无数据卡住
                    try:
                        if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
                            c.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 5000)
                    except Exception:
                        pass
                    cap = c
                    used_mode = mode
                    break
                if c is not None:
                    try:
                        c.release()
                    except Exception:
                        pass
            if not cap or not cap.isOpened():
                logger.warning(f"无法连接RTSP流: {rtsp_url}，10秒后重试（已尝试 FFmpeg+TCP 及默认）...")
                time.sleep(10)
                continue
            # 获取原帧率（用于计算抽帧间隔）
            original_fps = cap.get(cv2.CAP_PROP_FPS) or 25  # 默认为25FPS
            frame_interval = max(1, round(original_fps / fps))
            logger.info(f"RTSP流连接成功（mode={used_mode}），原帧率: {original_fps:.1f}FPS，抽帧间隔: {frame_interval}帧")
            frame_count = 0  # 重置帧计数器
        
        if record_cmd_queue is not None:
            try:
                cmd = record_cmd_queue.get_nowait()
                if isinstance(cmd, dict):
                    try:
                        c = str(cmd.get("cmd", "")).strip().lower()
                    except Exception:
                        c = ""
                    if c == "start":
                        pending_start = True
                        try:
                            pending_duration = float(cmd.get("duration", clip_duration_sec))
                        except Exception:
                            pending_duration = float(clip_duration_sec)
                    elif c == "stop":
                        recording_end_ts = 0.0
                else:
                    # 忽略非字典命令
                    pass
                record_cmd_queue.task_done()
            except queue.Empty:
                pass

        # 读取帧
        ret, frame = cap.read()
        if not ret:
            logger.warning("读取帧失败，尝试重连...")
            cap.release()
            cap = None
            time.sleep(1)
            continue
        
        now = time.time()
        # 维护预录缓冲：按时间窗口保留最近 _buffer_sec 秒的帧
        if _buffer_sec > 0:
            try:
                _frame_buffer.append((now, frame.copy()))
                # 清理过期帧
                while _frame_buffer and (now - _frame_buffer[0][0] > _buffer_sec):
                    _frame_buffer.popleft()
            except Exception:
                # 内存不足时可适当丢弃
                if _frame_buffer:
                    _frame_buffer.popleft()

        if pending_start:
            try:
                os.makedirs(clip_dir, exist_ok=True)
                h, w = frame.shape[:2]
                # 录制使用原始流帧率
                try:
                    rec_fps = float(original_fps)
                    if rec_fps <= 0:
                        rec_fps = 25.0
                except Exception:
                    rec_fps = 25.0
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                out_path = os.path.join(clip_dir, f"clip_{ts}.mp4")
                writer = cv2.VideoWriter(out_path, fourcc, rec_fps, (w, h))
                if writer is None or not writer.isOpened():
                    logger.error(f"启动录制失败: 无法打开输出文件 {out_path}")
                    writer = None
                else:
                    recording_end_ts = now + float(pending_duration)
                    logger.info(f"开始录制: {out_path}，预计持续 {pending_duration} 秒")
                    # 写入预录缓冲中的帧（时间在 _buffer_sec 窗口内的）
                    if _buffer_sec > 0 and _frame_buffer:
                        try:
                            for ts_buf, f_buf in list(_frame_buffer):
                                if (now - ts_buf) <= _buffer_sec:
                                    try:
                                        writer.write(f_buf)
                                    except Exception:
                                        pass
                        except Exception:
                            pass
            except Exception as e:
                logger.exception(f"启动录制异常: {e}")
                writer = None
                recording_end_ts = 0.0
            finally:
                pending_start = False

        if writer is not None:
            try:
                writer.write(frame)
            except Exception as e:
                logger.exception(f"写入录制帧失败: {e}")
            if now >= recording_end_ts or stop_event.is_set():
                try:
                    writer.release()
                except Exception:
                    pass
                writer = None
                recording_end_ts = 0.0
                logger.info("录制结束")

        # 按间隔抽帧
        if frame_count % frame_interval == 0:
            # 放入队列（队列满时丢弃）
            try:
                frame_queue.put(frame, block=True, timeout=1)
                logger.info(f"帧放入队列，当前队列大小: {frame_queue.qsize()}")
            except queue.Full:
                logger.warning("帧队列已满，丢弃当前帧")
        
        frame_count += 1
        # 检查退出信号（避免阻塞在read()时无法退出）
        if stop_event.is_set():
            break
    
    # 释放资源
    if cap:
        cap.release()
    if writer is not None:
        try:
            writer.release()
        except Exception:
            pass
    logger.info("RTSP流处理模块已停止")