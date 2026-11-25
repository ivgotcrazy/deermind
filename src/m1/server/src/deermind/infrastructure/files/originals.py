"""验证教材原件的格式与页数，调用者在有限的文件检查任务内运行。"""

from collections.abc import Callable
from contextlib import closing
from io import BytesIO
from math import isfinite
from threading import Lock
from typing import BinaryIO, cast

# 该发布包含原生运行库，尚未提供类型标记。此文件是窄适配边界。
import pypdfium2 as pdfium  # pyright: ignore[reportMissingTypeStubs]
from PIL import Image

# PDFium 的进程内调用不能并发。图像解码也共用一个槽位，限制峰值内存。
_DECODER = Lock()
MAX_PAGES = 600
MAX_PIXELS = 40_000_000


def inspect_original(source: BinaryIO, media_type: str) -> int:
    """按真实解析结果返回文件内页数；非法或无法解码的文件拒绝。"""
    source.seek(0)
    try:
        with _DECODER:
            if media_type == "application/pdf":
                # PDF 按页数校验，页数即对外记录的文件页号。
                with pdfium.PdfDocument(source, autoclose=False) as document:
                    count = len(document)
                    if not 1 <= count <= MAX_PAGES:
                        # 页数超出支持上限，拒绝收录。
                        raise ValueError("PDF page count exceeds the supported range")
                    return count
            with Image.open(
                source, formats=["PNG" if media_type == "image/png" else "JPEG"]
            ) as image:
                if image.width * image.height > MAX_PIXELS or getattr(image, "is_animated", False):
                    # 像素总量超限或为动图，不纳入教材原件。
                    raise ValueError("Image dimensions or frame count is not supported")
                image.verify()
            source.seek(0)
            with Image.open(source) as image:
                image.load()
            return 1
    except (OSError, SyntaxError, Image.DecompressionBombError, pdfium.PdfiumError) as error:
        # 解码异常统一收敛为"无法按声明格式解析"。
        raise ValueError("Original cannot be decoded as the declared format") from error
    finally:
        # 校验结束后指针复位，便于后续复用同一流。
        source.seek(0)


def render_original_page(source: BinaryIO, media_type: str, file_page: int) -> bytes:
    """按文件内页号制作有界模型用页图，原件留在不可变存储中。"""
    if not 1 <= file_page <= MAX_PAGES:
        # 页号越界，拒绝渲染。
        raise ValueError("Unknown original page")
    limit = 1800
    source.seek(0)
    with _DECODER, BytesIO() as output:
        if media_type == "application/pdf":
            with pdfium.PdfDocument(source, autoclose=False) as document:
                if file_page > len(document):
                    # 请求页号超出 PDF 实际页数。
                    raise ValueError("Unknown PDF page")
                with closing(document[file_page - 1]) as page:
                    longest = max(page.get_size())
                    if not isfinite(longest) or longest <= 0:
                        # 页面尺寸非有限正值，无法按比例缩放渲染。
                        raise ValueError("Invalid PDF page dimensions")
                    # PDFium 的 Python 包装没有 render/to_pil 的返回类型标记。
                    scale = min(3.0, limit / longest)
                    render = cast(
                        Callable[..., pdfium.PdfBitmap],
                        page.render,  # pyright: ignore[reportUnknownMemberType]
                    )
                    bitmap = render(scale=scale)
                    with closing(bitmap):
                        image = bitmap.to_pil()
                        image.convert("RGB").save(output, "JPEG", quality=92)
        else:
            if file_page != 1 or media_type not in {"image/jpeg", "image/png"}:
                # 静态图只有第 1 页，且类型必须在白名单内。
                raise ValueError("Unknown image page")
            with Image.open(source) as image:
                if image.width * image.height > MAX_PIXELS:
                    # 像素总量超限，缩图前先拦截。
                    raise ValueError("Image dimensions exceed the resource limit")
                image.thumbnail((limit, limit))
                image.convert("RGB").save(output, "JPEG", quality=92)
        return output.getvalue()
