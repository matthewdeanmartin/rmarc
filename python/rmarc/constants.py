"""Constants for rmarc (pymarc compatible)."""

__all__ = [
    "LEADER_LEN",
    "DIRECTORY_ENTRY_LEN",
    "SUBFIELD_INDICATOR",
    "END_OF_FIELD",
    "END_OF_RECORD",
]

LEADER_LEN = 24
DIRECTORY_ENTRY_LEN = 12
SUBFIELD_INDICATOR = chr(0x1F)
END_OF_FIELD = chr(0x1E)
END_OF_RECORD = chr(0x1D)
