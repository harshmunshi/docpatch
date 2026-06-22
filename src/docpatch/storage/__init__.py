"""Storage adapters."""

from docpatch.storage.base import DocMeta, DocPatchBundle, StorageAdapter
from docpatch.storage.in_memory import InMemoryStorage
from docpatch.storage.sidecar import SidecarStorage

__all__ = [
    "DocMeta",
    "DocPatchBundle",
    "InMemoryStorage",
    "SidecarStorage",
    "StorageAdapter",
]
