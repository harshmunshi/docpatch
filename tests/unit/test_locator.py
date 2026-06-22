"""Unit tests for the symbolic locator."""

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType
from docpatch.locator.symbolic import SymbolicLocator


def _make_tree() -> DocTree:
    intro = Node(id="heading:root/intro#0", type=NodeType.HEADING, content="Introduction")
    body = Node(id="paragraph:root/body#0", type=NodeType.PARAGRAPH, content="Body paragraph")
    conclusion = Node(id="heading:root/conclusion#1", type=NodeType.HEADING, content="Conclusion")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(intro, body, conclusion))
    return DocTree(root=root)


def test_symbolic_quoted_heading() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, 'Rewrite the "Introduction" section')
    assert result.node_ids == ["heading:root/intro#0"]
    assert result.confidence >= 0.8


def test_symbolic_bare_heading() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "shorten the Conclusion section")
    assert result.node_ids


def test_symbolic_ordinal() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "rewrite the first heading")
    assert result.node_ids
    assert result.node_ids[0] == "heading:root/intro#0"


def test_symbolic_no_match() -> None:
    tree = _make_tree()
    loc = SymbolicLocator()
    result = loc.locate(tree, "xyzzy quux frobnitz")
    assert result.confidence == 0.0
    assert result.node_ids == []
