# Offer 捕手

> 学生求职匹配智能体，当前只保留 `frontend/ + backend/` 这一套运行形态。

## 当前状态

- 主前端：`frontend/index.html`，通过 `python3 -m http.server 3000` 提供静态页面。
- 主后端：`backend/app/main.py`，通过 `uvicorn app.main:app --reload --port 8888` 启动。
- 一键入口：`./start.sh`。
- 当前项目目录里可能保留历史备份文件，例如 `frontend/index-new-backup.html`、`backend/app/main.py.bak`。这些文件只用于回看历史，不是运行入口。
- 旧 Next.js 路线如出现在历史文档中，均不作为当前实现依据。

## 功能

- 简历上传 / 文本解析
- 岗位 JD 解析
- 匹配分析
- 匹配分析流式输出
- 经历原子库
- 投递追踪
- 历史记录

## 启动方式

### 后端

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --port 8888
```

后端地址：`http://localhost:8888`

### 前端

```bash
cd frontend
python3 -m http.server 3000
```

前端地址：`http://localhost:3000/index.html`

### 一键启动

```bash
./start.sh
```

查看状态：

```bash
./start.sh status
```

## 项目结构

```text
offer-catcher/
├── backend/                  # FastAPI 后端
├── frontend/                 # 当前唯一前端（静态 HTML）
├── docs/                     # 产品方案、交接说明和提示词文档
├── start.sh                  # macOS/Linux 一键启动脚本
├── start.bat                 # Windows 启动脚本（同步到静态前端 + 8888 后端）
└── test_all_features.sh      # 本地接口验证脚本
```

## 维护说明

- 前端的真实主文件是 `frontend/index.html`。
- 后端的真实主文件是 `backend/app/main.py`。
- 后端默认端口是 `8888`，前端默认端口是 `3000`。
- 匹配分析流式输出已按标准 SSE `event + data` 协议接入。
- 如果需要继续开发前端，请直接改 `frontend/index.html`，不要重新启用历史 Next.js 路线。
- 不要删除历史备份文件，除非已经完成引用检查和完整回归验证。
