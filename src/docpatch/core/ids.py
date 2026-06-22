"""Deterministic node ID generation.

Format: {type}:{parent_id}/{slug}#{ord}
Root has no parent, so root id is just "{type}:root".
"""

from __future__ import annotations

import re
import unicodedata


def _slugify(text: str, max_len: int = 40) -> str:
    """Convert text to a stable slug suitable for use in an ID."""
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text).strip("-")
    return text[:max_len] or "node"


def make_id(node_type: str, parent_id: str | None, text: str | None, ordinal: int) -> str:
    """Build a deterministic node ID.

    Args:
        node_type: NodeType value string.
        parent_id: ID of the parent node, or None for root.
        text: Heading text / object key / other slug source, or None.
        ordinal: Zero-based sibling position among nodes of the same type.
    """
    slug = _slugify(text) if text else f"n{ordinal}"
    if parent_id is None:
        return f"{node_type}:root"
    return f"{node_type}:{parent_id}/{slug}#{ordinal}"
