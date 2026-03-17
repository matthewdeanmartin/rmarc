"""Type stubs for the rmarc Rust extension module."""

def version() -> str: ...

class MarcRecord:
    tag: str
    def __init__(self, tag: str) -> None: ...  # pylint: disable=unused-argument
    def value(self) -> str: ...

def decode_marc_raw(
    data: bytes,
    to_unicode: bool = True,
    force_utf8: bool = False,
    encoding: str = "iso8859-1",
    utf8_handling: str = "strict",
    quiet: bool = False,
) -> tuple[str, list[tuple[str, tuple]]]: ...

def encode_marc_raw(
    leader: str,
    fields: list[tuple[str, bytes]],
) -> bytes: ...

def marc8_to_unicode_rs(data: bytes, quiet: bool = False) -> str: ...
