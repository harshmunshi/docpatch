"""Unit tests for core/tree.py."""

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType


def _simple_tree() -> DocTree:
    child1 = Node(id="heading:root/intro#0", type=NodeType.HEADING, content="Intro")
    child2 = Node(id="paragraph:root/body#0", type=NodeType.PARAGRAPH, content="Body text")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(child1, child2))
    return DocTree(root=root)


def test_tree_get() -> None:
    tree = _simple_tree()
    node = tree.get("heading:root/intro#0")
    assert node is not None
    assert node.content == "Intro"


def test_tree_get_missing() -> None:
    tree = _simple_tree()
    assert tree.get("nonexistent") is None


def test_tree_parent() -> None:
    tree = _simple_tree()
    parent = tree.parent("heading:root/intro#0")
    assert parent is not None
    assert parent.id == "document:root"


def test_tree_parent_of_root() -> None:
    tree = _simple_tree()
    assert tree.parent("document:root") is None


def test_tree_walk_order() -> None:
    tree = _simple_tree()
    ids = [n.id for n in tree.walk()]
    assert ids[0] == "document:root"
    assert "heading:root/intro#0" in ids
    assert "paragraph:root/body#0" in ids


def test_tree_ancestors() -> None:
    grandchild = Node(id="text:heading:root/intro#0/word#0", type=NodeType.TEXT, content="hi")
    child = Node(
        id="heading:root/intro#0",
        type=NodeType.HEADING,
        content="Intro",
        children=(grandchild,),
    )
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(child,))
    tree = DocTree(root=root)
    ancestors = tree.ancestors("text:heading:root/intro#0/word#0")
    ancestor_ids = [a.id for a in ancestors]
    assert "document:root" in ancestor_ids
    assert "heading:root/intro#0" in ancestor_ids


def test_tree_heading_skeleton() -> None:
    tree = _simple_tree()
    skeleton = tree.heading_skeleton()
    assert any(nid == "heading:root/intro#0" for nid, _ in skeleton)


def test_tree_len() -> None:
    tree = _simple_tree()
    assert len(tree) == 3


def test_tree_contains() -> None:
    tree = _simple_tree()
    assert "document:root" in tree
    assert "nonexistent" not in tree
