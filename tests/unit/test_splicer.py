"""Unit tests for splicer/splice.py."""

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType
from docpatch.patcher.base import Patch
from docpatch.splicer.splice import splice
from docpatch.splicer.validate import validate_splice


def _make_tree() -> DocTree:
    p1 = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="Original text")
    h1 = Node(id="heading:root/h#0", type=NodeType.HEADING, content="Title")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(h1, p1))
    return DocTree(root=root)


def test_splice_identity() -> None:
    tree = _make_tree()
    patched = splice(tree, [])
    assert patched.root.fingerprint == tree.root.fingerprint


def test_splice_replaces_node() -> None:
    tree = _make_tree()
    new_node = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="New text")
    patch = Patch(target_id="paragraph:root/p#0", operation="replace", new_node=new_node)
    patched = splice(tree, [patch])

    updated = patched.get("paragraph:root/p#0")
    assert updated is not None
    assert updated.content == "New text"


def test_splice_does_not_affect_other_nodes() -> None:
    tree = _make_tree()
    new_node = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="Changed")
    patch = Patch(target_id="paragraph:root/p#0", operation="replace", new_node=new_node)
    patched = splice(tree, [patch])

    heading = patched.get("heading:root/h#0")
    assert heading is not None
    assert heading.content == "Title"


def test_splice_fingerprint_changes_on_patch() -> None:
    tree = _make_tree()
    new_node = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="Different")
    patch = Patch(target_id="paragraph:root/p#0", operation="replace", new_node=new_node)
    patched = splice(tree, [patch])

    assert patched.root.fingerprint != tree.root.fingerprint


def test_validate_splice_ok() -> None:
    tree = _make_tree()
    new_node = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="Updated")
    patch = Patch(target_id="paragraph:root/p#0", operation="replace", new_node=new_node)
    patched = splice(tree, [patch])
    result = validate_splice(tree, patched, [patch])
    assert result.ok


def test_validate_splice_catches_missing_node() -> None:
    tree = _make_tree()
    # Create a patch for a non-existent ID
    ghost_node = Node(id="ghost:root/x#0", type=NodeType.PARAGRAPH, content="?")
    patch = Patch(target_id="ghost:root/x#0", operation="replace", new_node=ghost_node)
    # Manually build a patched tree without the ghost
    result = validate_splice(tree, tree, [patch])
    assert not result.ok
