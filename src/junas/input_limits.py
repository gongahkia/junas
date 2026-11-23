"""Fixed capture and analyzed-text quotas for the text-only classifier."""

from collections.abc import Iterable
from typing import BinaryIO, TextIO

MAX_SOURCE_BYTES = 10 * 1024 * 1024
MAX_INLINE_TEXT_BYTES = 10 * 1024 * 1024
MAX_ANALYZED_TEXT_BYTES = 100 * 1024 * 1024
_TEXT_CHUNK = 4096


class ResourceLimitError(ValueError):
    """The input cannot be processed within the declared resource profile."""


def _utf8_size(text: str, maximum: int, label: str) -> int:
    if not isinstance(text, str):
        raise ValueError(f"{label} must be text")
    if len(text) > maximum:
        raise ResourceLimitError(f"{label} exceeds the {maximum}-byte limit")
    total = 0
    for offset in range(0, len(text), _TEXT_CHUNK):
        total += len(text[offset : offset + _TEXT_CHUNK].encode("utf-8"))
        if total > maximum:
            raise ResourceLimitError(f"{label} exceeds the {maximum}-byte limit")
    return total


def check_inline_text(text: str) -> None:
    _utf8_size(text, MAX_INLINE_TEXT_BYTES, "source text")


def check_analyzed_text(text: str) -> None:
    _utf8_size(text, MAX_ANALYZED_TEXT_BYTES, "analyzed text")


def check_text_parts(parts: Iterable[str], *, separator: str = "") -> None:
    total = 0
    first = True
    for part in parts:
        if not first:
            total += len(separator.encode("utf-8"))
        total += _utf8_size(part, MAX_ANALYZED_TEXT_BYTES - total, "analyzed text")
        first = False


def _read_binary(stream: BinaryIO, maximum: int, label: str) -> bytes:
    parts: list[bytes] = []
    total = 0
    while True:
        part = stream.read(min(_TEXT_CHUNK, maximum - total + 1))
        if not isinstance(part, bytes):
            raise ValueError(f"{label} must provide bytes")
        if not part:
            break
        total += len(part)
        if total > maximum:
            raise ResourceLimitError(f"{label} exceeds the {maximum}-byte limit")
        parts.append(part)
    return b"".join(parts)


def read_source(stream: BinaryIO) -> bytes:
    return _read_binary(stream, MAX_SOURCE_BYTES, "document source")


def read_stdin(stream: TextIO) -> str:
    binary = getattr(stream, "buffer", None)
    if binary is not None:
        data = _read_binary(binary, MAX_INLINE_TEXT_BYTES, "standard input")
        text = data.decode("utf-8")
        check_inline_text(text)
        return text
    parts: list[str] = []
    total = 0
    while True:
        part = stream.read(min(_TEXT_CHUNK, MAX_INLINE_TEXT_BYTES - total + 1))
        if not part:
            break
        total += _utf8_size(part, MAX_INLINE_TEXT_BYTES - total, "standard input")
        parts.append(part)
    return "".join(parts)
