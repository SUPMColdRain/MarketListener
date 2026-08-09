"""扫描件 OCR 补偿：将 PDF 页面渲染为图像后用 RapidOCR 识别中文文本。

该模块是 report_pipeline 的可选依赖。未安装 pymupdf / rapidocr-onnxruntime
时，调用方应捕获 ImportError 并继续使用纯文本抽取结果。
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Any

try:  # pragma: no cover - 依赖由 scripts/retry_report_ocr.py 安装
    import fitz  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

try:  # pragma: no cover
    from rapidocr_onnxruntime import RapidOCR
except Exception:  # pragma: no cover
    RapidOCR = None

_engine: Any | None = None
_engine_lock = threading.Lock()


def _get_engine() -> Any:
    """延迟初始化 RapidOCR（首次调用会下载 ONNX 模型）。"""

    global _engine
    if _engine is not None:
        return _engine
    if RapidOCR is None:
        raise ImportError("rapidocr-onnxruntime 未安装，无法执行 OCR")
    with _engine_lock:
        if _engine is None:
            _engine = RapidOCR()
    return _engine


def _render_page_png(page: Any, dpi: int = 200) -> bytes:
    """将 PDF 页面渲染为 PNG 字节。"""

    zoom = dpi / 72.0
    pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False)
    return pix.tobytes("png")


def ocr_pdf_pages(pdf_path: Path | str, *, dpi: int = 200, max_pages: int = 300) -> list[str]:
    """对 PDF 逐页 OCR，返回按页合并的文本列表。

    失败页会以空字符串占位，避免页码错位；整篇失败时抛异常。
    """

    if fitz is None:
        raise ImportError("pymupdf 未安装，无法渲染 PDF")
    engine = _get_engine()
    pdf_path = Path(pdf_path)
    pages: list[str] = []
    with fitz.open(str(pdf_path)) as document:
        page_count = min(len(document), max_pages)
        for page in document.pages(0, page_count):
            try:
                png = _render_page_png(page, dpi=dpi)
                result, _elapsed = engine(png)
                lines: list[str] = []
                if result:
                    for item in result:
                        # item: [box, text, score]
                        text = str(item[1]).strip()
                        if text:
                            lines.append(text)
                pages.append("\n".join(lines))
            except Exception:  # noqa: BLE001 - 单页失败不阻断整篇
                pages.append("")
    return pages


__all__ = ["ocr_pdf_pages"]
