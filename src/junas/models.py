"""Transport-independent inputs and labels for the classifier."""

from dataclasses import dataclass

from junas.input_limits import check_inline_text


@dataclass(frozen=True)
class DocumentInput:
    text: str

    def __post_init__(self) -> None:
        check_inline_text(self.text)
        if not self.text.strip():
            raise ValueError("text must contain non-whitespace content")
        if "\x00" in self.text:
            raise ValueError("binary NUL bytes are not accepted as text")
