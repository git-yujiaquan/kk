from flask import Flask, request, jsonify, send_from_directory
import json
from datetime import datetime
import os

app = Flask(__name__, static_folder='.')

# 存储检测结果（实际应用建议用数据库）
detections = []

@app.route('/')
def serve_frontend():
    """提供前端页面"""
    return send_from_directory('.', 'index.html')

@app.route('/api/detections', methods=['GET'])
def get_detections():
    """获取所有检测记录"""
    return jsonify({
        'success': True,
        'detections': detections.copy()
    })

@app.route('/api/upload', methods=['POST'])
def upload_detection():
    """接收边缘设备上传的检测结果（Base64）"""
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        required_fields = ['image_base64', 'category', 'location']
        for field in required_fields:
            if field not in data:
                return jsonify({'success': False, 'error': f'Missing field: {field}'}), 400

        new_detection = {
            'id': str(len(detections) + 1),
            'image_base64': data['image_base64'],
            'category': data['category'],
            'location': data['location'],
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        detections.insert(0, new_detection)
        return jsonify({'success': True, 'id': new_detection['id']})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

if __name__ == '__main__':
    # 启动前检查 index.html 是否存在
    if not os.path.exists('index.html'):
        print("❌ 错误: 请确保 index.html 文件在当前目录！")
        exit(1)
    print("✅ 启动成功！请访问 http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)