# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- **Agentic CLI output** — replaced the silent `click.echo` flow with a rich step-by-step display (parse → locate → generate → splice → write), showing timing, token counts, the selected node's context, and a before/after diff panel on every run.
- **`.env` API key support** — `Settings` now reads `ANTHROPIC_API_KEY` and `OPENAI_API_KEY` directly from `.env`, so provider keys no longer need to be passed via `--api-key` or wrapped in `DOCPATCH_*` names.
- **OpenAI package** added as an optional extra (`docpatch[openai]`); `openai` v2 is now installed and registered in `pyproject.toml`.
- **`DocTree.section_nodes()`** — new helper that returns the nodes belonging to a heading's logical section: forward siblings up to the next heading for flat markdown trees, children for nested formats.
- **`LIST_ITEM` serialization** — `_render_patched_leaf` now handles `LIST_ITEM` nodes, emitting `{markup} {content}\n` so patched list items round-trip correctly.

### Changed

- **Smarter symbolic locator** — added a `scoped_section` pattern that understands `"in X section change Y"` phrasing: finds X's heading, collects its section content, walks to leaf nodes (`paragraph`, `heading`, `code_block`, `table_cell`), and scores by word overlap with the post-scope instruction. Dropped `bare_heading` confidence from `0.7` → `0.55` so context headings never short-circuit to the wrong target.
- **Hierarchical skeleton** — `content_skeleton` now returns `(node_id, label, depth)` tuples and covers paragraphs, list items, and blockquotes. The semantic locator renders an indented outline so the model picks the deepest specific match rather than a section heading.
- **Formatting-preserving patcher** — `target_content` sent to the model uses `raw_span` for non-code nodes (preserves bold, inline code, bullet markers) and `content` for `CODE_BLOCK` nodes (fence-stripped, since the serializer owns the fences). The prompt template has a code-block-specific branch that instructs the model to return raw code only.
- **Trailing whitespace preserved** — the patcher carries the original node's trailing newlines into the new node's metadata so `_render_patched_leaf` reproduces them exactly, preventing extra blank lines from breaking tight lists.
- **Markdown parser: language tag stored** — `fence` tokens now have their `info` field (e.g. `python`, `bash`) stored in node metadata, fixing the serializer which was silently dropping language tags on patched code blocks.

### Fixed

- **OpenAI client** — `complete()` now raises `ModelError` with a specific reason (content filter, refusal, empty finish reason) instead of returning `""` and exhausting all retries with a misleading `empty model response` error.
