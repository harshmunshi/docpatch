"""Unit tests for patcher/replace.py."""

import pytest

from docpatch.core.errors import PatchError
from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType
from docpatch.models.mock import MockModelClient
from docpatch.patcher.replace import ReplaceOperation


def _make_tree() -> DocTree:
    para = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content="Old content.")
    heading = Node(id="heading:root/h#0", type=NodeType.HEADING, content="Title")
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(heading, para))
    return DocTree(root=root)


def test_replace_basic() -> None:
    tree = _make_tree()
    model = MockModelClient("New content.")
    op = ReplaceOperation()
    patch = op.apply(tree, "paragraph:root/p#0", "make it better", model)
    assert patch.operation == "replace"
    assert patch.new_node.content == "New content."
    assert patch.new_node.type == NodeType.PARAGRAPH


def test_replace_validation_ok() -> None:
    tree = _make_tree()
    model = MockModelClient("Updated.")
    op = ReplaceOperation()
    patch = op.apply(tree, "paragraph:root/p#0", "update it", model)
    result = op.validate(patch, tree)
    assert result.ok


def test_replace_target_not_found() -> None:
    tree = _make_tree()
    model = MockModelClient("x")
    op = ReplaceOperation()
    with pytest.raises(PatchError) as exc:
        op.apply(tree, "nonexistent:node#0", "do something", model)
    assert exc.value.kind == PatchError.Kind.TARGET_NOT_FOUND


def test_replace_empty_response_retries_and_fails() -> None:
    tree = _make_tree()
    model = MockModelClient("")  # always returns empty
    op = ReplaceOperation(max_retry=2)
    with pytest.raises(PatchError) as exc:
        op.apply(tree, "paragraph:root/p#0", "update", model)
    assert exc.value.kind == PatchError.Kind.MAX_RETRY_EXCEEDED


def test_validate_catches_empty_content() -> None:
    tree = _make_tree()
    op = ReplaceOperation()
    empty_node = Node(id="paragraph:root/p#0", type=NodeType.PARAGRAPH, content=None)
    from docpatch.patcher.base import Patch

    patch = Patch(target_id="paragraph:root/p#0", operation="replace", new_node=empty_node)
    result = op.validate(patch, tree)
    assert not result.ok
