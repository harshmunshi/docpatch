"""Locator layer. Symbolic first, semantic as fallback."""

from docpatch.locator.base import LocateResult, Locator
from docpatch.locator.composite import CompositeLocator
from docpatch.locator.semantic import SemanticLocator
from docpatch.locator.symbolic import SymbolicLocator

__all__ = ["CompositeLocator", "LocateResult", "Locator", "SemanticLocator", "SymbolicLocator"]
