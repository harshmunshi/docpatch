"""Patcher layer — operation primitives."""

from docpatch.patcher.base import Operation, Patch, ValidationResult
from docpatch.patcher.replace import ReplaceOperation

__all__ = ["Operation", "Patch", "ReplaceOperation", "ValidationResult"]
