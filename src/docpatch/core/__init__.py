"""Core domain types: Node, DocTree, IDs, fingerprints."""

from docpatch.core.errors import (
    DocPatchError,
    LocateError,
    ModelError,
    ParseError,
    PatchError,
    SpliceError,
    StorageError,
    ValidationError,
)
from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.core.types import DocFormat, NodeRef, NodeType

__all__ = [
    "DocPatchError",
    "DocTree",
    "DocFormat",
    "LocateError",
    "ModelError",
    "Node",
    "NodeRef",
    "NodeType",
    "ParseError",
    "PatchError",
    "SpliceError",
    "StorageError",
    "ValidationError",
]
