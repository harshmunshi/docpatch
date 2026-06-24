"""SemanticLocator — uses an LLM on the content skeleton only (never full body)."""

from __future__ import annotations

import json

from docpatch.core.errors import LocateError
from docpatch.core.tree import DocTree
from docpatch.locator.base import LocateResult
from docpatch.models.base import ModelClient

_PROMPT_TEMPLATE = """\
You are a document locator. Given an indented document outline and an edit instruction,
identify the single node that should be edited.

DOCUMENT OUTLINE (indentation = nesting depth; alias<TAB>label):
{skeleton}

INSTRUCTION: {instruction}

Respond with JSON only, no prose:
{{"node_ids": ["<alias>"], "confidence": 0.0-1.0, "candidates": []}}

Rules:
- node_ids MUST contain exactly one alias copied verbatim from the outline above.
- Pick the DEEPEST, MOST SPECIFIC node whose content matches what the instruction
  wants to change. If the instruction says "in X section change Y", pick the Y node
  inside X — not the X heading itself.
- A section heading is only the right answer if the instruction explicitly asks to
  rename the heading.
- confidence=1.0 only when the match is unambiguous.
- If uncertain, set confidence<0.7 and list all plausible aliases in candidates.
- Return an empty node_ids list if nothing matches.
"""


class SemanticLocator:
    """LLM-backed locator. Sends indented outline with short aliases."""

    def __init__(self, model: ModelClient, max_tokens: int = 256) -> None:
        self._model = model
        self._max_tokens = max_tokens

    def locate(self, tree: DocTree, instruction: str) -> LocateResult:
        skeleton = tree.content_skeleton(preview_chars=80)
        if not skeleton:
            return LocateResult(node_ids=[], confidence=0.0, method="semantic_no_skeleton")

        alias_to_id = {f"node_{i}": nid for i, (nid, _, _) in enumerate(skeleton)}
        skeleton_text = "\n".join(
            f"{'  ' * depth}node_{i}\t{label}" for i, (_, label, depth) in enumerate(skeleton)
        )
        prompt = _PROMPT_TEMPLATE.format(skeleton=skeleton_text, instruction=instruction)

        resp = self._model.complete(prompt, max_tokens=self._max_tokens)
        raw = _parse_response(resp.text)

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
