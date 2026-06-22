"""SymbolicLocator — regex/grammar patterns, zero LLM calls.

Patterns (evaluated in priority order):
1. JSON Pointer: "/foo/bar/0"
2. Quoted heading: 'the "Intro" section'
3. Heading path with /: "Installation/Requirements"
4. Ordinal reference: "first paragraph", "second heading"
5. Bare heading match (case-insensitive prefix)
"""

from __future__ import annotations

import re

from docpatch.core.tree import DocTree
from docpatch.core.types import NodeRef, NodeType
from docpatch.locator.base import LocateResult

_ORDINAL_MAP = {
    "first": 0,
    "second": 1,
    "third": 2,
    "fourth": 3,
    "fifth": 4,
    "sixth": 5,
    "seventh": 6,
    "eighth": 7,
    "ninth": 8,
    "tenth": 9,
}
_NODE_WORDS = {
    "paragraph": NodeType.PARAGRAPH,
    "heading": NodeType.HEADING,
    "section": NodeType.SECTION,
    "list": NodeType.LIST,
    "code": NodeType.CODE_BLOCK,
    "table": NodeType.TABLE,
}


def _nodes_by_type(tree: DocTree, node_type: NodeType) -> list[NodeRef]:
    return [n.id for n in tree.walk() if n.type == node_type]


class SymbolicLocator:
    """Pure-regex locator. Returns confidence=1.0 on unambiguous hit."""

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        # 1. JSON Pointer (starts with /)
        m = re.search(r'(/(?:[^"\s]+))', instruction)
        if m:
            pointer = m.group(1)
            # map pointer to a node id containing that path segment
            for node in tree.walk():
                if pointer in node.id or (node.content and pointer in node.content):
                    return LocateResult(node_ids=[node.id], confidence=1.0, method="json_pointer")

        # 2. Quoted heading
        m = re.search(r'"([^"]+)"', instruction)
        if m:
            target = m.group(1).lower()
            matches = [n.id for n in tree.walk() if n.content and n.content.lower() == target]
            if len(matches) == 1:
                return LocateResult(node_ids=matches, confidence=1.0, method="quoted_heading")
            if matches:
                return LocateResult(
                    node_ids=[matches[0]],
                    confidence=0.8,
                    candidates=matches,
                    method="quoted_heading_ambiguous",
                )

        # 3. Heading path "A/B"
        m = re.search(r"[\w ]+/[\w ]+", instruction)
        if m:
            parts = [p.strip().lower() for p in m.group(0).split("/")]
            for node in tree.walk():
                if node.content and node.content.lower() == parts[-1]:
                    ancestors = tree.ancestors(node.id)
                    ancestor_texts = [a.content.lower() for a in ancestors if a.content]
                    if any(p in ancestor_texts for p in parts[:-1]):
                        return LocateResult(
                            node_ids=[node.id], confidence=0.95, method="heading_path"
                        )

        # 4. Ordinal + type: "second heading", "first paragraph"
        for ordinal_word, idx in _ORDINAL_MAP.items():
            for type_word, node_type in _NODE_WORDS.items():
                if ordinal_word in instruction.lower() and type_word in instruction.lower():
                    candidates = _nodes_by_type(tree, node_type)
                    if idx < len(candidates):
                        return LocateResult(
                            node_ids=[candidates[idx]], confidence=0.9, method="ordinal"
                        )

        # 5. Bare heading match (case-insensitive)
        instr_lower = instruction.lower()
        heading_matches = [
            n.id
            for n in tree.walk()
            if n.type in (NodeType.HEADING, NodeType.KEY_VALUE)
            and n.content
            and n.content.lower() in instr_lower
        ]
        if len(heading_matches) == 1:
            return LocateResult(node_ids=heading_matches, confidence=0.7, method="bare_heading")
        if heading_matches:
            return LocateResult(
                node_ids=[heading_matches[0]],
                confidence=0.5,
                candidates=heading_matches,
                method="bare_heading_ambiguous",
            )

        return LocateResult(node_ids=[], confidence=0.0, method="symbolic_miss")
