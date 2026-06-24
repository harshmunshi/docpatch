"""docpatch edit FILE INSTRUCTION — end-to-end edit command."""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import cast

import click
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from docpatch.config import Settings
from docpatch.core.errors import LocateError
from docpatch.core.tree import DocTree
from docpatch.locator import CompositeLocator
from docpatch.models.base import ModelClient
from docpatch.models.mock import MockModelClient
from docpatch.parsers import detect_format, get_parser
from docpatch.patcher.replace import ReplaceOperation, _build_breadcrumb
from docpatch.splicer import splice, validate_splice

console = Console()


def _step(n: int, label: str) -> None:
    console.print(f"\n[bold cyan]  Step {n}[/bold cyan]  [dim]─[/dim]  {label}")


def _ok(msg: str) -> None:
    console.print(f"  [green]✓[/green]  {msg}")


def _info(label: str, value: str) -> None:
    console.print(f"  [dim]{label}:[/dim]  {value}")


def _abort(msg: str) -> None:
    console.print(f"\n  [bold red]✗  {msg}[/bold red]")
    sys.exit(1)


@click.command()
@click.argument("file", type=click.Path(exists=True, dir_okay=False))
@click.argument("instruction")
@click.option("--model", "model_name", default="mock", help="Model provider: mock|anthropic|openai")
@click.option("--out", default=None, help="Output path (default: overwrite in-place)")
@click.option("--dry-run", is_flag=True, default=False, help="Print result, do not write.")
@click.option("--api-key", default=None, envvar="DOCPATCH_API_KEY", help="Provider API key.")
@click.pass_context
def edit(
    ctx: click.Context,
    file: str,
    instruction: str,
    model_name: str,
    out: str | None,
    dry_run: bool,
    api_key: str | None,
) -> None:
    """Edit FILE according to INSTRUCTION using an LLM."""
    settings = Settings()
    path = Path(file)

    console.print(Rule("[bold]DocPatch[/bold]", style="cyan"))
    console.print(
        Panel(f'[italic]"{instruction}"[/italic]', title="Instruction", border_style="dim")
    )

    # ── Step 1: Parse ──────────────────────────────────────────────────────────
    _step(1, "Parsing document")
    t0 = time.perf_counter()
    data = path.read_bytes()
    fmt = detect_format(path, data)
    parser = get_parser(fmt)
    tree = cast(DocTree, parser.parse(data))
    parse_ms = (time.perf_counter() - t0) * 1000

    _ok(f"Parsed [bold]{path.name}[/bold] as [bold]{fmt}[/bold]  ({parse_ms:.0f} ms)")
    _info("Nodes", str(len(tree)))
    _info("Format", fmt)

    # ── Step 2: Build model ────────────────────────────────────────────────────
    _step(2, "Initialising model")
    model = _build_model(model_name, api_key, settings)
    _ok(f"Using [bold]{model_name}[/bold] provider")

    # ── Step 3: Locate target ──────────────────────────────────────────────────
    _step(3, "Locating target node")
    locator = CompositeLocator(
        model=model,
        threshold=settings.semantic_locator_threshold,
        max_tokens=settings.max_tokens,
    )

    t0 = time.perf_counter()
    try:
        locate_result = locator.locate(tree, instruction)
    except LocateError as exc:
        _abort(str(exc))

    locate_ms = (time.perf_counter() - t0) * 1000

    if not locate_result.node_ids:
        console.print("  [yellow]⚠[/yellow]  No target found. Candidates:")
        for c in locate_result.candidates:
            console.print(f"       [dim]·[/dim] {c}")
        sys.exit(1)

    target_id = locate_result.node_ids[0]
    target_node = tree.get(target_id)
    assert target_node is not None

    _ok(
        f"Found [bold]{target_node.type}[/bold] node  ({locate_ms:.0f} ms,  confidence={locate_result.confidence:.2f})"
    )
    _info("Node ID", target_id)
    _info("Method", locate_result.method)

    # Show the breadcrumb context the model used
    breadcrumb = _build_breadcrumb(tree, target_id)
    if breadcrumb and breadcrumb != "(root)":
        _info("Context path", breadcrumb.replace("\n", "  /  "))

    # Show what content the model will see
    section_preview = tree.render_subtree(target_id)
    preview_lines = section_preview.strip().splitlines()
    preview_truncated = "\n".join(preview_lines[:6])
    if len(preview_lines) > 6:
        preview_truncated += f"\n[dim]… +{len(preview_lines) - 6} more lines[/dim]"

    console.print()
    console.print(
        Panel(
            preview_truncated or "[dim](empty)[/dim]",
            title=f"[dim]Section content sent to model  ·  {target_node.type}[/dim]",
            border_style="dim",
            padding=(0, 1),
        )
    )

    # ── Step 4: Generate patch ─────────────────────────────────────────────────
    _step(4, "Generating replacement")
    op = ReplaceOperation(max_retry=settings.max_retry, max_tokens=settings.max_tokens)

    t0 = time.perf_counter()
    patch = op.apply(tree, target_id, instruction, model)
    patch_ms = (time.perf_counter() - t0) * 1000

    _ok(
        f"Replacement generated  ({patch_ms:.0f} ms,  in={patch.tokens_in} tok,  out={patch.tokens_out} tok)"
    )

    before = (target_node.content or "").strip()
    after = (patch.new_node.content or "").strip()

    diff_table = Table.grid(padding=(0, 2))
    diff_table.add_column(style="dim", width=8)
    diff_table.add_column()
    diff_table.add_row(
        "[red]before[/red]", Text(before[:200] + ("…" if len(before) > 200 else ""), style="red")
    )
    diff_table.add_row(
        "[green]after[/green]", Text(after[:200] + ("…" if len(after) > 200 else ""), style="green")
    )

    console.print()
    console.print(Panel(diff_table, title="[dim]Diff[/dim]", border_style="dim", padding=(0, 1)))

    # ── Step 5: Splice ─────────────────────────────────────────────────────────
    _step(5, "Splicing patch into document")
    t0 = time.perf_counter()
    patched_tree = splice(tree, [patch])
    result = validate_splice(tree, patched_tree, [patch])
    splice_ms = (time.perf_counter() - t0) * 1000

    if not result.ok:
        _abort(f"Splice validation failed: {result.error}")

    _ok(f"Document spliced cleanly  ({splice_ms:.0f} ms)")

    output_bytes = cast(bytes, parser.serialize(patched_tree))

    # ── Step 6: Write ──────────────────────────────────────────────────────────
    _step(6, "Writing output")
    if dry_run:
        console.print()
        console.print(Rule("[dim]dry-run output[/dim]", style="dim"))
        console.print(output_bytes.decode("utf-8", errors="replace"))
        return

    out_path = Path(out) if out else path
    out_path.write_bytes(output_bytes)
    _ok(f"Wrote [bold]{len(output_bytes):,}[/bold] bytes → [bold]{out_path}[/bold]")

    total_ms = parse_ms + locate_ms + patch_ms + splice_ms
    console.print()
    console.print(Rule(f"[dim]done  ·  {total_ms:.0f} ms total[/dim]", style="dim"))


def _build_model(name: str, api_key: str | None, settings: Settings) -> ModelClient:
    if name == "mock":
        return MockModelClient()
    if name == "anthropic":
        from docpatch.models.anthropic import AnthropicClient

        return AnthropicClient(api_key=api_key or settings.anthropic_api_key)
    if name == "openai":
        from docpatch.models.openai import OpenAIClient

        return OpenAIClient(api_key=api_key or settings.openai_api_key)
    _abort(f"Unknown model: {name}. Use mock|anthropic|openai.")
    raise SystemExit(1)  # unreachable, satisfies type checker
