"""Parser registry. Detects format and dispatches to the right module."""

from __future__ import annotations

import importlib
from pathlib import Path
from types import ModuleType

from docpatch.core.errors import ParseError
from docpatch.core.types import DocFormat

_EXT_MAP: dict[str, DocFormat] = {
    ".md": DocFormat.MARKDOWN,
    ".markdown": DocFormat.MARKDOWN,
    ".json": DocFormat.JSON,
    ".docx": DocFormat.DOCX,
    ".pdf": DocFormat.PDF,
    ".html": DocFormat.HTML,
    ".htm": DocFormat.HTML,
    ".xlsx": DocFormat.XLSX,
}

_MODULE_MAP: dict[DocFormat, str] = {
    DocFormat.MARKDOWN: "docpatch.parsers.markdown",
    DocFormat.JSON: "docpatch.parsers.json_parser",
}


def detect_format(path: str | Path | None = None, data: bytes | None = None) -> DocFormat:
    """Detect document format from file extension, then from content sniffing."""
    if path is not None:
        ext = Path(path).suffix.lower()
        if ext in _EXT_MAP:
            return _EXT_MAP[ext]
    if data is not None:
        stripped = data.lstrip()
        if stripped.startswith(b"{") or stripped.startswith(b"["):
            return DocFormat.JSON
        if stripped.startswith(b"#") or stripped.startswith(b"---"):
            return DocFormat.MARKDOWN
    return DocFormat.UNKNOWN


def get_parser(fmt: DocFormat) -> ModuleType:
    """Return the parser module for a format, or raise ParseError."""
    module_name = _MODULE_MAP.get(fmt)
    if module_name is None:
        raise ParseError(ParseError.Kind.UNSUPPORTED_FORMAT, str(fmt))
    return importlib.import_module(module_name)
