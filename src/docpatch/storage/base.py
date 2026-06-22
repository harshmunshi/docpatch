"""StorageAdapter Protocol + bundle/meta models."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel

from docpatch.core.types import DocFormat


class DocMeta(BaseModel):
    doc_id: str
    format: DocFormat
    title: str = ""
    created_at: str = ""
    updated_at: str = ""
    patch_count: int = 0


class DocPatchBundle(BaseModel):
    """On-disk bundle layout v1. Canonical format for all storage adapters."""

    meta: DocMeta
    original_bytes: bytes
    tree_json: str
    patches: list[dict[str, Any]] = []


@runtime_checkable
class StorageAdapter(Protocol):
    def save(self, doc_id: str, bundle: DocPatchBundle) -> None: ...
    def load(self, doc_id: str) -> DocPatchBundle: ...
    def list(self) -> list[DocMeta]: ...
