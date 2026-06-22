"""splice(tree, patches) -> DocTree — pure function, no model calls.

Identity law: splice(tree, []) == tree (same fingerprint on root).
"""

from __future__ import annotations

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.patcher.base import Patch


def splice(tree: DocTree, patches: list[Patch]) -> DocTree:
    """Apply patches to the tree and return a new DocTree.

    Patches are applied by node ID. A node not targeted by any patch is returned
    unchanged (same object, raw_span intact → lossless serialization).
    """
    if not patches:
        return tree

    patch_map: dict[str, Node] = {p.target_id: p.new_node for p in patches}
    new_root = _splice_node(tree.root, patch_map)
    return DocTree(root=new_root)


def _splice_node(node: Node, patch_map: dict[str, Node]) -> Node:
    if node.id in patch_map:
        return patch_map[node.id]
    if not node.children:
        return node
    new_children = tuple(_splice_node(child, patch_map) for child in node.children)
    if new_children == node.children:
        return node
    # rebuild parent with updated children (fingerprint recomputed by model_validator)
    return node.replace(children=new_children, raw_span=None)
