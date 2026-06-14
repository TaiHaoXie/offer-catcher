@echo off
REM Offer 捕手 - Windows 快速启动脚本（静态前端 + FastAPI 后端）

echo 🚀 启动 Offer 捕手...

REM 检查是否在项目根目录
if not exist "backend" (
    echo ❌ 请在项目根目录运行此脚本
    pause
    exit /b 1
)

REM 启动后端
echo 📦 启动后端服务...
cd backend

REM 检查虚拟环境
if not exist "venv" (
    echo 创建 Python 虚拟环境...
    python -m venv venv
)

REM 激活虚拟环境
call venv\Scripts\activate.bat

REM 检查依赖
if not exist "venv\Lib\site-packages\litellm" (
    echo 安装后端依赖...
    pip install -q -r requirements.txt
)

REM 检查环境变量
if not exist ".env" (
    echo ⚠️  请先配置 backend\.env 文件
    echo    复制 backend\.env.example 为 backend\.env
    echo    然后填入你的 API Key
    pause
    exit /b 1
)

REM 启动后端（新窗口）
echo 后端启动中... (http://localhost:8888)
start "Offer-Catcher-Backend" cmd /k "uvicorn app.main:app --reload --port 8888"

REM 等待后端启动
timeout /t 3 /nobreak >nul

cd ..

REM 启动前端
echo 🎨 启动前端服务...
cd frontend

REM 启动前端（新窗口）
echo 前端启动中... (http://localhost:3000/index.html)
start "Offer-Catcher-Frontend" cmd /k "python -m http.server 3000"

echo.
echo ✅ Offer 捕手 启动成功！
echo.
echo 📍 访问地址:
echo    前端: http://localhost:3000/index.html
echo    后端: http://localhost:8888
echo    API文档: http://localhost:8888/docs
echo.
echo ℹ️  当前主前端是 frontend\index.html，不再使用历史 Next.js 入口
echo ⏹️  关闭窗口即可停止服务
echo.

pause
