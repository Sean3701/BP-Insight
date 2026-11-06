"""M03 deterministic document extraction; no model API calls."""
from dataclasses import dataclass
from pathlib import Path
from zipfile import BadZipFile

SUPPORTED = {'.pdf', '.pptx', '.docx', '.xlsx'}
MAX_BYTES = 25 * 1024 * 1024
MAX_SEGMENTS = 5000
MAX_SEGMENT_CHARS = 12000


class DocumentParseError(Exception):
    pass


@dataclass
class Segment:
    location: str
    text: str


def _append(segments, location, text):
    content = str(text or '').strip()
    if content:
        if len(segments) >= MAX_SEGMENTS:
            raise DocumentParseError('文档内容太多，超过当前版本可处理的片段数量上限')
        # Don't silently truncate any excerpt: split long content into labeled parts.
        for idx, start in enumerate(range(0, len(content), MAX_SEGMENT_CHARS), 1):
            if len(segments) >= MAX_SEGMENTS:
                raise DocumentParseError('文档内容太多，超过当前版本可处理的片段数量上限')
            tail = f' · 分段{idx}' if len(content) > MAX_SEGMENT_CHARS else ''
            segments.append(Segment(location + tail, content[start:start + MAX_SEGMENT_CHARS]))


def extract(path: Path):
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED:
        raise DocumentParseError('当前仅支持 PDF、PPTX、DOCX、XLSX')
    parts = []
    try:
        if suffix == '.pdf':
            from pypdf import PdfReader
            reader = PdfReader(str(path), strict=False)
            if reader.is_encrypted:
                try:
                    reader.decrypt('')
                except Exception:
                    raise DocumentParseError('PDF 已加密，请上传无密码保护的版本')
            for page_no, page in enumerate(reader.pages, 1):
                _append(parts, f'第{page_no}页', page.extract_text() or '')
        elif suffix == '.pptx':
            from pptx import Presentation
            presentation = Presentation(str(path))
            for slide_no, slide in enumerate(presentation.slides, 1):
                for shape in slide.shapes:
                    if shape.has_text_frame:
                        _append(parts, f'第{slide_no}页幻灯片', shape.text)
                    if shape.has_table:
                        for row_no, row in enumerate(shape.table.rows, 1):
                            _append(parts, f'第{slide_no}页幻灯片 · 表格行{row_no}', ' | '.join(c.text for c in row.cells))
        elif suffix == '.docx':
            from docx import Document
            doc = Document(str(path))
            # Word pagination depends on renderer. Use paragraph/table indexes, not fictitious page numbers.
            for i, p in enumerate(doc.paragraphs, 1):
                _append(parts, f'段落{i}', p.text)
            for table_i, table in enumerate(doc.tables, 1):
                for row_i, row in enumerate(table.rows, 1):
                    _append(parts, f'表格{table_i} · 行{row_i}', ' | '.join(c.text for c in row.cells))
        else:
            from openpyxl import load_workbook
            from openpyxl.utils import get_column_letter
            wb = load_workbook(path, read_only=True, data_only=True)
            try:
                for sheet in wb:
                    for row_no, row in enumerate(sheet.iter_rows(), 1):
                        vals = [f'{get_column_letter(c.column)}={str(c.value)}' for c in row if c.value is not None]
                        if vals:
                            _append(parts, f'工作表「{sheet.title}」 · 第{row_no}行', ' | '.join(vals))
            finally:
                wb.close()
    except DocumentParseError:
        raise
    except Exception as exc:
        raise DocumentParseError(f'解析文件失败：{type(exc).__name__}；可能是加密、损坏或不支持的文件内容') from exc
    warning = '当前仅解析可提取文本和部分表格，不支持图片文字、复杂图表或扫描件 OCR；原文均未经独立核验。'
    if not parts:
        warning += ' 当前未提取到任何可用文字，请检查是否为扫描件或纯图片文档。'
    return parts, warning
