"""
简历解析异步任务

将简历解析放到后台执行，API 立即返回任务 ID
用户可轮询获取结果

作者：Claude
创建日期：2026-06-01
"""

from app.tasks.celery_app import celery_app
from app.services.fast_resume_parser import FastResumeParser
from app.services.xulindi_resume_parser import XulindiResumeParser
from app.db.sqlite_db import get_db
import logging

logger = logging.getLogger(__name__)

# 初始化解析器
resume_parser = FastResumeParser()
xulindi_parser = XulindiResumeParser()


@celery_app.task(name="tasks.parse_resume_text", bind=True, max_retries=3)
def parse_resume_text_task(self, text: str, use_cache: bool = True):
    """
    异步解析简历文本

    Args:
        text: 简历文本内容
        use_cache: 是否使用缓存（Celery 任务本身）

    Returns:
        dict: 解析结果 + resume_id
    """
    try:
        logger.info(f"Async parsing resume from text (task {self.request.id})")

        # 先尝试专用解析器
        try:
            resume_data = xulindi_parser.parse(text)
            if not resume_data.get("basic_info", {}).get("name"):
                raise ValueError("专用解析器未能识别姓名")
        except Exception:
            resume_data = resume_parser.parse_from_text(text)

        # 保存到数据库
        db = get_db()
        resume_id = db.save_resume(resume_data)

        logger.info(f"Resume parsed successfully: {resume_id}")

        return {
            "success": True,
            "resume_id": resume_id,
            "data": {**resume_data, "id": resume_id},
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Resume parsing failed: {e}")
        # 重试机制
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }


@celery_app.task(name="tasks.parse_resume_file", bind=True, max_retries=3)
def parse_resume_file_task(self, file_content: bytes, filename: str):
    """
    异步解析简历文件

    Args:
        file_content: 文件二进制内容
        filename: 文件名

    Returns:
        dict: 解析结果 + resume_id
    """
    try:
        logger.info(f"Async parsing resume file: {filename} (task {self.request.id})")

        text = ""
        # 根据文件类型提取文本
        if filename.lower().endswith('.pdf'):
            try:
                import pdfplumber
                import io

                pdf_file = io.BytesIO(file_content)
                with pdfplumber.open(pdf_file) as pdf:
                    for page in pdf.pages:
                        page_text = page.extract_text()
                        if page_text:
                            text += page_text + "\n"
            except Exception as e:
                # 降级使用 PyMuPDF
                import fitz
                doc = fitz.open(stream=io.BytesIO(file_content), filetype="pdf")
                for page in doc:
                    text += page.get_text()
                doc.close()

        elif filename.lower().endswith('.docx'):
            from docx import Document
            doc = Document(io.BytesIO(file_content))
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"

        else:
            text = file_content.decode('utf-8', errors='ignore')

        text = text.strip()
        if not text:
            raise ValueError("无法从文件中提取文本内容")

        # 解析文本
        try:
            resume_data = xulindi_parser.parse(text)
            if not resume_data.get("basic_info", {}).get("name"):
                raise ValueError("专用解析器未能识别姓名")
        except Exception:
            resume_data = resume_parser.parse_from_text(text)

        # 保存到数据库
        db = get_db()
        resume_id = db.save_resume(resume_data)

        logger.info(f"Resume file parsed successfully: {resume_id}")

        return {
            "success": True,
            "resume_id": resume_id,
            "data": {**resume_data, "id": resume_id},
            "task_id": self.request.id
        }

    except Exception as e:
        logger.error(f"Resume file parsing failed: {e}")
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60)
        return {
            "success": False,
            "error": str(e),
            "task_id": self.request.id
        }
