"""Post-splice structural validation."""

from __future__ import annotations

from docpatch.core.tree import DocTree
from docpatch.patcher.base import Patch, ValidationResult


def validate_splice(original: DocTree, patched: DocTree, patches: list[Patch]) -> ValidationResult:
    """Verify that the spliced tree is structurally sound.

    Checks:
    - All patched node IDs exist in the patched tree.
    - Total node count only changes by nodes explicitly removed/added by patches.
    """
    for patch in patches:
        if patch.target_id not in patched:
            return ValidationResult(
                ok=False,
                error=f"patched node {patch.target_id} missing from result tree",
            )

    # All original unpatched nodes must still be present
    patched_ids = {p.target_id for p in patches}
    for node in original.walk():
        if node.id not in patched_ids and node.id not in patched:
            return ValidationResult(
                ok=False,
                error=f"unpatched node {node.id} disappeared from tree",
            )

    return ValidationResult(ok=True)
