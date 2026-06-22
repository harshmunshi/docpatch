"""SidecarStorage — .dpx/ directory bundle, bundle layout v1.

Layout:
  .dpx/<doc_id>/
    meta.json       — DocMeta
    original        — raw source bytes
    tree.json       — serialized DocTree (node graph as JSON)
    patches/        — one JSON file per patch
"""

from __future__ import annotations

import json
from pathlib import Path

from docpatch.core.errors import StorageError
from docpatch.storage.base import DocMeta, DocPatchBundle


def _safe_join(base: Path, name: str) -> Path:
    """Prevent path traversal attacks."""
    resolved = (base / name).resolve()
    if not str(resolved).startswith(str(base.resolve())):
        raise StorageError(StorageError.Kind.PATH_TRAVERSAL, name)
    return resolved


class SidecarStorage:
    """Stores bundles as .dpx/ subdirectories next to (or at) a given root path."""

    BUNDLE_VERSION = "1"

    def __init__(self, root: str | Path, dir_name: str = ".dpx") -> None:
        self._root = Path(root).resolve()
        self._dir_name = dir_name

    def _bundle_dir(self, doc_id: str) -> Path:
        dpx = self._root / self._dir_name
        return _safe_join(dpx, doc_id)

    def save(self, doc_id: str, bundle: DocPatchBundle) -> None:
        bundle_dir = self._bundle_dir(doc_id)
        bundle_dir.mkdir(parents=True, exist_ok=True)

        (bundle_dir / "meta.json").write_text(
            bundle.meta.model_dump_json(indent=2), encoding="utf-8"
        )
        (bundle_dir / "original").write_bytes(bundle.original_bytes)
        (bundle_dir / "tree.json").write_text(bundle.tree_json, encoding="utf-8")

        patches_dir = bundle_dir / "patches"
        patches_dir.mkdir(exist_ok=True)
        for idx, patch in enumerate(bundle.patches):
            (patches_dir / f"{idx:06d}.json").write_text(
                json.dumps(patch, indent=2), encoding="utf-8"
            )

    def load(self, doc_id: str) -> DocPatchBundle:
        bundle_dir = self._bundle_dir(doc_id)
        if not bundle_dir.exists():
            raise StorageError(StorageError.Kind.NOT_FOUND, doc_id)

        meta = DocMeta.model_validate_json((bundle_dir / "meta.json").read_text())
        original_bytes = (bundle_dir / "original").read_bytes()
        tree_json = (bundle_dir / "tree.json").read_text(encoding="utf-8")

        patches_dir = bundle_dir / "patches"
        patches: list[dict] = []  # type: ignore[type-arg]
        if patches_dir.exists():
            for pf in sorted(patches_dir.glob("*.json")):
                patches.append(json.loads(pf.read_text()))

        return DocPatchBundle(
            meta=meta,
            original_bytes=original_bytes,
            tree_json=tree_json,
            patches=patches,
        )

    def list(self) -> list[DocMeta]:
        dpx = self._root / self._dir_name
        if not dpx.exists():
            return []
        metas: list[DocMeta] = []
        for meta_file in dpx.glob("*/meta.json"):
            try:
                metas.append(DocMeta.model_validate_json(meta_file.read_text()))
            except Exception:  # noqa: BLE001
                pass
        return metas
