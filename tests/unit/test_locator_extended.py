"""Extended tests for symbolic and semantic locators."""

import json

import pytest

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType
from docpatch.locator.semantic import SemanticLocator, _parse_response
from docpatch.locator.symbolic import SymbolicLocator, _find_heading
from docpatch.models.mock import MockModelClient

# ── shared fixtures ─────────────────────────────────────────────────────────

def _make_tree() -> DocTree:
    h_intro = Node(id="heading:root/intro#0", type=NodeType.HEADING, content="Introduction")
    p_intro = Node(
        id="paragraph:root/p-intro#0",
        type=NodeType.PARAGRAPH,
        content="Welcome to the docs.",
        raw_span=b"Welcome to the docs.\n",
    )
    h_install = Node(id="heading:root/install#1", type=NodeType.HEADING, content="Installation")
    code = Node(
        id="code_block:root/code#0",
        type=NodeType.CODE_BLOCK,
        content="pip install foo",
        metadata={"markup": "```", "info": "bash"},
    )
    h_api = Node(id="heading:root/api#2", type=NodeType.HEADING, content="API")
    p_api = Node(
        id="paragraph:root/p-api#0",
        type=NodeType.PARAGRAPH,
        content="Use the client to call endpoints.",
        raw_span=b"Use the client to call endpoints.\n",
    )
    root = Node(
        id="document:root",
        type=NodeType.DOCUMENT,
        children=(h_intro, p_intro, h_install, code, h_api, p_api),
    )
    return DocTree(root=root)


# ── _find_heading ────────────────────────────────────────────────────────────

def test_find_heading_exact() -> None:
    tree = _make_tree()
    nid = _find_heading(tree, "Installation")
    assert nid == "heading:root/install#1"


def test_find_heading_prefix() -> None:
    tree = _make_tree()
    nid = _find_heading(tree, "Intro")
    assert nid == "heading:root/intro#0"


def test_find_heading_missing() -> None:
    tree = _make_tree()
    assert _find_heading(tree, "Nonexistent") is None


# ── JSON pointer ─────────────────────────────────────────────────────────────

def test_symbolic_json_pointer_by_id() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "edit /install in the document")
    assert result.confidence == 1.0
    assert result.method == "json_pointer"


# ── quoted heading (ambiguous) ───────────────────────────────────────────────

def test_symbolic_quoted_heading_ambiguous() -> None:
    p1 = Node(id="p:root/a#0", type=NodeType.PARAGRAPH, content="duplicate")
    p2 = Node(id="p:root/a#1", type=NodeType.PARAGRAPH, content="duplicate")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(p1, p2))
    tree = DocTree(root=root)
    loc = SymbolicLocator()
    result = loc.locate(tree, 'edit the "duplicate" paragraph')
    assert result.confidence == 0.8
    assert result.method == "quoted_heading_ambiguous"
    assert len(result.candidates) == 2


# ── heading path ─────────────────────────────────────────────────────────────

def test_symbolic_heading_path() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "Introduction/Welcome")
    # Heading path requires last part to match a node content exactly
    # "Welcome" doesn't match so falls through — just check it doesn't crash
    assert result is not None


def test_symbolic_heading_path_match() -> None:
    child_h = Node(id="heading:root/intro#0/sub#0", type=NodeType.HEADING, content="Setup")
    parent_h = Node(
        id="heading:root/intro#0",
        type=NodeType.HEADING,
        content="Introduction",
        children=(child_h,),
    )
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(parent_h,))
    tree = DocTree(root=root)
    loc = SymbolicLocator()
    result = loc.locate(tree, "Introduction/Setup")
    assert result.method == "heading_path"
    assert result.node_ids == ["heading:root/intro#0/sub#0"]


# ── scoped section ───────────────────────────────────────────────────────────

def test_symbolic_scoped_section_finds_leaf() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "In the Installation section update the pip command")
    assert result.method == "scoped_section"
    assert result.node_ids == ["code_block:root/code#0"]
    assert result.confidence == 0.85


def test_symbolic_scoped_section_fallback_to_heading() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    # instruction post-scope has no overlapping words with section content
    result = loc.locate(tree, "In the API section do xyz quux frobnitz")
    assert result.method in ("scoped_section", "scoped_section_heading")


def test_symbolic_scoped_section_unknown_section() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "In the Nonexistent section change something")
    # Should fall through to bare_heading or miss
    assert result.method != "scoped_section"


# ── bare heading ambiguous ────────────────────────────────────────────────────

def test_symbolic_bare_heading_ambiguous() -> None:
    h1 = Node(id="heading:root/api#0", type=NodeType.HEADING, content="API")
    h2 = Node(id="heading:root/api#1", type=NodeType.HEADING, content="API")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(h1, h2))
    tree = DocTree(root=root)
    loc = SymbolicLocator()
    result = loc.locate(tree, "shorten the API section")
    assert result.method == "bare_heading_ambiguous"
    assert result.confidence == 0.4


# ── SemanticLocator ──────────────────────────────────────────────────────────

def test_semantic_locate_valid_response() -> None:
    tree = _make_tree()
    alias = "node_0"  # first entry
    response = json.dumps({"node_ids": [alias], "confidence": 0.9, "candidates": []})
    model = MockModelClient(response)
    loc = SemanticLocator(model)
    result = loc.locate(tree, "rewrite the intro")
    assert result.confidence == 0.9
    assert result.method == "semantic"
    assert len(result.node_ids) == 1


def test_semantic_locate_empty_skeleton() -> None:
    root = Node(id="document:root", type=NodeType.DOCUMENT)
    tree = DocTree(root=root)
    model = MockModelClient("{}")
    loc = SemanticLocator(model)
    result = loc.locate(tree, "anything")
    assert result.confidence == 0.0
    assert result.method == "semantic_no_skeleton"


def test_semantic_locate_unknown_alias() -> None:
    tree = _make_tree()
    response = json.dumps({"node_ids": ["node_999"], "confidence": 0.8, "candidates": []})
    model = MockModelClient(response)
    loc = SemanticLocator(model)
    result = loc.locate(tree, "something")
    assert result.node_ids == []
    assert result.confidence == 0.0


def test_parse_response_valid() -> None:
    raw = '{"node_ids": ["node_1"], "confidence": 0.75, "candidates": ["node_2"]}'
    result = _parse_response(raw)
    assert result.node_ids == ["node_1"]
    assert result.confidence == 0.75
    assert result.candidates == ["node_2"]


def test_parse_response_with_fences() -> None:
    raw = '```json\n{"node_ids": ["node_0"], "confidence": 1.0, "candidates": []}\n```'
    result = _parse_response(raw)
    assert result.node_ids == ["node_0"]


def test_parse_response_invalid_json() -> None:
    from docpatch.core.errors import LocateError

    with pytest.raises(LocateError):
        _parse_response("not json at all")
