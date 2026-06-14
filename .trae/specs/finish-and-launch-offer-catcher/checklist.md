# Checklist

- [x] `start.sh` 不含 `/Users/xulindi/Desktop/...` 等硬编码路径，基于脚本所在目录定位前后端
- [x] `./start.sh start` 可在仓库根目录直接运行，自动准备 venv / 依赖 / `.env`
- [x] 后端在 8888、前端在 3000 启动，`http://localhost:8888/` 健康检查返回 running
- [x] `POST /api/v1/analysis/deep` 接口存在，返回含 sentence_analysis/diff_table/verb_analysis 的结果
- [x] `POST /api/v1/atoms/generate` 接口存在，可从简历生成原子并入库
- [x] `POST /api/v1/atoms` 接口存在，兼容 FormData 与 JSON 两种提交
- [x] `DELETE /api/v1/atoms/{atom_id}` 接口存在，可删除原子
- [x] `GET /api/v1/resumes/{resume_id}` 接口存在，命中返回数据，未命中返回 404
- [x] 核心闭环（JD + 简历 → 流式匹配出结果）本地真实跑通
- [x] 未引入废弃 Next.js 前端，未强制依赖 Redis/Celery 即可启动核心服务
- [x] 前端原子库页面的生成/创建/删除按钮可正常工作（不再静默报错）
