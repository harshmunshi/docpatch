"""CLI visualizer for a DocPatch DocTree.

Usage:
    uv run python visualize_tree.py <file> [--max-content 60] [--no-ids] [--no-fp]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from docpatch.core.node import Node
from docpatch.core.tree import DocTree
from docpatch.parsers import detect_format

# ANSI colours (gracefully degraded when not a tty)
_USE_COLOR = sys.stdout.isatty()

_COLORS: dict[str, str] = {
    "document":      "\033[1;37m",   # bold white
    "section":       "\033[1;34m",   # bold blue
    "heading":       "\033[1;33m",   # bold yellow
    "paragraph":     "\033[0;37m",   # white
    "list":          "\033[0;36m",   # cyan
    "list_item":     "\033[0;36m",
    "blockquote":    "\033[0;35m",   # magenta
    "code_block":    "\033[0;32m",   # green
    "code_inline":   "\033[0;32m",
    "table":         "\033[0;34m",   # blue
    "table_row":     "\033[0;34m",
    "table_cell":    "\033[0;34m",
    "inline":        "\033[0;90m",   # dark grey
    "text":          "\033[0;90m",
    "object":        "\033[1;35m",   # bold magenta
    "array":         "\033[1;36m",   # bold cyan
    "key_value":     "\033[0;33m",   # yellow
    "string":        "\033[0;32m",
    "number":        "\033[0;31m",   # red
    "boolean":       "\033[0;31m",
    "null":          "\033[0;31m",
}
_RESET = "\033[0m"


def _color(node_type: str, text: str) -> str:
    if not _USE_COLOR:
        return text
    return _COLORS.get(node_type, "") + text + _RESET


def _truncate(s: str, maxlen: int) -> str:
    s = s.replace("\n", "\\n")
    return s if len(s) <= maxlen else s[: maxlen - 1] + "…"


def _print_node(
    node: Node,
    prefix: str,
    is_last: bool,
    *,
    max_content: int,
    show_ids: bool,
    show_fp: bool,
) -> None:
    connector = "└── " if is_last else "├── "
    child_prefix = prefix + ("    " if is_last else "│   ")

    # Build the label
    label_parts = [_color(str(node.type), str(node.type))]

    if show_ids:
        short_id = node.id if len(node.id) <= 40 else "…" + node.id[-38:]
        label_parts.append(f"\033[2m[{short_id}]\033[0m" if _USE_COLOR else f"[{short_id}]")

    if node.content is not None:
        snippet = _truncate(node.content, max_content)
        label_parts.append(
            f'\033[0;90m"{snippet}"\033[0m' if _USE_COLOR else f'"{snippet}"'
        )

    if show_fp and node.fingerprint:
        fp_short = node.fingerprint[:8]
        label_parts.append(
            f"\033[2m#{fp_short}\033[0m" if _USE_COLOR else f"#{fp_short}"
        )

    meta = ""
    if node.metadata:
        interesting = {k: v for k, v in node.metadata.items() if k not in ("level",)}
        if "level" in node.metadata:
            meta += f" L{node.metadata['level']}"
        if interesting:
            meta += " " + " ".join(f"{k}={v}" for k, v in list(interesting.items())[:3])

    label = " ".join(label_parts) + meta
    print(prefix + connector + label)

    children = list(node.children)
    for i, child in enumerate(children):
        _print_node(
            child,
            child_prefix,
            is_last=(i == len(children) - 1),
            max_content=max_content,
            show_ids=show_ids,
            show_fp=show_fp,
        )


def visualize(tree: DocTree, *, max_content: int = 60, show_ids: bool = True, show_fp: bool = False) -> None:
    """Print a DocTree to stdout as an ASCII tree."""
    node_count = len(tree)
    print(f"DocTree  nodes={node_count}  root={tree.root.id!r}")
    print("│")
    _print_node(
        tree.root,
        "",
        is_last=True,
        max_content=max_content,
        show_ids=show_ids,
        show_fp=show_fp,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Visualize a DocPatch DocTree")
    parser.add_argument("file", help="Document file to parse and visualize")
    parser.add_argument("--max-content", type=int, default=60, metavar="N",
                        help="Max chars of node content to show (default 60)")
    parser.add_argument("--no-ids", action="store_true", help="Hide node IDs")
    parser.add_argument("--fp", action="store_true", help="Show fingerprint prefix")
    args = parser.parse_args()

    path = Path(args.file)
    if not path.exists():
        sys.exit(f"error: file not found: {path}")

    data = path.read_bytes()
    fmt = detect_format(path.name)

    if fmt.value == "markdown":
        from docpatch.parsers.markdown import parse
    elif fmt.value == "json":
        from docpatch.parsers.json_parser import parse  # type: ignore[no-redef]
    else:
        sys.exit(f"error: unsupported format '{fmt}' — only markdown and json for now")

    tree = parse(data)
    visualize(tree, max_content=args.max_content, show_ids=not args.no_ids, show_fp=args.fp)


if __name__ == "__main__":
    main()
