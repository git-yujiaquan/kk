import time
import queue
import json
from pathlib import Path
from config_manager import load_config
import cv2
from datetime import datetime
from logger_setup import get_logger
from upload_detection import upload_numpy_image

def alarm_handler(alarm_queue, stop_event, record_cmd_queue=None):
    """
    从报警队列取信息，执行报警处理（示例：打印日志、写入文件）
    """
    try:
        _cfg = load_config()
    except Exception:
        _cfg = {}
    _rt = _cfg.get("record_trigger", {}) if isinstance(_cfg, dict) else {}
    try:
        _required_hits = int(_rt.get("required_hits", 1))
    except Exception:
        _required_hits = 1
    _types_raw = _rt.get("types", None)
    _types = set([str(x).strip() for x in _types_raw]) if isinstance(_types_raw, (list, set, tuple)) else None
    # 冷却时间与录制时长使用同一配置值（优先 duration_sec，回退 cooldown_sec）
    try:
        _cooldown_duration = float(_rt.get("duration_sec", _rt.get("cooldown_sec", 60)))
    except Exception:
        _cooldown_duration = 60.0
    _cooldown = _cooldown_duration
    _duration = _cooldown_duration
    _last_trigger_ts = 0.0
    _hit_streak = 0  # 连续命中计数
    logger = get_logger(__name__)
    while not stop_event.is_set():
        try:
            # 从报警队列取信息（阻塞等待，超时1秒检查退出信号）
            alarm_info = alarm_queue.get(block=True, timeout=1)
            alarm_queue.task_done()  # 标记报警已处理
            
            # 示例处理逻辑：打印报警并写入日志文件
            _log_obj = dict(alarm_info)
            _log_obj.pop("frame", None)
            logger.info(f"alarm_handler: alarm_info: {_log_obj}")
            
            # 写入日志文件（排除不可序列化的原始帧）
            alarm_json_path = Path(__file__).resolve().parent / "outputs" / "alarm_log.jsonl"
            with open(str(alarm_json_path), "a", encoding="utf-8") as f:
                f.write(json.dumps(_log_obj, ensure_ascii=False) + "\n")

            _save_pic = _cfg.get("save_pic", False)
            if _save_pic:
                try:
                    infer_dir = Path(__file__).resolve().parent / "outputs" / "alarm_frames"
                    infer_dir.mkdir(parents=True, exist_ok=True)
                    ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    cv2.imwrite(str(infer_dir / f"{ts}.jpg"), alarm_info.get("frame"))
                except Exception:
                    pass

            _ok = True
            if _types is not None:
                try:
                    _t = str(alarm_info.get("type", ""))
                except Exception:
                    _t = ""
                _ok = _t in _types

            # 使用连续命中次数判断
            if _ok:
                _hit_streak += 1
            else:
                _hit_streak = 0
            _now = time.time()
            if (_hit_streak >= _required_hits) and (_now - _last_trigger_ts >= _cooldown):
                if record_cmd_queue is not None:
                    try:
                        # 发送带时长的开始录制指令，rtsp_processor 将据此录制指定时长
                        record_cmd_queue.put({"cmd": "start", "duration": _duration}, block=False)
                        _last_trigger_ts = _now
                        _hit_streak = 0  # 触发后重置计数
                    except Exception:
                        pass
            
            # 可扩展：发送HTTP请求、邮件、短信等
            # todo 获取位置以及类别，后续可能还会上传视频
            upload_numpy_image(alarm_info.get("frame"), "施工场景")
            
        except queue.Empty:
            # 队列空时继续等待
            continue
        except Exception as e:
            logger.exception(f"报警处理出错: {str(e)}")
    
    logger.info("报警处理模块已停止")