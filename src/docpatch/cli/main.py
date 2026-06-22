"""CLI root group and shared options."""

from __future__ import annotations

import sys

import click
import structlog

from docpatch.cli.edit import edit


@click.group()
@click.option("--verbose", is_flag=True, default=False, help="Enable debug logging.")
@click.option("--json-logs", is_flag=True, default=False, help="Emit logs as JSON.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool, json_logs: bool) -> None:
    """DocPatch — surgical LLM document editing."""
    ctx.ensure_object(dict)
    ctx.obj["verbose"] = verbose

    level = "DEBUG" if verbose else "INFO"
    processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if json_logs:
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty()))

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(getattr(__import__("logging"), level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )


cli.add_command(edit)
