"""Splicer — deterministic patch application."""

from docpatch.splicer.splice import splice
from docpatch.splicer.validate import validate_splice

__all__ = ["splice", "validate_splice"]
