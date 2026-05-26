FROM python:3.11-slim

LABEL maintainer="yan.shen"
LABEL description="Equipment Maintenance Web - Flask + Qwen AI"

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 复制应用代码
COPY . .

# 创建上传目录
RUN mkdir -p /app/static/uploads

EXPOSE 5000

# 使用 Waitress 生产级 WSGI 服务器（Windows/Linux 均可用）
CMD ["python", "-c", "from waitress import serve; from app import app; serve(app, host='0.0.0.0', port=5000)"]
