"""DocPatch — surgical LLM document editing.

Convenience API:

    from docpatch import open_doc, edit_doc

    tree = open_doc("report.md")
    patched = edit_doc(tree, "Tighten the introduction", model=my_client)
"""

from __future__ import annotations

from pathlib import Path

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import DocFormat, NodeType
from docpatch.locator import CompositeLocator
from docpatch.models.base import ModelClient, ModelResponse
from docpatch.parsers import detect_format, get_parser
from docpatch.patcher.base import Patch
from docpatch.patcher.replace import ReplaceOperation
from docpatch.splicer import splice

__version__ = "0.1.0"

__all__ = [
    "DocFormat",
    "DocTree",
    "ModelClient",
    "ModelResponse",
    "Node",
    "NodeType",
    "Patch",
    "edit_doc",
    "open_doc",
]


def open_doc(path: str | Path) -> DocTree:
    """Parse a document file into a DocTree."""
    from typing import cast

    p = Path(path)
    data = p.read_bytes()
    fmt = detect_format(p, data)
    parser = get_parser(fmt)
    # get_parser returns a ModuleType; cast because mypy can't infer the parse signature
    return cast(DocTree, parser.parse(data))


def edit_doc(
    tree: DocTree,
    instruction: str,
    model: ModelClient,
    *,
    threshold: float = 0.6,
    max_retry: int = 3,
    max_tokens: int = 4096,
) -> DocTree:
    """Locate the target node, apply a replace patch, and return the updated tree."""
    locator = CompositeLocator(model=model, threshold=threshold, max_tokens=max_tokens)
    result = locator.locate(tree, instruction)
    if not result.node_ids:
        from docpatch.core.errors import LocateError

        raise LocateError(LocateError.Kind.NOT_FOUND, instruction)

    op = ReplaceOperation(max_retry=max_retry, max_tokens=max_tokens)
    patch = op.apply(tree, result.node_ids[0], instruction, model)
    return splice(tree, [patch])
