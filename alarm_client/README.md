# Anomaly Detection Dashboard

## 项目简介
本项目是一个异常检测上报系统，包含以下功能：
- 从本地文件夹加载图像。
- 将图像上传到后端进行异常检测。

## 文件结构
```
.
├── app.py                # 主应用程序入口
├── index.html            # 前端页面
├── upload_detection.py   # 图像上传脚本
├── test_img/             # 测试图像文件夹
```

## 使用说明

### 环境依赖
1. Python 3.8 或更高版本。
2. 安装必要的依赖库：
   ```bash
   pip install flask, datetime
   ```

### 运行步骤
1. 确保 `test_img/` 文件夹中包含需要上传的测试图像。
2. 首先运行后端代码：app.py
3. 网页浏览：http://localhost:5000 。 注意: 如果笔记本通过网线链接开发板，这里的localhost需要换成开发板的局域网IP.
2. 运行 `upload_detection.py` 脚本：
   ```bash
   python upload_detection.py
   ```
   注意：此脚本为上传图像的接口，可以把文件中的upload_numpy_image方法，import到你的模型推理函数中，得到实际的模型推理结果之后调用此方法上传图像到后端，然后后端再上传到前端。

### 配置后端地址
在 `upload_detection.py` 文件中，修改以下变量以配置后端 API 地址：
```python
BACKEND_URL = "http://127.0.0.1:5000/api/upload"
```

## 注意事项
- 开发板配置局域网IP，通过网线链接笔记本电脑，笔记本同样配置局域网IP，和开发板在同一个网段；