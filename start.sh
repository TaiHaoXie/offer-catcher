#!/bin/bash
# Offer 捕手 - 单前端版本启动脚本

set -e

# 脚本所在目录（仓库根目录），避免硬编码绝对路径
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"

echo "======================================"
echo "  Offer 捕手 - frontend + backend"
echo "======================================"
echo ""

# 检查端口占用
check_port() {
    if lsof -Pi :$1 -sTCP:LISTEN -t >/dev/null 2>&1 ; then
        echo "⚠️  端口 $1 已被占用，请先停止占用进程"
        return 1
    fi
    return 0
}

# 准备 Python 虚拟环境与依赖
prepare_backend_env() {
    cd "$BACKEND_DIR"

    # 创建/复用虚拟环境
    if [ ! -d "venv" ]; then
        echo "� 创建 Python 虚拟环境..."
        python3 -m venv venv
        source venv/bin/activate
        echo "📦 安装后端依赖（首次较慢）..."
        pip install --upgrade pip > /dev/null 2>&1 || true
        pip install -r requirements.txt
    else
        source venv/bin/activate
        # 复用已有 venv 时也同步一次依赖，确保新增依赖（如鉴权所需 PyJWT/passlib）已安装
        pip install -r requirements.txt > /dev/null 2>&1 || true
    fi

    # 准备 .env（缺失则由 .env.example 派生）
    if [ ! -f ".env" ]; then
        if [ -f ".env.example" ]; then
            cp .env.example .env
            echo "📝 已根据 .env.example 生成 backend/.env"
        else
            echo "⚠️  缺少 .env 与 .env.example，LLM 相关功能可能不可用"
        fi
    fi
}

# 启动后端
start_backend() {
    echo "🔧 启动后端服务..."
    prepare_backend_env
    cd "$BACKEND_DIR"
    uvicorn app.main:app --reload --port 8888 > /tmp/offer-catcher-backend.log 2>&1 &
    BACKEND_PID=$!
    echo "   后端 PID: $BACKEND_PID"
    echo $BACKEND_PID > /tmp/offer-catcher-backend.pid
}

# 启动前端（唯一保留前端）
start_frontend() {
    echo "🎨 启动前端服务..."
    cd "$FRONTEND_DIR"
    python3 -m http.server 3000 > /tmp/offer-catcher-frontend.log 2>&1 &
    FRONTEND_PID=$!
    echo "   前端 PID: $FRONTEND_PID"
    echo $FRONTEND_PID > /tmp/offer-catcher-frontend.pid
}

# 停止服务
stop_services() {
    echo "🛑 停止所有服务..."
    if [ -f /tmp/offer-catcher-backend.pid ]; then
        kill $(cat /tmp/offer-catcher-backend.pid) 2>/dev/null || true
        rm /tmp/offer-catcher-backend.pid
    fi
    if [ -f /tmp/offer-catcher-frontend.pid ]; then
        kill $(cat /tmp/offer-catcher-frontend.pid) 2>/dev/null || true
        rm /tmp/offer-catcher-frontend.pid
    fi
    pkill -f "uvicorn app.main:app" 2>/dev/null || true
    pkill -f "python3 -m http.server 3000" 2>/dev/null || true
    echo "✅ 服务已停止"
}

# 检查服务状态
check_status() {
    echo "📊 服务状态："
    echo ""
    if curl -s http://localhost:8888/ > /dev/null 2>&1; then
        echo "✅ 后端运行正常 (http://localhost:8888)"
        curl -s http://localhost:8888/ | jq .database_stats 2>/dev/null || echo ""
    else
        echo "❌ 后端未运行"
    fi

    if curl -s http://localhost:3000/ > /dev/null 2>&1; then
        echo "✅ 前端运行正常 (http://localhost:3000)"
    else
        echo "❌ 前端未运行"
    fi
}

# 主逻辑
case "${1:-start}" in
    start)
        stop_services
        sleep 1
        check_port 8888 && check_port 3000 || exit 1
        start_backend
        sleep 2
        start_frontend
        sleep 1
        echo ""
        echo "✅ 所有服务已启动！"
        echo ""
        echo "📍 访问地址："
        echo "   前端: http://localhost:3000/index.html"
        echo "   后端: http://localhost:8888/"
        echo ""
        echo "ℹ️  deprecated-frontend-nextjs/ 已废弃，请不要再作为运行入口"
        echo ""
        echo "📝 查看日志:"
        echo "   后端: tail -f /tmp/offer-catcher-backend.log"
        echo "   前端: tail -f /tmp/offer-catcher-frontend.log"
        ;;
    stop)
        stop_services
        ;;
    status)
        check_status
        ;;
    restart)
        stop_services
        sleep 1
        $0 start
        ;;
    *)
        echo "用法: $0 {start|stop|status|restart}"
        exit 1
        ;;
esac
