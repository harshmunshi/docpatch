"""Locator Protocol and LocateResult."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from pydantic import BaseModel

from docpatch.core.types import NodeRef


class LocateResult(BaseModel):
    node_ids: list[NodeRef]
    confidence: float  # 0.0–1.0
    candidates: list[NodeRef] = []
    method: str = ""


@runtime_checkable
class Locator(Protocol):
    def locate(self, tree: object, instruction: str) -> LocateResult: ...
