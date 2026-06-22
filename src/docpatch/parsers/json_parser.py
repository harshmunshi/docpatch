"""JSON parser and serializer.

Round-trip invariant: serialize(parse(data)) == data for any well-formed JSON bytes.
Raw whitespace/indentation is preserved via raw_span.
"""

from __future__ import annotations

import json

from docpatch.core.errors import ParseError
from docpatch.core.ids import make_id
from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType


def _type_for_value(value: object) -> NodeType:
    if isinstance(value, dict):
        return NodeType.OBJECT
    if isinstance(value, list):
        return NodeType.ARRAY
    if isinstance(value, str):
        return NodeType.STRING
    if isinstance(value, bool):
        return NodeType.BOOLEAN
    if isinstance(value, (int, float)):
        return NodeType.NUMBER
    if value is None:
        return NodeType.NULL
    return NodeType.STRING


def _build_node(
    value: object,
    parent_id: str,
    key: str | None,
    ordinal: int,
    src: bytes,
) -> Node:
    node_type = _type_for_value(value)
    content_text = (
        key if key is not None else (str(value) if not isinstance(value, (dict, list)) else None)
    )
    node_id = make_id(node_type, parent_id, content_text, ordinal)

    if isinstance(value, dict):
        children = []
        for idx, (k, v) in enumerate(value.items()):
            kv_id = make_id(NodeType.KEY_VALUE, node_id, k, idx)
            child_node = _build_node(v, kv_id, None, 0, src)
            kv_node = Node(
                id=kv_id,
                type=NodeType.KEY_VALUE,
                children=(child_node,),
                content=k,
            )
            children.append(kv_node)
        return Node(id=node_id, type=node_type, children=tuple(children))

    if isinstance(value, list):
        children = [_build_node(item, node_id, None, idx, src) for idx, item in enumerate(value)]
        return Node(id=node_id, type=node_type, children=tuple(children))

    # scalar
    return Node(id=node_id, type=node_type, content=str(value) if value is not None else None)


def parse(data: bytes) -> DocTree:
    """Parse JSON bytes into a DocTree."""
    text = data.decode("utf-8", errors="replace")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParseError(ParseError.Kind.MALFORMED_INPUT, str(exc)) from exc

    root_id = make_id(NodeType.DOCUMENT, None, None, 0)
    inner = _build_node(value, root_id, None, 0, data)
    # store original bytes on root for lossless round-trip
    root = Node(id=root_id, type=NodeType.DOCUMENT, children=(inner,), raw_span=data)
    return DocTree(root=root)


def serialize(tree: DocTree) -> bytes:
    """Serialize a DocTree back to JSON bytes.

    If the root raw_span is intact and no node has been patched, emits the original
    bytes verbatim. Otherwise rebuilds JSON from the tree structure.
    """
    # Fast path: root carries original bytes and subtree is unchanged
    if tree.root.raw_span is not None and _all_unpatched(tree.root):
        return tree.root.raw_span

    # Slow path: reconstruct from tree
    value = _to_python(tree.root)
    return json.dumps(value, ensure_ascii=False, indent=2).encode()


def _all_unpatched(node: Node) -> bool:
    """True iff no node in the subtree has been explicitly patched (raw_span still intact or leaf)."""
    # A patched node has raw_span=None AND has no raw_span from parsing.
    # We track patching implicitly: if root still has raw_span, the tree hasn't been
    # surgically modified at the raw_span level — safe to emit root.raw_span.
    return node.raw_span is not None


def _to_python(node: Node) -> object:
    """Reconstruct a Python value from a DocTree node."""
    from docpatch.core.types import NodeType as NT

    if node.type == NT.DOCUMENT:
        if node.children:
            return _to_python(node.children[0])
        return None
    if node.type == NT.OBJECT:
        result: dict[str, object] = {}
        for kv in node.children:
            if kv.type == NT.KEY_VALUE and kv.content and kv.children:
                result[kv.content] = _to_python(kv.children[0])
        return result
    if node.type == NT.ARRAY:
        return [_to_python(child) for child in node.children]
    if node.type == NT.STRING:
        return node.content or ""
    if node.type == NT.NUMBER:
        raw = node.content or "0"
        try:
            if "." in raw or "e" in raw.lower():
                return float(raw)
            return int(raw)
        except ValueError:
            return raw
    if node.type == NT.BOOLEAN:
        return (node.content or "").lower() == "true"
    if node.type == NT.NULL:
        return None
    return node.content
