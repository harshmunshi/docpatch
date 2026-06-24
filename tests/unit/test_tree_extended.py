"""Extended unit tests for core/tree.py — covers content_skeleton, render_subtree, section_nodes."""

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import NodeType


def _md_tree() -> DocTree:
    """Simulate a flat markdown tree: heading + paragraph + list + code block + table."""
    para = Node(id="paragraph:root/intro#0", type=NodeType.PARAGRAPH, content="Intro text.")
    item = Node(
        id="paragraph:list_item:root/li#0/text#0",
        type=NodeType.PARAGRAPH,
        content="List item text",
        raw_span=b"- List item text\n",
    )
    list_item = Node(
        id="list_item:root/li#0",
        type=NodeType.LIST_ITEM,
        content="List item text",
        raw_span=b"- List item text\n",
        children=(item,),
    )
    lst = Node(id="list:root/list#0", type=NodeType.LIST, children=(list_item,))
    code = Node(
        id="code_block:root/code#0",
        type=NodeType.CODE_BLOCK,
        content="print('hi')",
        metadata={"markup": "```", "info": "python"},
    )
    table = Node(id="table:root/table#0", type=NodeType.TABLE)
    heading = Node(id="heading:root/h#0", type=NodeType.HEADING, content="Section")
    root = Node(
        id="document:root",
        type=NodeType.DOCUMENT,
        children=(heading, para, lst, code, table),
    )
    return DocTree(root=root)


# ── content_skeleton ────────────────────────────────────────────────────────


def test_content_skeleton_returns_triples() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    assert all(len(entry) == 3 for entry in skeleton)


def test_content_skeleton_includes_heading() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    labels = [label for _, label, _ in skeleton]
    assert "Section" in labels


def test_content_skeleton_includes_paragraph() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    labels = [label for _, label, _ in skeleton]
    assert any("[para:" in lbl for lbl in labels)


def test_content_skeleton_includes_code_block() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    labels = [label for _, label, _ in skeleton]
    assert any("[code:" in lbl for lbl in labels)


def test_content_skeleton_includes_table() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    labels = [label for _, label, _ in skeleton]
    assert "[table]" in labels


def test_content_skeleton_depth_root_children_zero() -> None:
    tree = _md_tree()
    skeleton = tree.content_skeleton()
    heading_entry = next((e for e in skeleton if e[1] == "Section"), None)
    assert heading_entry is not None
    assert heading_entry[2] == 1  # child of document (depth 1)


# ── render_subtree ──────────────────────────────────────────────────────────


def test_render_subtree_missing_node() -> None:
    tree = _md_tree()
    assert tree.render_subtree("nonexistent") == ""


def test_render_subtree_leaf() -> None:
    tree = _md_tree()
    text = tree.render_subtree("paragraph:root/intro#0")
    assert "Intro text" in text


def test_render_subtree_uses_raw_span_when_present() -> None:
    tree = _md_tree()
    text = tree.render_subtree("list_item:root/li#0")
    assert "List item text" in text


def test_render_subtree_code_block() -> None:
    tree = _md_tree()
    text = tree.render_subtree("code_block:root/code#0")
    assert "print" in text


# ── section_nodes ───────────────────────────────────────────────────────────


def _section_tree() -> DocTree:
    """heading → paragraph → heading (stops section), paragraph (outside)."""
    h1 = Node(id="heading:root/intro#0", type=NodeType.HEADING, content="Intro")
    p1 = Node(id="paragraph:root/p1#0", type=NodeType.PARAGRAPH, content="First para.")
    p2 = Node(id="paragraph:root/p2#1", type=NodeType.PARAGRAPH, content="Second para.")
    h2 = Node(id="heading:root/end#1", type=NodeType.HEADING, content="End")
    p3 = Node(id="paragraph:root/p3#2", type=NodeType.PARAGRAPH, content="Outside.")
    root = Node(
        id="document:root",
        type=NodeType.DOCUMENT,
        children=(h1, p1, p2, h2, p3),
    )
    return DocTree(root=root)


def test_section_nodes_stops_at_next_heading() -> None:
    tree = _section_tree()
    nodes = tree.section_nodes("heading:root/intro#0")
    ids = [n.id for n in nodes]
    assert "paragraph:root/p1#0" in ids
    assert "paragraph:root/p2#1" in ids
    assert "heading:root/end#1" not in ids
    assert "paragraph:root/p3#2" not in ids


def test_section_nodes_missing_heading() -> None:
    tree = _section_tree()
    assert tree.section_nodes("nonexistent") == []


def test_section_nodes_no_parent() -> None:
    root = Node(id="document:root", type=NodeType.DOCUMENT)
    tree = DocTree(root=root)
    assert tree.section_nodes("document:root") == []


def test_section_nodes_nested_heading_uses_children() -> None:
    child = Node(id="paragraph:root/h#0/p#0", type=NodeType.PARAGRAPH, content="nested")
    h = Node(id="heading:root/h#0", type=NodeType.HEADING, content="H", children=(child,))
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(h,))
    tree = DocTree(root=root)
    nodes = tree.section_nodes("heading:root/h#0")
    assert len(nodes) == 1
    assert nodes[0].id == "paragraph:root/h#0/p#0"


# ── subtree_bytes ───────────────────────────────────────────────────────────


def test_subtree_bytes_returns_raw_span() -> None:
    node = Node(
        id="paragraph:root/p#0",
        type=NodeType.PARAGRAPH,
        content="hi",
        raw_span=b"hi\n",
    )
    root = Node(id="document:root", type=NodeType.DOCUMENT, children=(node,))
    tree = DocTree(root=root)
    assert tree.subtree_bytes("paragraph:root/p#0") == b"hi\n"


def test_subtree_bytes_missing_node() -> None:
    root = Node(id="document:root", type=NodeType.DOCUMENT)
    tree = DocTree(root=root)
    assert tree.subtree_bytes("nonexistent") is None
