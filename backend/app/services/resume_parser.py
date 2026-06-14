"""
Offer 捕手 - 简历解析服务
"""
import os
from typing import Dict, Optional
from pathlib import Path


class ResumeParser:
    """简历解析器"""

    def __init__(self, llm_client):
        """初始化解析器"""
        self.llm_client = llm_client

    def extract_text(self, file_path: str) -> str:
        """从文件中提取文本"""
        file_path = Path(file_path)

        if not file_path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        if file_path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(file_path)
        elif file_path.suffix.lower() in [".docx", ".doc"]:
            return self._extract_docx_text(file_path)
        elif file_path.suffix.lower() == ".txt":
            return self._extract_txt_text(file_path)
        else:
            raise ValueError(f"不支持的文件格式: {file_path.suffix}")

    def _extract_pdf_text(self, file_path: Path) -> str:
        """提取PDF文本"""
        try:
            import PyPDF2
            text = ""
            with open(file_path, "rb") as file:
                reader = PyPDF2.PdfReader(file)
                for page in reader.pages:
                    text += page.extract_text() + "\n"
            return text.strip()
        except ImportError:
            # 备用方案：pdfplumber
            try:
                import pdfplumber
                text = ""
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        text += page.extract_text() + "\n"
                return text.strip()
            except ImportError:
                raise ImportError("请安装 PyPDF2 或 pdfplumber: pip install PyPDF2 pdfplumber")

    def _extract_docx_text(self, file_path: Path) -> str:
        """提取Word文本"""
        try:
            from docx import Document
            doc = Document(file_path)
            text = ""
            for paragraph in doc.paragraphs:
                text += paragraph.text + "\n"
            return text.strip()
        except ImportError:
            raise ImportError("请安装 python-docx: pip install python-docx")

    def _extract_txt_text(self, file_path: Path) -> str:
        """提取TXT文本"""
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()

    def parse(self, file_path: str) -> Dict:
        """解析简历文件并返回结构化数据"""
        # 1. 提取文本
        text = self.extract_text(file_path)

        if not text or len(text) < 50:
            raise ValueError("文件内容为空或过少，请检查文件格式")

        # 2. 调用LLM解析
        result = self.llm_client.resume_parse(text)

        return result

    def parse_from_text(self, text: str) -> Dict:
        """直接从文本解析简历"""
        if not text or len(text) < 50:
            raise ValueError("文本内容过少，无法解析")

        return self.llm_client.resume_parse(text)
