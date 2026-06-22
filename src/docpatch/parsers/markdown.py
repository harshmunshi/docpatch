"""Markdown parser and serializer using markdown-it-py.

Round-trip invariant: serialize(parse(data)) == data for any valid Markdown bytes.

Strategy: each top-level block's raw_span is extended to include trailing blank lines
up to the next block, so the spans tile the source without gaps. Nested blocks store
only their own lines (gaps are in the parent's span). The DOCUMENT root stores the
complete source bytes so an unpatched tree can be serialized instantly.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token

from docpatch.core.ids import make_id
from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType

_BLOCK_TOKEN_TO_NODE_TYPE: dict[str, NodeType] = {
    "heading": NodeType.HEADING,
    "paragraph": NodeType.PARAGRAPH,
    "bullet_list": NodeType.LIST,
    "ordered_list": NodeType.LIST,
    "list_item": NodeType.LIST_ITEM,
    "blockquote": NodeType.BLOCKQUOTE,
    "fence": NodeType.CODE_BLOCK,
    "code_block": NodeType.CODE_BLOCK,
    "table": NodeType.TABLE,
    "tr": NodeType.TABLE_ROW,
    "td": NodeType.TABLE_CELL,
    "th": NodeType.TABLE_CELL,
    "html_block": NodeType.HTML_BLOCK,
    "hr": NodeType.THEMATIC_BREAK,
}


@dataclass
class _BlockInfo:
    open_tok: Token
    close_tok: Token
    inner_tokens: list[Token]
    node_type: NodeType
    ordinal: int
    content: str | None
    meta: dict[str, Any]


def _collect_blocks(tokens: list[Token]) -> list[_BlockInfo]:
    """First pass: collect block boundaries without computing raw_spans."""
    blocks: list[_BlockInfo] = []
    type_counter: dict[str, int] = {}
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if tok.type == "inline":
            i += 1
            continue

        if tok.nesting == 1:  # opening tag
            base = tok.type.replace("_open", "").replace("_close", "")
            node_type = _BLOCK_TOKEN_TO_NODE_TYPE.get(base, NodeType.PARAGRAPH)
            ord_ = type_counter.get(node_type, 0)
            type_counter[node_type] = ord_ + 1

            depth = 1
            j = i + 1
            close_type = tok.type.replace("_open", "_close")
            while j < len(tokens) and depth > 0:
                if tokens[j].type == close_type:
                    depth -= 1
                elif tokens[j].type == tok.type:
                    depth += 1
                j += 1
            inner = tokens[i + 1 : j - 1]
            close_tok = tokens[j - 1]
            content = _extract_content(inner)

            meta: dict[str, Any] = {}
            if node_type == NodeType.HEADING and tok.tag:
                meta["level"] = tok.tag[1]
            if node_type == NodeType.CODE_BLOCK:
                meta["markup"] = tok.markup or "```"
                if tok.info:
                    meta["info"] = tok.info.strip()

            blocks.append(_BlockInfo(tok, close_tok, inner, node_type, ord_, content, meta))
            i = j

        elif tok.nesting == 0 and tok.type != "inline":
            base = tok.type
            node_type = _BLOCK_TOKEN_TO_NODE_TYPE.get(base, NodeType.PARAGRAPH)
            ord_ = type_counter.get(node_type, 0)
            type_counter[node_type] = ord_ + 1
            content = tok.content or None
            meta = {"markup": tok.markup} if tok.markup else {}
            blocks.append(_BlockInfo(tok, tok, [], node_type, ord_, content, meta))
            i += 1
        else:
            i += 1

    return blocks


def _source_lines(src: bytes) -> list[bytes]:
    return src.splitlines(keepends=True)


def _parse_block(
    tokens: list[Token],
    src: bytes,
    parent_id: str,
    src_lines: list[bytes],
    parent_end_line: int,
) -> list[Node]:
    """Build nodes from a token list, tiling raw_spans to cover all source bytes."""
    blocks = _collect_blocks(tokens)
    if not blocks:
        return []

    nodes: list[Node] = []
    for idx, blk in enumerate(blocks):
        open_map = blk.open_tok.map
        if not open_map:
            # No source map — can't compute raw_span; build node without it
            node_id = make_id(blk.node_type, parent_id, blk.content, blk.ordinal)
            sub = _parse_block(blk.inner_tokens, src, node_id, src_lines, 0)
            nodes.append(
                Node(
                    id=node_id,
                    type=blk.node_type,
                    children=tuple(sub),
                    content=blk.content,
                    metadata=blk.meta,
                )
            )
            continue

        start_line = open_map[0]
        # Extend end to next sibling's start (covers blank lines between blocks)
        if idx + 1 < len(blocks):
            next_map = blocks[idx + 1].open_tok.map
            end_line = next_map[0] if next_map else open_map[1]
        else:
            end_line = parent_end_line  # last block: extend to parent's end

        raw_span = b"".join(src_lines[start_line:end_line])

        node_id = make_id(blk.node_type, parent_id, blk.content, blk.ordinal)
        # Nested blocks use only their own tight span (no gap-extension needed for children)
        tight_end = open_map[1]
        sub = _parse_block(blk.inner_tokens, src, node_id, src_lines, tight_end)

        nodes.append(
            Node(
                id=node_id,
                type=blk.node_type,
                children=tuple(sub),
                content=blk.content,
                raw_span=raw_span,
                metadata=blk.meta,
            )
        )

    return nodes


def _extract_content(tokens: list[Token]) -> str | None:
    """Pull inline text from a token list."""
    parts: list[str] = []
    for tok in tokens:
        if tok.type == "inline" and tok.children:
            for child in tok.children:
                if child.type in ("text", "softbreak", "hardbreak", "code_inline"):
                    parts.append(child.content if child.content else "\n")
        elif tok.type == "inline" and tok.content:
            parts.append(tok.content)
    text = "".join(parts).strip()
    return text or None


def _tokens_to_tree(tokens: list[Token], src: bytes) -> DocTree:
    root_id = make_id(NodeType.DOCUMENT, None, None, 0)
    src_lines = _source_lines(src)
    children = _parse_block(tokens, src, root_id, src_lines, len(src_lines))
    # root stores complete source for fast unpatched serialization
    root = Node(
        id=root_id,
        type=NodeType.DOCUMENT,
        children=tuple(children),
        raw_span=src,
    )
    return DocTree(root=root)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

_md = MarkdownIt().enable("table")


def parse(data: bytes) -> DocTree:
    """Parse Markdown bytes into a DocTree."""
    text = data.decode("utf-8", errors="replace")
    tokens = _md.parse(text)
    return _tokens_to_tree(tokens, data)


def serialize(tree: DocTree) -> bytes:
    """Serialize a DocTree back to Markdown bytes.

    Unpatched tree: emit root.raw_span directly (O(1), lossless).
    Patched tree (root.raw_span cleared by splice): rebuild from child spans.
    """
    return _serialize_node(tree.root)


def _serialize_node(node: Node) -> bytes:
    # Fast path: node has original bytes and subtree is unpatched
    if node.raw_span is not None:
        return node.raw_span
    # Patched node: reconstruct from children or content
    if node.children:
        return b"".join(_serialize_node(c) for c in node.children)
    return _render_patched_leaf(node)


def _render_patched_leaf(node: Node) -> bytes:
    """Reconstruct markdown bytes for a patched leaf node (raw_span is None)."""
    content = node.content or ""
    meta = node.metadata

    if node.type == NodeType.CODE_BLOCK:
        fence = meta.get("markup", "```")
        info = meta.get("info", "")
        opener = f"{fence}{info}" if info else fence
        closer = fence[:3]  # ``` or ~~~, strip any language suffix
        return f"{opener}\n{content}\n{closer}\n\n".encode()

    if node.type == NodeType.HEADING:
        level = int(meta.get("level", 1))
        return f"{'#' * level} {content}\n\n".encode()

    if node.type == NodeType.PARAGRAPH:
        return f"{content}\n\n".encode()

    if node.type == NodeType.THEMATIC_BREAK:
        markup = meta.get("markup", "---")
        return f"{markup}\n\n".encode()

    # Generic fallback for anything else (inline nodes, etc.)
    return content.encode() + b"\n"
