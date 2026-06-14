# Offer 捕手后端 Docker 镜像
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    build-essential \
    libpoppler-cpp-dev \
    ghostscript \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .

# 安装 Python 依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY app ./app
COPY .env.example .env

# 创建必要的目录
RUN mkdir -p logs data uploads

# 暴露端口
EXPOSE 8888

# 启动命令
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8888"]
