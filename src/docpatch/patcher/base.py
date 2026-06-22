"""Operation Protocol and Patch/ValidationResult models."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from docpatch.core.node import Node
from docpatch.core.types import NodeRef


class Patch(BaseModel):
    target_id: NodeRef
    operation: str
    new_node: Node
    tokens_in: int = 0
    tokens_out: int = 0
    model_id: str = ""


class ValidationResult(BaseModel):
    ok: bool
    error: str = ""


@runtime_checkable
class Operation(Protocol):
    def apply(
        self,
        tree: object,
        target_id: NodeRef,
        instruction: str,
        model: object,
    ) -> Patch: ...

    def validate(self, patch: Patch, tree: object) -> ValidationResult: ...
