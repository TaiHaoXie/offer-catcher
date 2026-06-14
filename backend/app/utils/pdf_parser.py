"""
快速 PDF 解析器

优化策略：
1. 优先使用 PyMuPDF (fitz) - 速度快 5-10 倍
2. 限制提取页数（简历通常只有 1-2 页）
3. 去除空白字符优化

作者：Claude
创建日期：2026-06-01
"""

import io
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class FastPDFParser:
    """快速 PDF 解析器"""

    def __init__(self, max_pages: int = 3):
        """
        Args:
            max_pages: 最大提取页数（简历通常不需要太多页）
        """
        self.max_pages = max_pages

    def extract_text(self, content: bytes, filename: str = "") -> str:
        """
        从 PDF 内容提取文本

        策略：优先 PyMuPDF（快）。若结果为空/过短/疑似乱码，自动回退 pdfplumber 再试一次，
        取两者中更可信的结果，尽量避免“解析半吊子”。

        Args:
            content: PDF 文件二进制内容
            filename: 文件名（用于日志）

        Returns:
            str: 提取的文本内容
        """
        fitz_text = ""
        try:
            fitz_text = self._extract_with_fitz(content)
        except ImportError:
            logger.warning("PyMuPDF 未安装，使用 pdfplumber")
        except Exception as e:
            logger.warning(f"PyMuPDF 解析失败: {e}")

        # fitz 结果可信，直接用
        if len(fitz_text) >= 80 and not self._looks_garbled(fitz_text):
            return fitz_text

        # 否则回退 pdfplumber 再试一次
        plumber_text = ""
        try:
            plumber_text = self._extract_with_pdfplumber(content)
        except Exception as e:
            logger.warning(f"pdfplumber 解析失败: {e}")

        # 取更长且不乱码的结果
        candidates = [t for t in (fitz_text, plumber_text) if t and not self._looks_garbled(t)]
        if candidates:
            return max(candidates, key=len)
        # 都不理想时，返回较长的原始结果（让上层根据字数判断是否提示用户改粘贴）
        return max([fitz_text, plumber_text], key=len) if (fitz_text or plumber_text) else ""

    @staticmethod
    def _looks_garbled(text: str) -> bool:
        """粗略判断文本是否疑似乱码：可见字符（中文/字母/数字/常见标点）占比过低。"""
        if not text:
            return False
        import re
        meaningful = re.findall(r"[\u4e00-\u9fff0-9A-Za-z]", text)
        ratio = len(meaningful) / max(len(text), 1)
        # 正常简历该比例通常 > 0.5；过低多为乱码/编码异常
        return ratio < 0.25

    def _extract_with_fitz(self, content: bytes) -> str:
        """使用 PyMuPDF 提取文本（最快）"""
        try:
            import fitz
        except ImportError:
            raise ImportError("请安装 PyMuPDF: pip install PyMuPDF")

        doc = fitz.open(stream=io.BytesIO(content), filetype="pdf")
        text_parts = []

        # 只提取前几页（简历通常 1-2 页）
        for page_num, page in enumerate(doc):
            if page_num >= self.max_pages:
                break

            # 快速提取文本
            page_text = page.get_text()
            if page_text.strip():
                text_parts.append(page_text)

        doc.close()

        # 合并并清理
        full_text = "\n".join(text_parts)
        return self._clean_text(full_text)

    def _extract_with_pdfplumber(self, content: bytes) -> str:
        """使用 pdfplumber 提取文本（较慢但更准确）"""
        try:
            import pdfplumber
        except ImportError:
            raise ImportError("请安装 pdfplumber: pip install pdfplumber")

        pdf_file = io.BytesIO(content)
        text_parts = []

        with pdfplumber.open(pdf_file) as pdf:
            for page_num, page in enumerate(pdf.pages):
                if page_num >= self.max_pages:
                    break

                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)

        full_text = "\n".join(text_parts)
        return self._clean_text(full_text)

    def _clean_text(self, text: str) -> str:
        """清理提取的文本"""
        # 去除多余空白
        lines = []
        for line in text.split("\n"):
            cleaned = line.strip()
            if cleaned:
                lines.append(cleaned)

        return "\n".join(lines)


# 全局实例（单例）
_pdf_parser_instance: Optional[FastPDFParser] = None


def get_pdf_parser() -> FastPDFParser:
    """获取 PDF 解析器实例"""
    global _pdf_parser_instance
    if _pdf_parser_instance is None:
        _pdf_parser_instance = FastPDFParser()
    return _pdf_parser_instance
