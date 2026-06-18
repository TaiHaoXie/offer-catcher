"""两份简历端到端烟测。

覆盖：登录 -> 匹配 SSE -> 定制简历 -> 后端 PDF 下载 -> PDF 文本/页数/乱码检查。
会调用线上 LLM 接口，非日常单测；需要本地 8888 服务已启动。
"""
import json
import re
from pathlib import Path

import fitz
import requests


BASE_URL = "http://localhost:8888"
OUT_DIR = Path("/tmp/offer-catcher-e2e")
OUT_DIR.mkdir(parents=True, exist_ok=True)


LONG_RESUME = """赵振华
手机号：13800138000
邮箱：zhaozhenhua@example.com
所在地：北京
求职意向：后端开发工程师 / Java 后端实习生

个人介绍
计算机科学与技术专业硕士，具备扎实的 Java 后端开发、数据库设计、缓存与消息队列使用经验。熟悉 Spring Boot、MyBatis、MySQL、Redis、Kafka 等技术栈，理解接口设计、服务拆分、性能优化和稳定性建设方法。

核心技能
Java、Spring Boot、MyBatis、MySQL、Redis、Kafka、Docker、Linux、Git、RESTful API、SQL 优化、接口设计、系统稳定性

教育经历
2018 - 2022 华南理工大学 软件工程 本科
2022 - 2025 北京邮电大学 计算机科学与技术 硕士

项目经历一：Offer 捕手智能求职匹配系统
项目时间：2024.03 - 2024.08
项目角色：后端开发负责人
项目描述：面向学生求职场景，系统支持简历解析、岗位 JD 解析、匹配度计算、优化建议生成和历史记录管理。
工作内容：
1. 使用 FastAPI 实现简历上传、JD 解析、匹配分析、优化建议和历史记录查询等接口。
2. 设计 SQLite 数据表结构，拆分简历、岗位、匹配记录、经历原子等数据模型。
3. 接入大模型能力完成简历与 JD 的匹配分析，并在接口层增加异常处理。
4. 优化简历匹配链路，确保每次匹配只使用当前上传或粘贴的简历内容。
5. 增加 PDF 导出能力，处理长简历分页、中文渲染和内容截断问题。

项目经历二：校园二手交易平台
项目时间：2023.09 - 2024.01
项目角色：后端开发
工作内容：
1. 使用 Spring Boot 和 MyBatis 完成商品发布、商品搜索、订单创建、订单取消和用户收藏等核心接口。
2. 设计商品表、订单表、用户表、收藏表和消息表，使用索引优化商品关键词检索和用户订单查询。
3. 使用 Redis 缓存热门商品列表和商品详情页，减少数据库重复查询压力。
4. 增加基础参数校验和统一异常返回，避免空字段、非法价格、重复提交导致异常。
5. 参与接口联调和性能测试，针对商品列表接口进行分页优化。

项目经历三：实验室设备预约系统
项目时间：2023.03 - 2023.07
项目角色：后端开发
工作内容：
1. 负责预约规则设计，支持用户按日期、时间段和设备类型提交预约申请。
2. 实现预约冲突检测逻辑，避免同一设备在同一时间段被重复预约。
3. 使用 MySQL 设计设备、预约、审批、用户和使用记录表，并通过事务保证审批状态一致。
4. 增加管理员审批接口，支持通过、驳回和备注说明。

实习经历一：北京云启科技有限公司 后端开发实习生
实习时间：2024.06 - 2024.09
工作内容：
1. 参与企业内部数据看板系统开发，负责用户权限、数据查询和报表导出相关接口。
2. 使用 Spring Boot 开发部门维度、日期维度和业务线维度的数据聚合接口。
3. 编写复杂 SQL 完成多表关联查询，并通过增加索引和调整查询条件优化慢查询。
4. 配合前端完成图表接口联调，统一处理空数据、异常数据和时间范围筛选逻辑。
5. 使用 Redis 缓存部分高频统计结果，降低重复查询对数据库的压力。

实习经历二：杭州星河智能科技有限公司 Java 开发实习生
实习时间：2023.07 - 2023.10
工作内容：
1. 参与客户管理系统迭代，负责客户信息维护、跟进记录、标签管理和导入导出功能。
2. 使用 MyBatis 完成客户列表多条件筛选，包括关键词、标签、负责人和创建时间筛选。
3. 修复 Excel 导入中重复数据、空字段和格式错误导致的异常问题。
4. 增加操作日志记录，帮助业务人员追踪客户资料修改历史。

兴趣爱好
喜欢阅读技术博客和工程实践文章，长期关注后端架构、AI 工具和效率产品。业余时间喜欢跑步和羽毛球。
"""


SHORT_RESUME = """李明
手机号：13900139000
邮箱：liming@example.com
所在地：广州
求职意向：产品经理实习生

个人介绍
信息管理与信息系统本科在读，做过校园社团小程序和课程调研项目，熟悉需求访谈、问卷分析、原型设计和基础 SQL 数据分析。

核心技能
Axure、墨刀、Excel、SQL、问卷设计、竞品分析、需求文档、用户访谈

教育经历
2021 - 2025 华南师范大学 信息管理与信息系统 本科

项目经历：校园活动报名小程序
项目时间：2024.03 - 2024.06
项目角色：产品负责人
工作内容：
1. 访谈 12 名学生和 3 名社团负责人，梳理活动发布、报名、签到和通知提醒流程。
2. 使用墨刀完成 18 个核心页面原型，覆盖活动列表、详情页、报名表单和后台审核页。
3. 整理 PRD 文档并与两名前端同学、一名后端同学完成接口字段确认。
4. 上线后收集 46 份问卷反馈，整理出报名信息重复填写和通知触达不及时两个主要问题。

实习经历：广州青禾教育科技有限公司 产品运营实习生
实习时间：2024.07 - 2024.09
工作内容：
1. 负责学习打卡活动的数据统计，每周用 Excel 汇总报名人数、完课人数和留存情况。
2. 协助产品经理整理用户反馈，将高频问题归类为课程内容、提醒机制和页面操作三类。
3. 参与一次版本评审，补充用户反馈样例和数据截图，帮助团队确认优化优先级。

兴趣爱好
喜欢体验效率工具和教育产品，平时会整理产品拆解笔记，也喜欢摄影和羽毛球。
"""


BACKEND_JD = """后端开发工程师实习生
岗位职责：
1. 参与核心业务后端系统的设计、开发和维护，保障系统稳定性和可扩展性。
2. 负责业务接口开发、数据库设计、缓存设计和性能优化。
3. 参与服务端问题排查，定位接口异常、慢查询和线上稳定性问题。
4. 与产品、前端、测试协作，完成需求评审、接口联调和上线验证。

任职要求：
1. 本科及以上学历，计算机、软件工程、信息管理等相关专业优先。
2. 熟悉 Java 语言，了解 Spring Boot、MyBatis 等常用后端框架。
3. 熟悉 MySQL，理解索引、事务、分页查询和常见 SQL 优化方式。
4. 了解 Redis、Kafka 或其他缓存、消息队列组件者优先。
5. 有完整后端项目经历或互联网实习经历优先。
"""


PRODUCT_JD = """产品经理实习生
岗位职责：
1. 参与用户调研、需求分析、竞品分析和产品方案设计。
2. 输出产品原型、PRD 文档和流程图，推动设计、研发、测试协作落地。
3. 跟踪产品上线后的数据表现和用户反馈，提出优化建议。
4. 支持教育或效率工具方向的功能迭代。

任职要求：
1. 本科及以上学历，专业不限，信息管理、计算机、心理学、教育相关背景优先。
2. 熟悉 Axure、墨刀、Figma 等原型工具之一。
3. 具备基础数据分析能力，能使用 Excel 或 SQL 做简单统计。
4. 有产品项目、用户调研、产品运营或互联网实习经历优先。
"""


def login() -> str:
    resp = requests.post(
        f"{BASE_URL}/api/v1/auth/login",
        json={"phone": "18303891187", "code": "WASD"},
        timeout=20,
    )
    resp.raise_for_status()
    return resp.json()["token"]


def parse_sse_result(text: str) -> dict:
    event = None
    data_lines = []
    result = None
    errors = []
    for raw in text.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("event:"):
            event = line.split(":", 1)[1].strip()
            data_lines = []
        elif line.startswith("data:"):
            data_lines.append(line.split(":", 1)[1].strip())
        elif line == "" and event and data_lines:
            payload = json.loads("\n".join(data_lines))
            if event == "result":
                result = payload
            elif event == "error":
                errors.append(payload)
            event = None
            data_lines = []
    if errors:
        raise AssertionError(f"SSE error: {errors[-1]}")
    if not result:
        raise AssertionError("SSE 未返回 result 事件")
    return result


def run_match(token: str, name: str, resume_text: str, jd_text: str) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/match/from-upload/stream",
        headers={"Authorization": f"Bearer {token}"},
        data={"jd_text": jd_text},
        files={"resume_file": ("resume.txt", resume_text.encode("utf-8"), "text/plain")},
        timeout=180,
    )
    resp.raise_for_status()
    (OUT_DIR / f"{name}-match.sse").write_text(resp.text, encoding="utf-8")
    result = parse_sse_result(resp.text)
    (OUT_DIR / f"{name}-match.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def run_customize(name: str, resume_text: str, jd_text: str, match_result: dict) -> dict:
    resp = requests.post(
        f"{BASE_URL}/api/v1/resume/customize",
        json={
            "resume_text": resume_text,
            "jd_text": jd_text,
            "match_result": match_result,
            "atoms": [],
        },
        timeout=180,
    )
    resp.raise_for_status()
    body = resp.json()
    assert body.get("success") is True, body
    payload = body["data"]
    (OUT_DIR / f"{name}-customize.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def export_pdf(name: str, payload: dict) -> tuple[int, int, str]:
    resp = requests.post(f"{BASE_URL}/api/v1/resume/export-pdf", json={"resume": payload}, timeout=60)
    resp.raise_for_status()
    pdf_bytes = resp.content
    assert pdf_bytes.startswith(b"%PDF-"), "导出不是 PDF"
    pdf_path = OUT_DIR / f"{name}-定制简历.pdf"
    pdf_path.write_bytes(pdf_bytes)
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    text = "\n".join(page.get_text() for page in doc)
    page_count = doc.page_count
    doc.close()
    assert not any(bad in text for bad in ["J a v a", "S p r i n g", "M y B a t i s", "燧"]), "PDF 存在字体乱码"
    assert "兴趣爱好" in text or "Interests" in text, "PDF 缺少兴趣爱好段"
    return page_count, len(pdf_bytes), text


def assert_no_cross_person(case_name: str, text: str, must_have: str, forbidden: str) -> None:
    normalized = re.sub(r"\s+", "", text)
    assert must_have in normalized, f"{case_name} 缺少当前候选人姓名 {must_have}"
    assert forbidden not in normalized, f"{case_name} 串入另一个候选人 {forbidden}"


def run_case(token: str, case_name: str, resume_text: str, jd_text: str, must_have: str, forbidden: str) -> dict:
    match_result = run_match(token, case_name, resume_text, jd_text)
    payload = run_customize(case_name, resume_text, jd_text, match_result)
    all_json = json.dumps(payload, ensure_ascii=False)
    assert_no_cross_person(case_name, all_json, must_have, forbidden)
    pages, size, pdf_text = export_pdf(case_name, payload)
    assert_no_cross_person(case_name + " PDF", pdf_text, must_have, forbidden)
    return {
        "case": case_name,
        "score": match_result.get("match_score") or match_result.get("score") or match_result.get("report_executive_summary", {}).get("match_score"),
        "level": match_result.get("match_level") or match_result.get("level") or match_result.get("report_executive_summary", {}).get("match_level"),
        "engine": payload.get("engine"),
        "candidate": payload.get("basic_info", {}).get("name"),
        "pdf_pages": pages,
        "pdf_bytes": size,
        "blocks": len(payload.get("selected_atoms") or []),
        "skills": payload.get("skills_line") or [],
    }


def main() -> None:
    token = login()
    results = [
        run_case(token, "long-backend", LONG_RESUME, BACKEND_JD, "赵振华", "李明"),
        run_case(token, "short-product", SHORT_RESUME, PRODUCT_JD, "李明", "赵振华"),
    ]
    summary_path = OUT_DIR / "summary.json"
    summary_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"out_dir": str(OUT_DIR), "results": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
