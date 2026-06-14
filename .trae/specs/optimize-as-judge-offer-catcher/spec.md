# 评委视角优化「Offer 捕手」Spec

## Why
以参赛评委视角对项目打分（前端 72 / 后端 62 / 赛题契合度 72，综合约 68）后，发现几类直接拉低得分、且会在现场演示翻车的问题：安全事故（明文密钥）、可靠性缺口（LLM 失败无降级、DOCX 上传必崩）、功能失效（"沉淀原子"按钮、按钮双触发）、以及赛题最大短板（痛点1"海量岗位推荐"几乎缺失）。本次按投入产出比优先修复这些问题，把综合分从约 68 拉升到 80+。

## 评委打分（修复前基线）
- 前端体验/质量：72/100
- 后端架构/可靠性：62/100
- 赛题契合度/产品完整度：72/100
- 综合：约 68/100

## What Changes
### A. 安全与可靠性（P0，必做）
- 移除 `backend/.env.example` 与 `docs/项目交接文档.md` 中明文写死的真实 Kimi 密钥，改为占位符（**BREAKING**：需重新配置 `.env`，但 `.env` 不入库，影响可控）。
- 修复 `backend/app/main.py` 缺失 `import io` 导致 DOCX 简历上传必崩（NameError）。
- 给流式匹配接好已写但未接线的降级兜底：LLM 重试仍失败时返回可渲染的基础分析，而非直接报错白屏。

### B. 前端功能修复（P0/P1）
- 修复"沉淀为经历原子"按钮：去掉对永不赋值的 `state.jobData` 的依赖，改用 `state.lastMatchResult` + JD 输入推导岗位信息。
- 消除"一键优化 / 沉淀原子"按钮的双重触发（内联 onclick 与 addEventListener 同时存在，导致重复请求/重复入库）。
- 错误提示区分 429/限流场景，给出"接口繁忙，请稍后重试"的友好中文文案，避免透传英文报错。

### C. 赛题契合度提升（P1，核心加分项）
- 新增"岗位推荐"能力 MVP，直接命中痛点1：
  - 后端提供一个内置岗位池（JSON 种子数据）+ `POST /api/v1/jobs/recommend` 接口：输入简历，复用现有规则匹配引擎对岗位池批量打分并返回 Top-N 排序结果。
  - 前端新增「岗位推荐」标签页：展示推荐岗位列表（岗位名/公司/匹配度/匹配理由），并能一键把某岗位 JD 带入匹配工作台做深度分析，串起痛点1→痛点2闭环。

### D. 收尾（P2，按需）
- 统一端口口径：`main.py` `__main__` 写死的 8000 与实际 8888 不一致，统一为 8888。

不做（避免过度工程）：
- 不做爬虫/实时岗位抓取，岗位池用本地种子数据即可。
- 不批量删除 services/ 死代码（风险高、对评分提升有限），仅在不影响运行的前提下保留。
- 不强制接入 Redis/Celery，保持可选降级。
- 不恢复废弃的 Next.js 前端。

## Impact
- Affected specs: 安全配置、简历解析、流式匹配可靠性、经历原子库、岗位推荐（新增）、前端交互。
- Affected code:
  - `backend/.env.example`、`docs/项目交接文档.md`（密钥占位）
  - `backend/app/main.py`（import io、岗位推荐接口、端口统一）
  - `backend/app/services/one_shot_match_engine.py`（降级兜底接线）
  - `backend/app/services/job_recommender.py`（新增，复用现有匹配/校招引擎）
  - `backend/data/job_pool.json`（新增岗位池种子数据）
  - `frontend/index.html`（沉淀原子修复、双触发修复、错误文案、岗位推荐 tab）

## ADDED Requirements

### Requirement: 凭证安全
仓库中不得包含可用的真实 API 密钥。

#### Scenario: 示例配置不含真实密钥
- **WHEN** 查看 `backend/.env.example` 或 `docs/项目交接文档.md`
- **THEN** 其中的 API Key 字段均为占位符（如 `your_kimi_api_key_here`），不含真实可用密钥

### Requirement: DOCX 简历可解析
系统 SHALL 支持上传 DOCX 简历而不崩溃。

#### Scenario: 上传 DOCX 简历
- **WHEN** 用户向 `/api/v1/resume/parse` 上传 .docx 文件
- **THEN** 后端正常提取文本并解析，不抛 NameError

### Requirement: LLM 失败时优雅降级
流式匹配在 LLM 多次重试仍失败时 SHALL 返回可渲染的基础结果，而非仅报错。

#### Scenario: LLM 持续限流
- **WHEN** 流式匹配的 LLM 调用经重试仍失败
- **THEN** 接口返回一份基础兜底分析结果（result 事件），前端可正常渲染并提示这是降级结果

### Requirement: 沉淀经历原子可用
在匹配结果页点击"沉淀为经历原子" SHALL 成功创建原子。

#### Scenario: 分析完成后沉淀原子
- **WHEN** 用户完成一次匹配分析并点击"沉淀为经历原子"
- **THEN** 系统基于当前匹配结果与 JD 创建一条经历原子，且只创建一条（无双重触发）

### Requirement: 岗位推荐
系统 SHALL 根据简历从内置岗位池推荐匹配度较高的岗位。

#### Scenario: 简历获取推荐岗位
- **WHEN** 用户在「岗位推荐」标签页基于已上传/解析的简历请求推荐
- **THEN** 后端返回 Top-N 岗位（含岗位名、公司、匹配度分数、匹配理由），按匹配度降序

#### Scenario: 从推荐岗位进入匹配分析
- **WHEN** 用户在推荐列表中选择某个岗位"去分析"
- **THEN** 该岗位 JD 被带入匹配工作台，可直接发起招聘官视角匹配分析
