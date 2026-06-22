"""SemanticLocator — uses an LLM on the content skeleton only (never full body)."""

from __future__ import annotations

import json

from docpatch.core.errors import LocateError
from docpatch.core.tree import DocTree
from docpatch.locator.base import LocateResult
from docpatch.models.base import ModelClient

_PROMPT_TEMPLATE = """\
You are a document locator. Given a document outline and an edit instruction,
identify which node(s) should be targeted.

DOCUMENT OUTLINE (each line is: alias<TAB>description):
{skeleton}

INSTRUCTION: {instruction}

Respond with JSON only, no prose:
{{"node_ids": ["<alias1>", ...], "confidence": 0.0-1.0, "candidates": []}}

Rules:
- node_ids and candidates MUST be aliases copied verbatim from the alias column above
  (e.g. "node_3"). Do NOT invent values or use the description text as an ID.
- confidence=1.0 only when the match is unambiguous.
- If uncertain, set confidence<0.7 and list all plausible aliases in candidates.
- Return an empty node_ids list if nothing matches.
"""


class SemanticLocator:
    """LLM-backed locator. Sends content skeleton with short aliases — robust to long IDs."""

    def __init__(self, model: ModelClient, max_tokens: int = 256) -> None:
        self._model = model
        self._max_tokens = max_tokens

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        skeleton = tree.content_skeleton(preview_chars=200)
        if not skeleton:
            return LocateResult(node_ids=[], confidence=0.0, method="semantic_no_skeleton")

        # Map short aliases → real node IDs so the model never has to copy long strings.
        alias_to_id = {f"node_{i}": nid for i, (nid, _) in enumerate(skeleton)}
        skeleton_text = "\n".join(
            f"  node_{i}\t{label}" for i, (_, label) in enumerate(skeleton)
        )
        prompt = _PROMPT_TEMPLATE.format(skeleton=skeleton_text, instruction=instruction)

        resp = self._model.complete(prompt, max_tokens=self._max_tokens)
        raw = _parse_response(resp.text)

        # Resolve aliases back to real node IDs; drop anything unrecognised.
        good_ids = [alias_to_id[a] for a in raw.node_ids if a in alias_to_id]
        good_candidates = [alias_to_id[a] for a in raw.candidates if a in alias_to_id]
        confidence = raw.confidence if good_ids else 0.0
        return LocateResult(
            node_ids=good_ids,
            confidence=confidence,
            candidates=good_candidates,
            method="semantic",
        )


def _parse_response(text: str) -> LocateResult:
    """Parse the model's JSON response into a LocateResult."""
    try:
        clean = text.strip()
        if clean.startswith("```"):
            clean = clean.split("\n", 1)[1]
            clean = clean.rsplit("```", 1)[0]
        data = json.loads(clean)
        return LocateResult(
            node_ids=data.get("node_ids", []),
            confidence=float(data.get("confidence", 0.0)),
            candidates=data.get("candidates", []),
            method="semantic",
        )
    except (json.JSONDecodeError, KeyError, ValueError) as exc:
        raise LocateError(
            LocateError.Kind.INVALID_INSTRUCTION,
            f"Model returned unparseable response: {exc}",
        ) from exc
