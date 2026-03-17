"""Type stubs for the rmarc Rust extension module."""

def version() -> str: ...

class MarcRecord:
    tag: str
    def __init__(self, tag: str) -> None: ...  # pylint: disable=unused-argument
    def value(self) -> str: ...
