"""Type stubs for the rmarc Rust extension module."""

from rmarc.field import Field, Indicators, Subfield

def version() -> str: ...
def decode_marc_raw(
    data: bytes,
    to_unicode: bool = True,
    force_utf8: bool = False,
    encoding: str = "iso8859-1",
    utf8_handling: str = "strict",
    quiet: bool = False,
) -> tuple[str, list[tuple[str, tuple]]]: ...
def decode_marc_fields(
    data: bytes,
    field_type: type[Field],
    subfield_type: type[Subfield],
    indicators_type: type[Indicators],
    to_unicode: bool = True,
    force_utf8: bool = False,
    encoding: str = "iso8859-1",
    utf8_handling: str = "strict",
    quiet: bool = False,
) -> tuple[str, list[Field]]: ...
def encode_marc_raw(
    leader: str,
    fields: list[tuple[str, bytes]],
) -> bytes: ...
def marc8_to_unicode_rs(data: bytes, quiet: bool = False) -> str: ...
