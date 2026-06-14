# Tasks

- [x] Task 1: 安全与后端可靠性修复（P0）
  - [x] SubTask 1.1: 将 `backend/.env.example` 第 20 行的真实 Kimi 密钥替换为占位符 `your_kimi_api_key_here`
  - [x] SubTask 1.2: 移除 `docs/项目交接文档.md` 中明文的真实 Kimi 密钥，改为占位说明
  - [x] SubTask 1.3: 在 `backend/app/main.py` 顶部补 `import io`，修复 DOCX 上传 NameError
  - [x] SubTask 1.4: 在 `one_shot_match_engine.py` 的 `analyze_stream` except 分支接入降级兜底（复用已有 `fallback_result` 逻辑或构造基础结果并经 `_normalize_recruiter_report` 规范化后 yield result + done），保证 LLM 失败仍有可渲染结果
  - [x] SubTask 1.5: 将 `main.py` `__main__` 中写死的 8000 端口统一为 8888

- [x] Task 2: 前端功能修复（P0/P1）
  - [x] SubTask 2.1: 修复 `createAtomFromMatchResult`：去掉 `!state.jobData` 拦截，岗位信息改从 `state.lastMatchResult`/`#jd-input` 推导
  - [x] SubTask 2.2: 消除"一键优化"与"沉淀原子"按钮双触发（移除内联 onclick 或 addEventListener，二选一保留）
  - [x] SubTask 2.3: `showMatchError` 对 429/限流/overloaded 关键字给出"接口繁忙，请稍后重试"的友好中文文案，不透传英文原始报错

- [x] Task 3: 岗位推荐能力 MVP（P1，核心加分）
  - [x] SubTask 3.1: 新增 `backend/data/job_pool.json`，内置 8-12 条覆盖常见学生求职方向的岗位（含 position_name/company/jd_text 等字段）
  - [x] SubTask 3.2: 新增 `backend/app/services/job_recommender.py`，输入简历数据，复用现有规则匹配/校招评分引擎对岗位池批量打分，返回 Top-N（含分数与匹配理由）
  - [x] SubTask 3.3: 在 `main.py` 新增 `POST /api/v1/jobs/recommend`（入参 resume_id 或 resume 数据），调用 recommender 返回排序结果
  - [x] SubTask 3.4: 前端 `index.html` 新增「岗位推荐」标签页与渲染逻辑：展示推荐岗位卡片（岗位/公司/匹配度/理由），并提供"去分析"按钮把该岗位 JD 带入匹配工作台

- [x] Task 4: 端到端验证
  - [x] SubTask 4.1: 重启后端，验证 DOCX 上传不再 500、岗位推荐接口返回排序结果
  - [x] SubTask 4.2: 浏览器验证：沉淀原子成功且只插一条、按钮无双触发、岗位推荐 tab 可用并能带 JD 进工作台、LLM 失败时有降级结果

# Task Dependencies
- Task 4 depends on Task 1, Task 2, Task 3
- Task 2.1/2.2 相互独立，可并行
