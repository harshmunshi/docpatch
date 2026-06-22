"""Unit tests for parsers/markdown.py."""

from docpatch.core.types import NodeType
from docpatch.parsers.markdown import parse, serialize

SIMPLE_MD = b"# Hello\n\nThis is a paragraph.\n"
MULTI_HEADING = b"# First\n\nParagraph one.\n\n## Second\n\nParagraph two.\n"


def test_parse_returns_doctree() -> None:
    tree = parse(SIMPLE_MD)
    assert tree.root.type == NodeType.DOCUMENT


def test_parse_finds_heading() -> None:
    tree = parse(SIMPLE_MD)
    headings = [n for n in tree.walk() if n.type == NodeType.HEADING]
    assert len(headings) == 1
    assert headings[0].content == "Hello"


def test_parse_finds_paragraph() -> None:
    tree = parse(SIMPLE_MD)
    paragraphs = [n for n in tree.walk() if n.type == NodeType.PARAGRAPH]
    assert len(paragraphs) >= 1


def test_parse_multi_heading() -> None:
    tree = parse(MULTI_HEADING)
    headings = [n for n in tree.walk() if n.type == NodeType.HEADING]
    assert len(headings) == 2


def test_serialize_round_trip() -> None:
    tree = parse(SIMPLE_MD)
    out = serialize(tree)
    assert out == SIMPLE_MD


def test_serialize_multi_heading_round_trip() -> None:
    tree = parse(MULTI_HEADING)
    out = serialize(tree)
    assert out == MULTI_HEADING


def test_node_ids_are_unique() -> None:
    tree = parse(MULTI_HEADING)
    ids = [n.id for n in tree.walk()]
    assert len(ids) == len(set(ids))


def test_node_fingerprints_filled() -> None:
    tree = parse(SIMPLE_MD)
    for node in tree.walk():
        assert node.fingerprint != ""


def test_code_block_parse() -> None:
    md = b"# Heading\n\n```python\nprint('hi')\n```\n"
    tree = parse(md)
    code_nodes = [n for n in tree.walk() if n.type == NodeType.CODE_BLOCK]
    assert len(code_nodes) >= 1
