"""CompositeLocator — symbolic first, semantic as fallback."""

from __future__ import annotations

from docpatch.core.tree import DocTree
from docpatch.locator.base import LocateResult
from docpatch.locator.semantic import SemanticLocator
from docpatch.locator.symbolic import SymbolicLocator
from docpatch.models.base import ModelClient


class CompositeLocator:
    """Tries symbolic locator; falls back to semantic if confidence < threshold."""

    def __init__(
        self,
        model: ModelClient,
        threshold: float = 0.6,
        max_tokens: int = 256,
    ) -> None:
        self._symbolic = SymbolicLocator()
        self._semantic = SemanticLocator(model, max_tokens=max_tokens)
        self._threshold = threshold

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        result = self._symbolic.locate(tree, instruction)
        if result.confidence >= self._threshold and result.node_ids:
            return result
        # symbolic miss — escalate to semantic
        semantic_result = self._semantic.locate(tree, instruction)
        # merge candidates
        all_candidates = list(dict.fromkeys(result.candidates + semantic_result.candidates))
        return LocateResult(
            node_ids=semantic_result.node_ids,
            confidence=semantic_result.confidence,
            candidates=all_candidates,
            method=f"composite({result.method}→{semantic_result.method})",
        )
