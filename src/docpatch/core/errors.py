"""Typed exceptions. Never raise bare Exception or RuntimeError."""

from __future__ import annotations

from enum import StrEnum


class DocPatchError(Exception):
    """Base for all docpatch errors."""


class ParseError(DocPatchError):
    class Kind(StrEnum):
        UNSUPPORTED_FORMAT = "unsupported_format"
        MALFORMED_INPUT = "malformed_input"
        ROUND_TRIP_VIOLATION = "round_trip_violation"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"ParseError.{kind}: {detail}" if detail else f"ParseError.{kind}")


class LocateError(DocPatchError):
    class Kind(StrEnum):
        NOT_FOUND = "not_found"
        AMBIGUOUS = "ambiguous"
        INVALID_INSTRUCTION = "invalid_instruction"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"LocateError.{kind}: {detail}" if detail else f"LocateError.{kind}")


class PatchError(DocPatchError):
    class Kind(StrEnum):
        VALIDATION_FAILED = "validation_failed"
        MAX_RETRY_EXCEEDED = "max_retry_exceeded"
        TARGET_NOT_FOUND = "target_not_found"
        MODEL_ERROR = "model_error"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"PatchError.{kind}: {detail}" if detail else f"PatchError.{kind}")


class SpliceError(DocPatchError):
    class Kind(StrEnum):
        NODE_NOT_FOUND = "node_not_found"
        STRUCTURAL_VIOLATION = "structural_violation"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"SpliceError.{kind}: {detail}" if detail else f"SpliceError.{kind}")


class StorageError(DocPatchError):
    class Kind(StrEnum):
        NOT_FOUND = "not_found"
        ALREADY_EXISTS = "already_exists"
        IO_ERROR = "io_error"
        PATH_TRAVERSAL = "path_traversal"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"StorageError.{kind}: {detail}" if detail else f"StorageError.{kind}")


class ModelError(DocPatchError):
    class Kind(StrEnum):
        MISSING_EXTRA = "missing_extra"
        API_ERROR = "api_error"
        INVALID_RESPONSE = "invalid_response"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(f"ModelError.{kind}: {detail}" if detail else f"ModelError.{kind}")


class ValidationError(DocPatchError):
    class Kind(StrEnum):
        STRUCTURAL = "structural"
        POLICY = "policy"
        SCHEMA = "schema"

    def __init__(self, kind: Kind, detail: str = "") -> None:
        self.kind = kind
        super().__init__(
            f"ValidationError.{kind}: {detail}" if detail else f"ValidationError.{kind}"
        )
