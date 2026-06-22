"""Unit tests for typed errors."""

import pytest

from docpatch.core.errors import (
    DocPatchError,
    LocateError,
    ModelError,
    ParseError,
    PatchError,
    SpliceError,
    StorageError,
    ValidationError,
)


def test_parse_error_is_docpatch_error() -> None:
    with pytest.raises(DocPatchError):
        raise ParseError(ParseError.Kind.MALFORMED_INPUT, "bad json")


def test_parse_error_has_kind() -> None:
    exc = ParseError(ParseError.Kind.UNSUPPORTED_FORMAT, "xlsx")
    assert exc.kind == ParseError.Kind.UNSUPPORTED_FORMAT
    assert "xlsx" in str(exc)


def test_locate_error() -> None:
    exc = LocateError(LocateError.Kind.AMBIGUOUS, "multiple matches")
    assert exc.kind == LocateError.Kind.AMBIGUOUS


def test_patch_error() -> None:
    exc = PatchError(PatchError.Kind.MAX_RETRY_EXCEEDED)
    assert "max_retry_exceeded" in str(exc)


def test_all_errors_inherit_base() -> None:
    errors = [
        ParseError(ParseError.Kind.MALFORMED_INPUT),
        LocateError(LocateError.Kind.NOT_FOUND),
        PatchError(PatchError.Kind.TARGET_NOT_FOUND),
        SpliceError(SpliceError.Kind.NODE_NOT_FOUND),
        StorageError(StorageError.Kind.NOT_FOUND),
        ModelError(ModelError.Kind.API_ERROR),
        ValidationError(ValidationError.Kind.STRUCTURAL),
    ]
    for exc in errors:
        assert isinstance(exc, DocPatchError)
