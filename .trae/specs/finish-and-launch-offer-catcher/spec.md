# 完成并启动「Offer 捕手」参赛作品 Spec

## Why
项目（学生 AI 求职智能匹配智能体）主体已完成约 90%：FastAPI 后端 + 单页前端 `frontend/index.html`，核心闭环（简历解析 / JD 解析 / 流式匹配分析 / 优化建议 / 历史记录 / 经历原子库 / 校招评分）大部分已实现。但作为参赛作品当前无法稳定一键跑通，且前端存在若干"点了没反应/报错"的按钮，影响演示完整度与作品质量。本次目标是补齐运行链路与缺失接口，让作品可被评委直接启动、完整体验。

核心痛点对应能力：
- 痛点1（海量岗位中找匹配岗位耗时）→ JD 解析 + 匹配度计算 + 投递建议。
- 痛点2（不确定简历与岗位匹配度、不知如何优化）→ 匹配分析 + 优化建议 + 定制简历 + 校招初筛评分。

## What Changes
- 修复 `start.sh`：去除硬编码的 `/Users/xulindi/Desktop/...` 路径，改为基于脚本所在目录的相对路径；自动创建/复用 Python 虚拟环境并安装依赖；不依赖 Redis/Celery 也能启动核心服务。
- 新增后端 `.env`（基于 `.env.example`），保证 LLM（Kimi）可调用；若无密钥则给出明确降级提示。
- 在 `backend/app/main.py` 中补齐前端已调用但后端缺失的接口（底层 service 与 DB 方法均已存在，仅需接线）：
  - `POST /api/v1/analysis/deep`（深度分析，复用 `DeepAnalysisService`）
  - `POST /api/v1/atoms/generate`（从简历生成经历原子，复用 `AtomGenerator`）
  - `POST /api/v1/atoms`（手动创建经历原子，兼容前端的 FormData 与 JSON 两种提交方式）
  - `DELETE /api/v1/atoms/{atom_id}`（删除经历原子）
  - `GET /api/v1/resumes/{resume_id}`（按 ID 获取简历，供校招评分流程取数）
- 确认并保证核心端到端闭环（上传简历 → 粘贴 JD → 流式匹配 → 查看结果/优化建议/历史）在本地真实跑通。
- 同步核对 `start.sh`、端口（后端 8888 / 前端 3000）、文档与真实实现一致。

不做（避免过度工程，超出参赛"能跑通能演示"目标）：
- 不引入或恢复废弃的 Next.js 前端。
- 不强制部署 Redis/Celery/Prometheus（保持可选，缺失时优雅降级）。
- 不重写已有匹配/解析引擎。

## Impact
- Affected specs: 简历解析、JD 解析、匹配分析、简历优化、经历原子库、深度分析、校招评分、历史记录、一键启动。
- Affected code:
  - `start.sh`
  - `backend/.env`（新增，从 `.env.example` 派生）
  - `backend/app/main.py`（新增 5 个路由）
  - 复用：`backend/app/services/deep_analysis.py`、`backend/app/services/atom_generator.py`、`backend/app/db/sqlite_db.py`
  - `frontend/index.html`（仅在确有 bug 时做最小修复，不重构）

## ADDED Requirements

### Requirement: 一键启动可用
系统 SHALL 提供可在当前仓库目录直接运行的 `start.sh`，无需手工改路径即可启动前后端。

#### Scenario: 全新环境一键启动
- **WHEN** 用户在仓库根目录执行 `./start.sh start`
- **THEN** 脚本基于自身所在目录定位 `backend/` 与 `frontend/`，准备好 Python 依赖，在 8888 启动后端、3000 启动前端，并打印可访问地址

#### Scenario: 缺少 LLM 密钥时的明确提示
- **WHEN** 后端启动时未配置可用的 LLM 密钥
- **THEN** 服务仍能启动，且在调用匹配/解析接口时返回可读的错误提示，而非静默失败

### Requirement: 深度分析接口
系统 SHALL 提供 `POST /api/v1/analysis/deep`，对指定简历与岗位执行 JD 逐句拆解分析。

#### Scenario: 深度分析成功
- **WHEN** 前端以 `resume_id` 与 `job_id`（FormData）请求该接口
- **THEN** 后端复用 `DeepAnalysisService` 返回 `{success, data}`，`data` 含 `sentence_analysis` / `diff_table` / `verb_analysis` 等字段供前端渲染

### Requirement: 经历原子库管理接口
系统 SHALL 提供经历原子的生成、创建与删除接口，使前端原子库页面功能可用。

#### Scenario: 从简历生成原子
- **WHEN** 前端以 `resume_id`（FormData）请求 `POST /api/v1/atoms/generate`
- **THEN** 后端复用 `AtomGenerator` 从简历生成原子并入库，返回 `{success, data:[...]}`

#### Scenario: 手动创建原子（兼容两种提交格式）
- **WHEN** 前端以 FormData 或 JSON 提交 `POST /api/v1/atoms`
- **THEN** 后端均能正确解析字段（title/atom_type/description/company/skills）并入库返回新建记录

#### Scenario: 删除原子
- **WHEN** 前端请求 `DELETE /api/v1/atoms/{atom_id}`
- **THEN** 后端删除对应原子并返回成功状态

### Requirement: 按 ID 获取简历
系统 SHALL 提供 `GET /api/v1/resumes/{resume_id}`，返回指定简历数据。

#### Scenario: 校招评分取数
- **WHEN** 前端在校招评分流程中按 `resume_id` 拉取简历
- **THEN** 后端返回该简历完整数据；不存在时返回 404
