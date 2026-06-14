"""OCR服务 - 扫描版PDF/图片的兜底解析方案.

支持中英文简历识别，使用PaddleOCR引擎。
"""

import asyncio
import logging
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# PaddleOCR 单例
_paddle_ocr = None
_init_lock = asyncio.Lock()
_ocr_available: Optional[bool] = None


def _check_paddleocr_available() -> bool:
    """检查PaddleOCR是否可用."""
    try:
        import paddleocr
        import paddle
        return True
    except ImportError:
        return False


async def get_ocr_engine():
    """获取PaddleOCR引擎单例（懒加载）。

    Returns:
        PaddleOCR实例

    Raises:
        ImportError: PaddleOCR未安装
        RuntimeError: 初始化失败
    """
    global _paddle_ocr, _ocr_available

    # 首次检查可用性
    if _ocr_available is None:
        _ocr_available = _check_paddleocr_available()
        if not _ocr_available:
            logger.warning("PaddleOCR未安装，OCR功能不可用")
            raise ImportError(
                "PaddleOCR未安装。安装命令：uv add paddleocr paddlepaddle"
            )

    # 快速路径：已初始化
    if _paddle_ocr is not None:
        return _paddle_ocr

    # 使用锁防止重复初始化
    async with _init_lock:
        # 双重检查
        if _paddle_ocr is not None:
            return _paddle_ocr

        # 在线程中初始化（PaddleOCR初始化较慢）
        def init_paddle():
            from paddleocr import PaddleOCR

            logger.info("初始化PaddleOCR引擎...")
            # 使用CPU模式，适合服务器环境
            # det_model_dir=None 使用内置模型
            ocr = PaddleOCR(
                use_angle_cls=True,  # 支持旋转文字
                lang="ch",  # 中文+英文
                use_gpu=False,  # CPU模式
                show_log=False,  # 减少日志噪音
            )
            logger.info("PaddleOCR初始化完成")
            return ocr

        try:
            _paddle_ocr = await asyncio.to_thread(init_paddle)
            return _paddle_ocr
        except Exception as e:
            logger.error(f"PaddleOCR初始化失败：{e}")
            _ocr_available = False
            raise RuntimeError(f"PaddleOCR初始化失败：{e}") from e


async def parse_image_to_text(
    image_path: str | Path,
    min_confidence: float = 0.5
) -> str:
    """使用OCR从图片/PDF页面提取文本。

    Args:
        image_path: 图片文件路径
        min_confidence: 最小置信度阈值

    Returns:
        识别的文本内容
    """
    ocr = await get_ocr_engine()

    def run_ocr():
        result = ocr.ocr(str(image_path), cls=True)
        if not result or not result[0]:
            return ""

        # 提取文本行
        lines = []
        for line in result[0]:
            if line and len(line) >= 2:
                box, (text, confidence) = line
                # 过滤低置信度结果
                if confidence >= min_confidence:
                    lines.append(text)

        return "\n".join(lines)

    try:
        text = await asyncio.to_thread(run_ocr)
        logger.info(f"OCR识别完成：{len(text)}字符，{len(text.splitlines())}行")
        return text
    except Exception as e:
        logger.error(f"OCR识别失败：{e}")
        return ""


async def parse_pdf_to_text(
    pdf_path: str | Path,
    max_pages: int = 10,
    min_confidence: float = 0.5
) -> str:
    """使用OCR从PDF提取文本（扫描版PDF兜底方案）。

    将PDF转换为图片后进行OCR识别。

    Args:
        pdf_path: PDF文件路径
        max_pages: 最大处理页数（默认10页）
        min_confidence: 最小置信度阈值

    Returns:
        识别的文本内容
    """
    # 将PDF转换为图片
    images = await _convert_pdf_to_images(pdf_path, max_pages)

    if not images:
        logger.warning(f"PDF转图片失败：{pdf_path}")
        return ""

    # 对每页进行OCR
    all_text = []
    for i, img_path in enumerate(images, 1):
        logger.info(f"OCR处理第 {i}/{len(images)} 页...")
        page_text = await parse_image_to_text(img_path, min_confidence)
        if page_text:
            all_text.append(f"# 第 {i} 页\n\n{page_text}")

    # 清理临时图片
    for img_path in images:
        try:
            Path(img_path).unlink(missing_ok=True)
        except Exception:
            pass

    return "\n\n".join(all_text)


async def _convert_pdf_to_images(
    pdf_path: str | Path,
    max_pages: int = 10
) -> list[str]:
    """将PDF转换为图片（用于OCR预处理）。

    使用pdf2image或PyMuPDF。

    Args:
        pdf_path: PDF文件路径
        max_pages: 最大转换页数

    Returns:
        图片文件路径列表
    """
    pdf_path = Path(pdf_path)

    # 优先使用pdf2image（需要poppler）
    try:
        from pdf2image import convert_from_path

        def convert():
            # 转换为PIL Image对象
            images = convert_from_path(
                str(pdf_path),
                first_page=1,
                last_page=max_pages,
                dpi=200,  # 较高DPI提高OCR准确率
            )
            # 保存为临时文件
            temp_paths = []
            for i, img in enumerate(images, 1):
                with tempfile.NamedTemporaryFile(
                    suffix=f"_page_{i}.png",
                    delete=False
                ) as tmp:
                    img.save(tmp.name, "PNG")
                    temp_paths.append(tmp.name)
            return temp_paths

        return await asyncio.to_thread(convert)

    except ImportError:
        logger.warning("pdf2image未安装，尝试使用PyMuPDF...")
    except Exception as e:
        logger.warning(f"pdf2image转换失败：{e}，尝试使用PyMuPDF...")

    # 备选：使用PyMuPDF（fitz）
    try:
        import fitz

        def convert_with_fitz():
            doc = fitz.open(str(pdf_path))
            temp_paths = []
            for i in range(min(len(doc), max_pages)):
                page = doc[i]
                # 渲染为图片
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), dpi=200)
                with tempfile.NamedTemporaryFile(
                    suffix=f"_page_{i+1}.png",
                    delete=False
                ) as tmp:
                    pix.save(tmp.name)
                    temp_paths.append(tmp.name)
            doc.close()
            return temp_paths

        return await asyncio.to_thread(convert_with_fitz)

    except ImportError:
        logger.error("pdf2image和PyMuFIT均未安装，无法进行PDF OCR")
        return []
    except Exception as e:
        logger.error(f"PDF转图片失败：{e}")
        return []


async def is_scan_only_pdf(content: bytes, filename: str) -> bool:
    """检测PDF是否为扫描版（无文本层）。

    Args:
        content: PDF文件内容
        filename: 文件名

    Returns:
        True if 扫描版PDF（需要OCR）
    """
    if not filename.lower().endswith(".pdf"):
        return False

    # 先尝试普通解析
    try:
        from app.services.parser import parse_document
        text = await parse_document(content, filename)

        # 检查文本质量
        if text and len(text.strip()) > 100:
            # 有足够文本，可能不是扫描版
            visible_ratio = sum(1 for c in text if c.isprintable() or c.isspace()) / max(len(text), 1)
            if visible_ratio > 0.7:
                return False  # 有可读文本，不需要OCR

        # 文本过少或质量差，可能是扫描版
        return True

    except Exception:
        # 解析失败，可能是扫描版
        return True


async def parse_with_ocr_fallback(
    content: bytes,
    filename: str,
    force_ocr: bool = False
) -> str:
    """带OCR兜底的文档解析。

    Args:
        content: 文件内容
        filename: 文件名
        force_ocr: 强制使用OCR（不先尝试普通解析）

    Returns:
        解析后的文本内容
    """
    suffix = Path(filename).suffix.lower()

    # 非PDF文件直接用普通解析
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp"} and not force_ocr:
        from app.services.parser import parse_document
        return await parse_document(content, filename)

    # 检查是否需要OCR
    need_ocr = force_ocr

    if not need_ocr and suffix == ".pdf":
        need_ocr = await is_scan_only_pdf(content, filename)

    if need_ocr:
        logger.info(f"检测到扫描版PDF或图片，启用OCR：{filename}")

        # 保存为临时文件
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)

        try:
            if suffix == ".pdf":
                text = await parse_pdf_to_text(tmp_path)
            else:
                text = await parse_image_to_text(tmp_path)

            if not text or len(text.strip()) < 20:
                raise ValueError("OCR识别结果为空或过短")

            return text

        finally:
            tmp_path.unlink(missing_ok=True)

    # 不需要OCR，使用普通解析
    from app.services.parser import parse_document
    return await parse_document(content, filename)


def is_ocr_available() -> bool:
    """检查OCR功能是否可用."""
    if _ocr_available is None:
        return _check_paddleocr_available()
    return _ocr_available
