"""Unit tests for storage adapters."""

import tempfile

import pytest

from docpatch.core.errors import StorageError
from docpatch.core.types import DocFormat
from docpatch.storage.base import DocMeta, DocPatchBundle
from docpatch.storage.in_memory import InMemoryStorage
from docpatch.storage.sidecar import SidecarStorage


def _bundle(doc_id: str = "doc1") -> DocPatchBundle:
    return DocPatchBundle(
        meta=DocMeta(doc_id=doc_id, format=DocFormat.MARKDOWN, title="Test"),
        original_bytes=b"# Hello\n",
        tree_json="{}",
    )


class TestInMemoryStorage:
    def test_save_and_load(self) -> None:
        store = InMemoryStorage()
        b = _bundle()
        store.save("doc1", b)
        loaded = store.load("doc1")
        assert loaded.meta.doc_id == "doc1"

    def test_load_missing(self) -> None:
        store = InMemoryStorage()
        with pytest.raises(StorageError) as exc:
            store.load("missing")
        assert exc.value.kind == StorageError.Kind.NOT_FOUND

    def test_list(self) -> None:
        store = InMemoryStorage()
        store.save("a", _bundle("a"))
        store.save("b", _bundle("b"))
        metas = store.list()
        ids = {m.doc_id for m in metas}
        assert {"a", "b"} == ids

    def test_overwrite(self) -> None:
        store = InMemoryStorage()
        store.save("doc1", _bundle())
        b2 = _bundle()
        b2 = b2.model_copy(update={"original_bytes": b"new"})
        store.save("doc1", b2)
        loaded = store.load("doc1")
        assert loaded.original_bytes == b"new"


class TestSidecarStorage:
    def test_save_and_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SidecarStorage(tmp)
            store.save("doc1", _bundle())
            loaded = store.load("doc1")
            assert loaded.meta.doc_id == "doc1"
            assert loaded.original_bytes == b"# Hello\n"

    def test_load_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SidecarStorage(tmp)
            with pytest.raises(StorageError) as exc:
                store.load("no_such_doc")
            assert exc.value.kind == StorageError.Kind.NOT_FOUND

    def test_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SidecarStorage(tmp)
            store.save("a", _bundle("a"))
            store.save("b", _bundle("b"))
            ids = {m.doc_id for m in store.list()}
            assert ids == {"a", "b"}

    def test_path_traversal_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = SidecarStorage(tmp)
            with pytest.raises(StorageError) as exc:
                store.load("../../etc/passwd")
            assert exc.value.kind == StorageError.Kind.PATH_TRAVERSAL
