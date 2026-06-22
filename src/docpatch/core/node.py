"""Node — the fundamental unit of a DocTree."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

from docpatch.core.fingerprint import compute_fingerprint
from docpatch.core.types import NodeType


class Node(BaseModel, frozen=True):
    """Immutable node in a DocTree.

    raw_span stores the original source bytes for lossless round-trip: unchanged nodes are
    serialized by emitting raw_span verbatim. Only patched nodes need to generate new bytes.
    """

    id: str
    type: NodeType
    children: tuple[Node, ...] = Field(default_factory=tuple)
    content: str | None = None
    raw_span: bytes | None = None
    fingerprint: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _fill_fingerprint(self) -> Node:
        if self.fingerprint:
            return self
        fp = compute_fingerprint(self.content, [c.fingerprint for c in self.children])
        object.__setattr__(self, "fingerprint", fp)
        return self

    def replace(self, **kwargs: Any) -> Node:
        """Return a new Node with selected fields replaced."""
        data = self.model_dump(exclude={"fingerprint"})
        data.update(kwargs)
        data.pop("fingerprint", None)
        return Node(**data)
