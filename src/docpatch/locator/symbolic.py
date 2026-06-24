"""SymbolicLocator — regex/grammar patterns, zero LLM calls.

Patterns (evaluated in priority order):
1. JSON Pointer: "/foo/bar/0"
2. Quoted heading: 'the "Intro" section'
3. Heading path with /: "Installation/Requirements"
4. Scoped section: "in the X section change Y" → find Y within X's subtree
5. Ordinal reference: "first paragraph", "second heading"
6. Bare heading match (case-insensitive) — confidence 0.55 so it falls through
   to semantic when nothing else matches; semantic is authoritative for body nodes.
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

# "in (the) X section/area/part ..."
_SCOPE_RE = re.compile(
    r"\bin\s+(?:the\s+)?(['\"]?)(.+?)\1\s+(?:section|area|part|heading)\b",
    re.IGNORECASE,
)


def _nodes_by_type(tree: DocTree, node_type: NodeType) -> list[NodeRef]:
    return [n.id for n in tree.walk() if n.type == node_type]


def _find_heading(tree: DocTree, name: str) -> NodeRef | None:
    name_l = name.strip().lower()
    for node in tree.walk():
        if node.type in (NodeType.HEADING, NodeType.KEY_VALUE) and node.content:
            if node.content.lower() == name_l or node.content.lower().startswith(name_l):
                return node.id
    return None


class SymbolicLocator:
    """Pure-regex locator. Returns confidence=1.0 on unambiguous hit."""

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        instr_lower = instruction.lower()

        # 1. JSON Pointer (starts with /)
        m = re.search(r'(/(?:[^"\s]+))', instruction)
        if m:
            pointer = m.group(1)
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

        # 4. Scoped section: "in X section ... change Y" → search within X's content
        scope_m = _SCOPE_RE.search(instruction)
        if scope_m:
            section_name = scope_m.group(2).strip()
            section_id = _find_heading(tree, section_name)
            if section_id is not None:
                # For flat trees (markdown), scan forward siblings; for nested trees, walk children.
                section_content = tree.section_nodes(section_id)
                after_scope = instruction[scope_m.end():].lower()
                instr_words = set(re.findall(r"\w+", after_scope))
                # Stopwords that are too common to be useful for scoring
                _STOP = {"the", "a", "an", "to", "of", "in", "and", "or", "change",
                         "update", "replace", "modify", "rename", "content", "text"}
                instr_words -= _STOP
                _LEAF_TYPES = {
                    NodeType.PARAGRAPH, NodeType.HEADING, NodeType.CODE_BLOCK,
                    NodeType.TABLE_CELL, NodeType.INLINE,
                }
                candidates_pool = []
                for n in section_content:
                    # Walk the full subtree and score leaf-ish nodes only
                    for leaf in tree.walk(n):
                        if leaf.type not in _LEAF_TYPES:
                            continue
                        raw = leaf.content or (
                            leaf.raw_span.decode("utf-8", errors="replace") if leaf.raw_span else ""
                        )
                        text = raw.lower()
                        if not text.strip():
                            continue
                        words = set(re.findall(r"\w+", text)) - _STOP
                        overlap = len(words & instr_words)
                        if overlap:
                            candidates_pool.append((overlap, leaf.id))
                scored = sorted(candidates_pool, key=lambda x: -x[0])
                if scored:
                    return LocateResult(
                        node_ids=[scored[0][1]],
                        confidence=0.85,
                        candidates=[nid for _, nid in scored[1:4]],
                        method="scoped_section",
                    )
                # Section found but no content match — return the section heading as fallback
                return LocateResult(
                    node_ids=[section_id], confidence=0.6, method="scoped_section_heading"
                )

        # 5. Ordinal + type: "second heading", "first paragraph"
        for ordinal_word, idx in _ORDINAL_MAP.items():
            for type_word, node_type in _NODE_WORDS.items():
                if ordinal_word in instr_lower and type_word in instr_lower:
                    candidates = _nodes_by_type(tree, node_type)
                    if idx < len(candidates):
                        return LocateResult(
                            node_ids=[candidates[idx]], confidence=0.9, method="ordinal"
                        )

        # 6. Bare heading match — confidence 0.55 (below default threshold 0.6) so the
        #    composite locator always escalates to semantic for non-specific matches.
        heading_matches = [
            n.id
            for n in tree.walk()
            if n.type in (NodeType.HEADING, NodeType.KEY_VALUE)
            and n.content
            and n.content.lower() in instr_lower
        ]
        if len(heading_matches) == 1:
            return LocateResult(node_ids=heading_matches, confidence=0.55, method="bare_heading")
        if heading_matches:
            return LocateResult(
                node_ids=[heading_matches[0]],
                confidence=0.4,
                candidates=heading_matches,
                method="bare_heading_ambiguous",
            )

        return LocateResult(node_ids=[], confidence=0.0, method="symbolic_miss")
