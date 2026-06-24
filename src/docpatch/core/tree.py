"""DocTree — root node + index + back-pointer map."""

from __future__ import annotations

from collections.abc import Iterator

from pydantic import BaseModel

from docpatch.core.node import Node
from docpatch.core.types import NodeRef, NodeType


def _build_index(
    node: Node,
    index: dict[NodeRef, Node],
    parents: dict[NodeRef, NodeRef | None],
    parent_id: NodeRef | None,
) -> None:
    index[node.id] = node
    parents[node.id] = parent_id
    for child in node.children:
        _build_index(child, index, parents, node.id)


class DocTree(BaseModel):
    root: Node
    _index: dict[NodeRef, Node] = {}
    _parents: dict[NodeRef, NodeRef | None] = {}

    def model_post_init(self, __context: object) -> None:
        idx: dict[NodeRef, Node] = {}
        pars: dict[NodeRef, NodeRef | None] = {}
        _build_index(self.root, idx, pars, None)
        object.__setattr__(self, "_index", idx)
        object.__setattr__(self, "_parents", pars)

    # ------------------------------------------------------------------
    # Lookup helpers
    # ------------------------------------------------------------------

    def get(self, node_id: NodeRef) -> Node | None:
        return self._index.get(node_id)

    def parent(self, node_id: NodeRef) -> Node | None:
        parent_id = self._parents.get(node_id)
        if parent_id is None:
            return None
        return self._index.get(parent_id)

    def ancestors(self, node_id: NodeRef) -> list[Node]:
        """Return ancestors from root down to (not including) node_id."""
        result: list[Node] = []
        cur_id: NodeRef | None = self._parents.get(node_id)
        while cur_id is not None:
            node = self._index[cur_id]
            result.append(node)
            cur_id = self._parents.get(cur_id)
        result.reverse()
        return result

    def walk(self, node: Node | None = None) -> Iterator[Node]:
        """Pre-order DFS over the tree."""
        root = node if node is not None else self.root
        stack = [root]
        while stack:
            cur = stack.pop()
            yield cur
            stack.extend(reversed(cur.children))

    def heading_skeleton(self) -> list[tuple[str, str]]:
        """Return [(node_id, heading_text)] for all heading/key nodes.

        Used by SemanticLocator — never includes body paragraph text.
        """
        result: list[tuple[str, str]] = []
        heading_types = {NodeType.HEADING, NodeType.KEY_VALUE, NodeType.OBJECT}
        for node in self.walk():
            if node.type in heading_types and node.content:
                result.append((node.id, node.content))
        return result

    def content_skeleton(self, preview_chars: int = 80) -> list[tuple[str, str, int]]:
        """Return [(node_id, label, depth)] for every addressable node.

        Depth reflects nesting so the locator can render an indented outline
        and pick the deepest specific match rather than a section heading.
        """
        result: list[tuple[str, str, int]] = []
        depth_map: dict[NodeRef, int] = {}

        def _depth(node_id: NodeRef) -> int:
            if node_id in depth_map:
                return depth_map[node_id]
            parent_id = self._parents.get(node_id)
            d = 0 if parent_id is None else _depth(parent_id) + 1
            depth_map[node_id] = d
            return d

        for node in self.walk():
            d = _depth(node.id)
            if node.type in {NodeType.HEADING, NodeType.KEY_VALUE, NodeType.OBJECT}:
                if node.content:
                    result.append((node.id, node.content, d))
            elif node.type in {NodeType.PARAGRAPH, NodeType.LIST_ITEM, NodeType.BLOCKQUOTE}:
                raw = node.content or (
                    node.raw_span.decode("utf-8", errors="replace") if node.raw_span else ""
                )
                flat = " ".join(raw.split())
                if flat:
                    result.append((node.id, f"[para: {flat[:preview_chars]}]", d))
            elif node.type == NodeType.CODE_BLOCK:
                raw = node.content or (
                    node.raw_span.decode("utf-8", errors="replace") if node.raw_span else ""
                )
                flat = " | ".join(ln.strip() for ln in raw.strip().splitlines() if ln.strip())
                result.append((node.id, f"[code: {flat[:preview_chars]}]", d))
            elif node.type == NodeType.TABLE:
                result.append((node.id, "[table]", d))
        return result

    def render_subtree(self, node_id: NodeRef) -> str:
        """Return a plain-text rendering of a node and all its descendants.

        Used to give the patcher model full section context rather than
        just the target node's own content field.
        """
        node = self.get(node_id)
        if node is None:
            return ""
        parts: list[str] = []
        for n in self.walk(node):
            # Prefer raw_span to preserve markdown formatting for the model.
            text = (
                n.raw_span.decode("utf-8", errors="replace") if n.raw_span else n.content or ""
            )
            if text.strip():
                parts.append(text.strip())
        return "\n".join(parts)

    def section_nodes(self, heading_id: NodeRef) -> list[Node]:
        """Return the sibling nodes that belong to a heading's logical section.

        For flat markdown trees (headings have no children), this is all siblings
        that follow the heading up to the next heading of equal or higher level.
        If the heading has children, those children are returned instead.
        """
        heading = self.get(heading_id)
        if heading is None:
            return []
        if heading.children:
            return list(self.walk(heading))[1:]

        parent = self.parent(heading_id)
        if parent is None:
            return []

        siblings = parent.children
        try:
            idx = next(i for i, n in enumerate(siblings) if n.id == heading_id)
        except StopIteration:
            return []

        # Determine heading depth from the node ID or content — headings in
        # markdown-it-py embed the level in the ID as "heading:…/slug#N".
        # We use a simple heuristic: compare content length as a proxy isn't
        # reliable, so we inspect subsequent headings by type only.
        result: list[Node] = []
        for sibling in siblings[idx + 1:]:
            if sibling.type == NodeType.HEADING:
                break
            result.append(sibling)
        return result

    def subtree_bytes(self, node_id: NodeRef) -> bytes | None:
        """Return raw_span of a node if available, else None."""
        node = self.get(node_id)
        if node is None:
            return None
        return node.raw_span

    def __len__(self) -> int:
        return len(self._index)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self._index
