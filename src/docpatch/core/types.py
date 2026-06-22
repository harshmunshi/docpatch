"""Fundamental enumerations and type aliases. No pydantic, no imports from docpatch."""

from __future__ import annotations

from enum import StrEnum

NodeRef = str  # a node ID string


class NodeType(StrEnum):
    # structural
    DOCUMENT = "document"
    SECTION = "section"
    HEADING = "heading"
    PARAGRAPH = "paragraph"
    LIST = "list"
    LIST_ITEM = "list_item"
    BLOCKQUOTE = "blockquote"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    TABLE_ROW = "table_row"
    TABLE_CELL = "table_cell"
    THEMATIC_BREAK = "thematic_break"
    HTML_BLOCK = "html_block"
    # inline (leaf)
    INLINE = "inline"
    TEXT = "text"
    CODE_INLINE = "code_inline"
    SOFTBREAK = "softbreak"
    HARDBREAK = "hardbreak"
    IMAGE = "image"
    LINK = "link"
    # JSON-specific
    OBJECT = "object"
    ARRAY = "array"
    KEY_VALUE = "key_value"
    STRING = "string"
    NUMBER = "number"
    BOOLEAN = "boolean"
    NULL = "null"


class DocFormat(StrEnum):
    MARKDOWN = "markdown"
    JSON = "json"
    DOCX = "docx"
    PDF = "pdf"
    HTML = "html"
    XLSX = "xlsx"
    UNKNOWN = "unknown"
