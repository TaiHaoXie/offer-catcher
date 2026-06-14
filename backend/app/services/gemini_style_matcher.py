"""
Gemini 风格的流式匹配引擎
模拟真实 HR 思考过程，逐字流式输出，专业结构化分析
"""
import asyncio
import json
from typing import Dict, List, Generator


class GeminiStyleMatcher:
    """Gemini 风格的简历匹配分析器"""

    # 思考停顿延迟（毫秒）
    THINKING_PAUSES = {
        "short": 50,
        "medium": 150,
        "long": 300,
        "thinking": 500
    }

    async def _sleep(self, duration: int):
        """异步延迟"""
        await asyncio.sleep(duration / 1000)

    async def _yield_thinking(self, message: str = "") -> Generator:
        """输出思考状态"""
        yield 'event: thinking\ndata: ' + json.dumps({"message": message}, ensure_ascii=False) + '\n\n'

    async def _stream_text(self, text: str, chunk_size: int = 3) -> Generator:
        """逐字流式输出文本"""
        for i in range(0, len(text), chunk_size):
            chunk = text[i:i + chunk_size]
            yield 'event: content\ndata: ' + json.dumps({"text": chunk}, ensure_ascii=False) + '\n\n'
            await self._sleep(self.THINKING_PAUSES["short"])

    async def _analyze_section(self, title: str, emoji: str = "📋") -> Generator:
        """输出分析章节标题"""
        yield 'event: section\ndata: ' + json.dumps({"title": title, "emoji": emoji}, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["medium"])

    async def match_analysis_stream(self, resume: Dict, job: Dict) -> Generator:
        """流式匹配分析主函数"""

        # ========== 开始分析 ==========
        yield 'event: start\ndata: ' + json.dumps({
            "message": "正在分析简历匹配度...",
            "total_steps": 5
        }, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["thinking"])

        # ========== 第一部分：候选人概览 ==========
        async for event in self._section_candidate_overview(resume):
            yield event

        await self._sleep(self.THINKING_PAUSES["thinking"])

        # ========== 第二部分：岗位需求拆解 ==========
        async for event in self._section_job_requirements(job):
            yield event

        await self._sleep(self.THINKING_PAUSES["thinking"])

        # ========== 第三部分：技能匹配深度分析 ==========
        async for event in self._section_skill_analysis(resume, job):
            yield event

        await self._sleep(self.THINKING_PAUSES["thinking"])

        # ========== 第四部分：经验相关性评估 ==========
        async for event in self._section_experience_analysis(resume, job):
            yield event

        await self._sleep(self.THINKING_PAUSES["thinking"])

        # ========== 第五部分：综合匹配结论 ==========
        async for event in self._section_final_verdict(resume, job):
            yield event

        # ========== 分析完成 ==========
        yield 'event: complete\ndata: ' + json.dumps({
            "message": "分析完成"
        }, ensure_ascii=False) + '\n\n'

    async def _section_candidate_overview(self, resume: Dict) -> Generator:
        """候选人概览分析"""
        async for event in self._analyze_section("候选人画像", ""):
            yield event

        basic_info = resume.get("basic_info", {})
        education = resume.get("education", {})
        experience = resume.get("experience", [])

        # 思考过程
        thinking = ["正在读取候选人背景...", "分析教育经历...", "梳理工作轨迹..."]
        for thought in thinking:
            yield 'event: thinking\ndata: ' + json.dumps({"message": thought}, ensure_ascii=False) + '\n\n'
            await self._sleep(self.THINKING_PAUSES["long"])

        # 输出候选人信息
        name = basic_info.get("name", "未知")
        school = education.get("school", "未知")
        degree = education.get("degree", "未知")
        major = education.get("major", "未知")

        overview_text = f"{name}，{school}{degree}毕业，专业是{major}。"
        async for event in self._stream_text(overview_text):
            yield event

        # 工作经历分析
        if experience:
            await self._sleep(self.THINKING_PAUSES["medium"])
            exp_text = f"\n\n工作经历方面，"
            async for event in self._stream_text(exp_text):
                yield event

            for i, exp in enumerate(experience):
                company = exp.get("company", "某公司")
                position = exp.get("position", "某岗位")
                duration = exp.get("duration", "")

                if i > 0:
                    async for event in self._stream_text("，"):
                        yield event
                    await self._sleep(self.THINKING_PAUSES["short"])

                exp_detail = f"曾在{company}担任{position}"
                if duration:
                    exp_detail += f"（{duration}）"
                async for event in self._stream_text(exp_detail):
                    yield event

            async for event in self._stream_text("。"):
                yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

    async def _section_job_requirements(self, job: Dict) -> Generator:
        """岗位需求拆解"""
        async for event in self._analyze_section("岗位需求拆解", ""):
            yield event

        yield 'event: thinking\ndata: ' + json.dumps({"message": "正在拆解岗位核心要求..."}, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["thinking"])

        position = job.get("position_name", "该岗位")
        company = job.get("company", "某公司")
        requirements = job.get("requirements", {})

        # 岗位描述
        job_text = f"这个岗位是{company}的{position}。"
        async for event in self._stream_text(job_text):
            yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

        # 核心要求
        hard_skills = requirements.get("hard_skills", [])
        soft_skills = requirements.get("soft_skills", [])

        if hard_skills:
            async for event in self._stream_text("\n\n硬性技能要求包括："):
                yield event
            for skill in hard_skills:
                await self._sleep(self.THINKING_PAUSES["short"])
                async for event in self._stream_text(f" {skill}"):
                    yield event
                if skill != hard_skills[-1]:
                    async for event in self._stream_text("、"):
                        yield event

        # 软技能
        if soft_skills:
            await self._sleep(self.THINKING_PAUSES["medium"])
            async for event in self._stream_text("\n\n软技能方面，需要："):
                yield event
            for skill in soft_skills:
                await self._sleep(self.THINKING_PAUSES["short"])
                async for event in self._stream_text(f" {skill}"):
                    yield event
                if skill != soft_skills[-1]:
                    async for event in self._stream_text("、"):
                        yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

    async def _section_skill_analysis(self, resume: Dict, job: Dict) -> Generator:
        """技能匹配深度分析"""
        async for event in self._analyze_section("技能匹配分析", ""):
            yield event

        yield 'event: thinking\ndata: ' + json.dumps({"message": "正在逐项核对技能匹配度..."}, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["thinking"])

        resume_skills = resume.get("skills", [])
        job_requirements = job.get("requirements", {})
        required_skills = job_requirements.get("hard_skills", [])

        matched = []
        missing = []

        for req_skill in required_skills:
            req_lower = req_skill.lower()
            found = False
            for resume_skill in resume_skills:
                if req_lower in resume_skill.lower() or resume_skill.lower() in req_lower:
                    matched.append(req_skill)
                    found = True
                    break
            if not found:
                missing.append(req_skill)

        # 输出匹配分析
        if matched:
            async for event in self._stream_text("\n技能匹配情况："):
                yield event

            for skill in matched:
                await self._sleep(self.THINKING_PAUSES["medium"])
                yield 'event: thinking\ndata: ' + json.dumps({"message": f"核对 {skill}..."}, ensure_ascii=False) + '\n\n'
                await self._sleep(self.THINKING_PAUSES["long"])
                async for event in self._stream_text(f"\n  • {skill} — 简历中有相关经验"):
                    yield event

        if missing:
            await self._sleep(self.THINKING_PAUSES["medium"])
            async for event in self._stream_text("\n\n技能缺口："):
                yield event

            for skill in missing:
                await self._sleep(self.THINKING_PAUSES["medium"])
                yield 'event: thinking\ndata: ' + json.dumps({"message": f"评估 {skill} 的重要性..."}, ensure_ascii=False) + '\n\n'
                await self._sleep(self.THINKING_PAUSES["long"])
                async for event in self._stream_text(f"\n  • {skill} — 简历中未直接提及"):
                    yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

    async def _section_experience_analysis(self, resume: Dict, job: Dict) -> Generator:
        """经验相关性评估"""
        async for event in self._analyze_section("经验相关性评估", ""):
            yield event

        yield 'event: thinking\ndata: ' + json.dumps({"message": "正在分析工作经历与岗位的相关性..."}, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["thinking"])

        experience = resume.get("experience", [])
        projects = resume.get("projects", [])

        if not experience:
            async for event in self._stream_text("\n候选人暂无工作经历记录。"):
                yield event
        else:
            async for event in self._stream_text("\n从工作经历来看，"):
                yield event

            for exp in experience:
                await self._sleep(self.THINKING_PAUSES["long"])
                company = exp.get("company", "")
                async for event in self._stream_text(f"\n  • {company}"):
                    yield event

        # 项目经验
        if projects:
            await self._sleep(self.THINKING_PAUSES["medium"])
            async for event in self._stream_text("\n\n项目经验方面，"):
                yield event

            for i, proj in enumerate(projects[:3]):
                await self._sleep(self.THINKING_PAUSES["long"])
                name = proj.get("name", "")
                role = proj.get("role", "")

                proj_desc = f"\n  • {name}"
                if role:
                    proj_desc += f"（{role}）"

                async for event in self._stream_text(proj_desc):
                    yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

    async def _section_final_verdict(self, resume: Dict, job: Dict) -> Generator:
        """综合匹配结论"""
        async for event in self._analyze_section("综合评估结论", ""):
            yield event

        yield 'event: thinking\ndata: ' + json.dumps({"message": "正在整合分析结果，给出综合评估..."}, ensure_ascii=False) + '\n\n'
        await self._sleep(self.THINKING_PAUSES["thinking"])

        # 计算匹配度
        resume_skills = resume.get("skills", [])
        job_requirements = job.get("requirements", {})
        required_skills = job_requirements.get("hard_skills", [])

        matched_count = 0
        for req_skill in required_skills:
            req_lower = req_skill.lower()
            for resume_skill in resume_skills:
                if req_lower in resume_skill.lower() or resume_skill.lower() in req_lower:
                    matched_count += 1
                    break

        total_required = len(required_skills) if required_skills else 1
        match_rate = int((matched_count / total_required) * 100) if total_required > 0 else 50

        # 经验加分
        experience = resume.get("experience", [])
        projects = resume.get("projects", [])

        # 项目经验丰富度
        project_bonus = min(len(projects) * 5, 20)  # 最多加20分

        # 综合评分
        final_score = min(match_rate + project_bonus, 95)

        # 评级
        if final_score >= 85:
            grade = "A"
            grade_desc = "强烈推荐面试"
        elif final_score >= 70:
            grade = "B"
            grade_desc = "值得进一步沟通"
        elif final_score >= 50:
            grade = "C"
            grade_desc = "可考虑作为备选"
        else:
            grade = "D"
            grade_desc = "匹配度较低"

        # 流式输出结论
        async for event in self._stream_text("\n基于以上分析，"):
            yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

        async for event in self._stream_text(f"我给出的综合评分是 {final_score}分"):
            yield event

        await self._sleep(self.THINKING_PAUSES["long"])

        async for event in self._stream_text(f"，评级为 {grade}（{grade_desc}）。"):
            yield event

        await self._sleep(self.THINKING_PAUSES["long"])

        # 详细建议
        async for event in self._stream_text("\n\n我的建议是："):
            yield event

        await self._sleep(self.THINKING_PAUSES["thinking"])

        if final_score >= 70:
            suggestion = "该候选人的技能和经验与岗位要求较为匹配，建议安排技术面试进一步沟通。"
        elif final_score >= 50:
            suggestion = "该候选人有一定基础，但存在技能缺口，可以先进行电话沟通了解实际情况。"
        else:
            suggestion = "该候选人与岗位匹配度不高，建议继续寻找更合适的人选。"

        async for event in self._stream_text(suggestion):
            yield event

        await self._sleep(self.THINKING_PAUSES["medium"])

        # 输出结构化数据（给前端使用）
        yield 'event: result\ndata: ' + json.dumps({
            "score": final_score,
            "grade": grade,
            "grade_description": grade_desc,
            "matched_skills": matched_count,
            "total_required": total_required,
            "skill_match_rate": match_rate,
            "experience_count": len(experience),
            "project_count": len(projects)
        }, ensure_ascii=False) + '\n\n'

        await self._sleep(self.THINKING_PAUSES["medium"])
