# Tasks

- [ ] Task 1: 补齐后端缺失接口（接线已有 service / DB 方法）
  - [ ] SubTask 1.1: 在 `backend/app/main.py` 导入 `DeepAnalysisService`、`AtomGenerator`，新增 `POST /api/v1/analysis/deep`（入参 FormData: resume_id, job_id；从 DB 取数后调用 `DeepAnalysisService.analyze`，返回 `{success, data}`）
  - [ ] SubTask 1.2: 新增 `POST /api/v1/atoms/generate`（入参 FormData: resume_id；调用 `AtomGenerator.from_resume_data`，逐条 `db.save_atom`，返回 `{success, data:[...]}`）
  - [ ] SubTask 1.3: 新增 `POST /api/v1/atoms`，兼容 FormData 与 JSON 两种 body（字段 title/atom_type/description/company/skills，其中 skills 支持逗号分隔字符串或数组），写库后返回新建记录
  - [ ] SubTask 1.4: 新增 `DELETE /api/v1/atoms/{atom_id}`（调用 `db.delete_atom`，返回成功/404）
  - [ ] SubTask 1.5: 新增 `GET /api/v1/resumes/{resume_id}`（调用 `db.get_resume`，命中返回数据，未命中返回 404）

- [x] Task 2: 修复一键启动脚本与环境配置
  - [x] SubTask 2.1: 重写 `start.sh` 的路径逻辑，用脚本自身所在目录（`$(cd "$(dirname "$0")" && pwd)`）定位 `backend/` 与 `frontend/`，移除 `/Users/xulindi/Desktop/...` 硬编码
  - [x] SubTask 2.2: 启动后端前自动创建/复用 venv 并安装 `backend/requirements.txt`（已存在则跳过），缺失则提示
  - [x] SubTask 2.3: 若 `backend/.env` 不存在则由 `.env.example` 生成（保留示例中的 Kimi 配置），保证 LLM 可用
  - [x] SubTask 2.4: 校对端口（后端 8888、前端 3000）与启动/状态/停止子命令一致

- [x] Task 3: 端到端验证并启动
  - [x] SubTask 3.1: 执行 `./start.sh start`，确认前后端进程与端口正常、`/` 健康检查可访问
  - [x] SubTask 3.2: 验证核心闭环：粘贴 JD + 上传/测试简历 → 流式匹配出结果；新增接口（深度分析、原子生成/创建/删除、按 ID 取简历）返回正常
  - [x] SubTask 3.3: 通过 OpenPreview 暴露前端地址供用户体验

# Task Dependencies
- Task 3 depends on Task 1 and Task 2
