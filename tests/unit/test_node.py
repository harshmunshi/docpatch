"""Unit tests for core/node.py."""

from docpatch.core.node import Node
from docpatch.core.types import NodeType


def _make_node(nid: str = "paragraph:root/intro#0", content: str | None = "hello") -> Node:
    return Node(id=nid, type=NodeType.PARAGRAPH, content=content)


def test_node_fingerprint_auto() -> None:
    node = _make_node()
    assert node.fingerprint != ""


def test_node_fingerprint_changes_with_content() -> None:
    n1 = _make_node(content="hello")
    n2 = _make_node(content="world")
    assert n1.fingerprint != n2.fingerprint


def test_node_fingerprint_changes_with_children() -> None:
    child_a = Node(id="text:root/a#0", type=NodeType.TEXT, content="A")
    child_b = Node(id="text:root/b#0", type=NodeType.TEXT, content="B")
    parent_a = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, children=(child_a,))
    parent_b = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, children=(child_b,))
    assert parent_a.fingerprint != parent_b.fingerprint


def test_node_replace() -> None:
    node = _make_node(content="original")
    replaced = node.replace(content="updated")
    assert replaced.content == "updated"
    assert replaced.id == node.id
    assert replaced.type == node.type
    assert replaced.fingerprint != node.fingerprint


def test_node_immutable() -> None:
    node = _make_node()
    try:
        node.content = "mutate"  # type: ignore[misc]
        raise AssertionError("Should have raised")
    except AssertionError:
        raise
    except Exception:
        pass
