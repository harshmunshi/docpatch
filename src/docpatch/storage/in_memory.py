"""InMemoryStorage — dict-backed, single-process, not thread-safe (documented)."""

from __future__ import annotations

from docpatch.core.errors import StorageError
from docpatch.storage.base import DocMeta, DocPatchBundle


class InMemoryStorage:
    """Not thread-safe. Suitable for tests and single-request CLI usage."""

    def __init__(self) -> None:
        self._store: dict[str, DocPatchBundle] = {}

    def save(self, doc_id: str, bundle: DocPatchBundle) -> None:
        self._store[doc_id] = bundle

    def load(self, doc_id: str) -> DocPatchBundle:
        if doc_id not in self._store:
            raise StorageError(StorageError.Kind.NOT_FOUND, doc_id)
        return self._store[doc_id]

    def list(self) -> list[DocMeta]:
        return [b.meta for b in self._store.values()]

    def delete(self, doc_id: str) -> None:
        if doc_id not in self._store:
            raise StorageError(StorageError.Kind.NOT_FOUND, doc_id)
        del self._store[doc_id]
