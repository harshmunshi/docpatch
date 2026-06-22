"""BLAKE3 fingerprints over canonicalized subtree content."""

from __future__ import annotations

import blake3


def compute_fingerprint(content: str | None, child_fingerprints: list[str]) -> str:
    """Stable fingerprint for a node.

    Combines the node's own content hash with an ordered list of child fingerprints,
    so any change anywhere in the subtree propagates upward.
    """
    h = blake3.blake3()
    if content:
        h.update(content.encode())
    for fp in child_fingerprints:
        h.update(fp.encode())
    return h.hexdigest()
