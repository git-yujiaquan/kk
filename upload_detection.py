import requests
import base64
import cv2
import numpy as np
from config_manager import load_config
from datetime import datetime
import os
import logging


# 日志
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s [%(name)s] %(message)s")

# 配置：后端服务地址（仅加载一次）
_CONFIG = load_config()
_BASE_URL = _CONFIG.get("backend_base_url", "http://127.0.0.1:5000").rstrip("/")
BACKEND_UPLOAD_URL = f"{_BASE_URL}/api/upload"

def upload_numpy_image(numpy_image, category="未知", location="未知位置"):
    """
    将 NumPy 格式的图像上传到后端异常检测上报系统。

    :param numpy_image: NumPy array (H, W, C)，BGR 或 RGB 格式均可。
    :param category: 检测类别，有可能只是个类别编号，由前端匹配显示
    :param location: 检测位置，GPS获取的位置信息
    :return: 成功返回 True，失败返回 False
    """
    try:
        # 确保图像是 uint8 类型
        if numpy_image.dtype != np.uint8:
            numpy_image = numpy_image.astype(np.uint8)

        # 如果是 RGB，转为 BGR（OpenCV 默认）
        # 如果你的图像是 RGB，可以取消下面这行注释
        # numpy_image = cv2.cvtColor(numpy_image, cv2.COLOR_RGB2BGR)

        # 将 NumPy 图像编码为 JPEG 格式
        success, buffer = cv2.imencode('.jpg', numpy_image)
        if not success:
            raise ValueError("图像编码失败")

        # 转换为 Base64 字符串
        image_base64 = base64.b64encode(buffer).decode('utf-8')

        # 构造请求数据
        payload = {
            "image_base64": image_base64,
            "category": category,
            "location": location
        }

        # 发送 POST 请求
        response = requests.post(BACKEND_UPLOAD_URL, json=payload, timeout=10)
        response.raise_for_status()
        result = response.json()

        if result.get('success'):
            logger.info(f"检测结果上传成功，ID: {result.get('id')}")
            return True
        else:
            logger.error(f"上传失败: {result.get('error', '未知错误')}")
            return False

    except Exception as e:
        logger.exception(f"上传过程中发生错误: {e}")
        return False