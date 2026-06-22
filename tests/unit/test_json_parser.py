"""Unit tests for parsers/json_parser.py."""

import pytest

from docpatch.core.errors import ParseError
from docpatch.core.types import NodeType
from docpatch.parsers.json_parser import parse, serialize

SIMPLE_JSON = b'{"name": "Alice", "age": 30}'
NESTED_JSON = b'{"person": {"name": "Bob"}, "scores": [1, 2, 3]}'


def test_parse_returns_doctree() -> None:
    tree = parse(SIMPLE_JSON)
    assert tree.root.type == NodeType.DOCUMENT


def test_parse_finds_object() -> None:
    tree = parse(SIMPLE_JSON)
    obj_nodes = [n for n in tree.walk() if n.type == NodeType.OBJECT]
    assert len(obj_nodes) >= 1


def test_parse_finds_key_value() -> None:
    tree = parse(SIMPLE_JSON)
    kv_nodes = [n for n in tree.walk() if n.type == NodeType.KEY_VALUE]
    keys = {n.content for n in kv_nodes}
    assert "name" in keys
    assert "age" in keys


def test_serialize_round_trip_simple() -> None:
    tree = parse(SIMPLE_JSON)
    out = serialize(tree)
    assert out == SIMPLE_JSON


def test_serialize_round_trip_nested() -> None:
    tree = parse(NESTED_JSON)
    out = serialize(tree)
    assert out == NESTED_JSON


def test_parse_array() -> None:
    data = b"[1, 2, 3]"
    tree = parse(data)
    assert tree.root.children[0].type == NodeType.ARRAY


def test_parse_invalid_json() -> None:
    with pytest.raises(ParseError) as exc_info:
        parse(b"{bad json}")
    assert exc_info.value.kind == ParseError.Kind.MALFORMED_INPUT


def test_node_ids_unique() -> None:
    tree = parse(NESTED_JSON)
    ids = [n.id for n in tree.walk()]
    assert len(ids) == len(set(ids))
