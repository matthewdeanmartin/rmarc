"""Exceptions for rmarc (pymarc compatible)."""


class PymarcException(Exception):
    """Base pymarc Exception."""

    pass


class FatalReaderError(PymarcException):
    """Error preventing further reading."""

    pass


class RecordLengthInvalid(FatalReaderError):
    """Invalid record length."""

    def __str__(self):
        return "Invalid record length in first 5 bytes of record"


class TruncatedRecord(FatalReaderError):
    """Truncated record data."""

    def __str__(self):
        return "Record length in leader is greater than the length of data"


class EndOfRecordNotFound(FatalReaderError):
    """Unable to locate end of record marker."""

    def __str__(self):
        return "Unable to locate end of record marker"


class RecordLeaderInvalid(PymarcException):
    """Unable to extract record leader."""

    def __str__(self):
        return "Unable to extract record leader"


class RecordDirectoryInvalid(PymarcException):
    """Invalid directory."""

    def __str__(self):
        return "Invalid directory"


class NoFieldsFound(PymarcException):
    """Unable to locate fields in record data."""

    def __str__(self):
        return "Unable to locate fields in record data"


class BaseAddressInvalid(PymarcException):
    """Base address exceeds size of record."""

    def __str__(self):
        return "Base address exceeds size of record"


class BaseAddressNotFound(PymarcException):
    """Unable to locate base address of record."""

    def __str__(self):
        return "Unable to locate base address of record"


class WriteNeedsRecord(PymarcException):
    """Write requires a pymarc.Record object as an argument."""

    def __str__(self):
        return "Write requires a pymarc.Record object as an argument"


class NoActiveFile(PymarcException):
    """There is no active file to write to in call to write."""

    def __str__(self):
        return "There is no active file to write to in call to write"


class FieldNotFound(PymarcException):
    """Record does not contain the specified field."""

    def __str__(self):
        return "Record does not contain the specified field"


class BadSubfieldCodeWarning(Warning):
    """Warning about a non-ASCII subfield code."""

    def __init__(self, subf):
        super().__init__()
        self.subf = subf

    def __str__(self):
        return f"The subfield contained a non-ASCII subfield code: {self.subf}"


class BadLeaderValue(PymarcException):
    """Error when setting a leader value."""

    pass


class MissingLinkedFields(PymarcException):
    """Error when a non-880 field has a subfield 6 that cannot be matched to an 880."""

    def __init__(self, field):
        super().__init__(field)
        self.field = field

    def __str__(self):
        return f"{self.field.tag} field includes a subfield 6 but no linked fields could be found."
