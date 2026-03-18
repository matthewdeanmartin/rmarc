"""The rmarc field file (pymarc compatible)."""

import logging
import typing
from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import NamedTuple

from rmarc.constants import END_OF_FIELD, SUBFIELD_INDICATOR
from rmarc.marc8 import marc8_to_unicode

logger = logging.getLogger("pymarc")


class Subfield(NamedTuple):
    code: str
    value: str


class Indicators(NamedTuple):
    """A named tuple representing the indicators for a non-control field."""

    first: str
    second: str


class Field:
    """Field() pass in the field tag, indicators and subfields for the tag."""

    __slots__ = ("tag", "data", "_indicators", "subfields", "__pos", "control_field")

    def __init__(
        self,
        tag: str,
        indicators: Indicators | None = None,
        subfields: list[Subfield] | None = None,
        data: str | None = None,
    ):
        # attempt to normalize integer tags if necessary
        try:
            self.tag = f"{int(tag):03}"
        except ValueError:
            self.tag = f"{tag}"

        if subfields and isinstance(subfields[0], str):
            raise ValueError("""The subfield input no longer accepts strings, and should use Subfield.
                   Please consult the documentation for details.
                """)

        self.subfields: list[Subfield] = []
        self._indicators: Indicators | None = None
        self.data: str | None = None
        self.control_field: bool = False

        # assume control fields are numeric only; replicates ruby-marc behavior
        if self.tag < "010" and self.tag.isdigit():
            self.control_field = True
            self.data = data
        else:
            self.subfields = subfields or []
            if not indicators:
                self._indicators = Indicators(" ", " ")
            elif indicators and isinstance(indicators, (list, tuple)) and len(indicators) == 2:
                self._indicators = Indicators(*indicators)
            else:
                self.indicators = indicators

    @property
    def indicators(self) -> Indicators | None:
        return self._indicators

    @indicators.setter
    def indicators(self, value: Sequence) -> None:
        if value and isinstance(value, (list, tuple)) and len(value) != 2:
            raise ValueError("""The indicators input no longer accepts an iterable of arbitrary length. Use
                   the Indicators() named tuple instead. Please consult the documentation
                   for details.
                """)
        if value is not None:
            if isinstance(value, Indicators):
                self._indicators = value
            else:
                self._indicators = Indicators(*value)

    @classmethod
    def convert_legacy_subfields(cls, subfields: list[str]) -> list[Subfield]:
        subf_it: Iterator[str] = iter(subfields)
        subf = zip(subf_it, subf_it, strict=True)
        return [Subfield._make(t) for t in subf]

    def __iter__(self):
        self.__pos = 0
        return self

    def __str__(self) -> str:
        if self.control_field:
            _data: str = self.data.replace(" ", "\\") if self.data else ""
            return f"={self.tag}  {_data}"
        else:
            _ind = []
            _subf = []

            for indicator in self._indicators or Indicators(" ", " "):
                if indicator in (" ", "\\"):
                    _ind.append("\\")
                else:
                    _ind.append(f"{indicator}")

            for subfield in self.subfields:
                _subf.append(f"${subfield.code}{subfield.value}")

            return f"={self.tag}  {''.join(_ind)}{''.join(_subf)}"

    @typing.overload
    def get(self, code: str, default: str) -> str: ...

    @typing.overload
    def get(self, code: str, default: None = None) -> str | None: ...

    def get(self, code: str, default: str | None = None) -> str | None:
        try:
            return self[code]
        except KeyError:
            return default

    def __getitem__(self, code: str) -> str:
        if self.control_field:
            raise KeyError

        if code not in self:
            raise KeyError

        for subf in self.subfields:
            if subf.code == code:
                return subf.value
        raise KeyError

    def __contains__(self, subfield: str) -> bool:
        if self.control_field:
            return False

        for s in self.subfields:
            if s.code == subfield:
                return True
        return False

    def __setitem__(self, code: str, value: str) -> None:
        if self.control_field:
            raise KeyError("field is a control field")

        num_subfields: int = [x.code for x in self.subfields].count(code)

        if num_subfields > 1:
            raise KeyError(f"more than one code '{code}'")
        elif num_subfields == 0:
            raise KeyError(f"no code '{code}'")

        for idx, subf in enumerate(self.subfields):
            if subf.code == code:
                new_val = Subfield(code=subf.code, value=value)
                self.subfields[idx] = new_val
                break

    def __next__(self) -> Subfield:
        if self.control_field:
            raise StopIteration

        try:
            subfield = self.subfields[self.__pos]
            self.__pos += 1
            return subfield
        except IndexError:
            raise StopIteration from None

    def value(self) -> str:
        if self.control_field:
            return self.data or ""

        return " ".join(subfield.value.strip() for subfield in self.subfields)

    def get_subfields(self, *codes) -> list[str]:
        if self.control_field:
            return []

        return [subfield.value for subfield in self.subfields if subfield.code in codes]

    def add_subfield(self, code: str, value: str, pos=None) -> None:
        if self.control_field:
            return None

        append: bool = pos is None or pos > len(self.subfields)
        insertable: Subfield = Subfield(code=code, value=value)

        if append:
            self.subfields.append(insertable)
        elif pos is not None:
            self.subfields.insert(pos, insertable)

        return None

    def delete_subfield(self, code: str) -> str | None:
        if self.control_field:
            return None

        if code not in self:
            return None

        index: int = [s.code for s in self.subfields].index(code)
        whole_field: Subfield = self.subfields.pop(index)

        return whole_field.value

    def subfields_as_dict(self) -> dict[str, list]:
        if self.control_field:
            return {}

        subs: defaultdict[str, list] = defaultdict(list)
        for field in self.subfields:
            subs[field.code].append(field.value)
        return dict(subs)

    def is_control_field(self) -> bool:
        return self.control_field

    def linkage_occurrence_num(self) -> str | None:
        ocn = self.get("6", "")
        return ocn.split("-")[1].split("/")[0] if ocn else None

    def as_marc(self, encoding: str) -> bytes:
        if self.control_field:
            return f"{self.data}{END_OF_FIELD}".encode(encoding)

        _subf = []
        for subfield in self.subfields:
            _subf.append(f"{SUBFIELD_INDICATOR}{subfield.code}{subfield.value}")

        return f"{self.indicator1}{self.indicator2}{''.join(_subf)}{END_OF_FIELD}".encode(encoding)

    # alias for backwards compatibility
    as_marc21 = as_marc

    def format_field(self) -> str:
        if self.control_field:
            return self.data or ""

        field_data: str = ""

        for subfield in self.subfields:
            if subfield.code == "6":
                continue

            if not self.is_subject_field():
                field_data += f" {subfield.value}"
            else:
                if subfield.code not in ("v", "x", "y", "z"):
                    field_data += f" {subfield.value}"
                else:
                    field_data += f" -- {subfield.value}"
        return field_data.strip()

    def is_subject_field(self) -> bool:
        return self.tag.startswith("6")

    @property
    def indicator1(self) -> str:
        return self._indicators.first if self._indicators else ""

    @indicator1.setter
    def indicator1(self, value: str) -> None:
        if self.control_field:
            return
        self._indicators = (self._indicators or Indicators(" ", " "))._replace(first=value)

    @property
    def indicator2(self) -> str:
        return self._indicators.second if self._indicators else ""

    @indicator2.setter
    def indicator2(self, value: str) -> None:
        if self.control_field:
            return
        self._indicators = (self._indicators or Indicators(" ", " "))._replace(second=value)


class RawField(Field):
    """MARC field that keeps data in raw, un-decoded byte strings."""

    def as_marc(self, encoding: str | None = None):
        if encoding is not None:
            logger.warning("Attempt to force a RawField into encoding %s", encoding)
        if self.control_field:
            _d = self.data
            raw: bytes = bytes(_d) if isinstance(_d, bytes) else (_d or "").encode("iso8859-1")
            return raw + END_OF_FIELD.encode("ascii")
        marc: bytes = self.indicator1.encode("ascii") + self.indicator2.encode("ascii")
        for subfield in self.subfields:
            val = subfield.value if isinstance(subfield.value, bytes) else subfield.value.encode("iso8859-1")
            marc += SUBFIELD_INDICATOR.encode("ascii") + subfield.code.encode("ascii") + val
        return marc + END_OF_FIELD.encode("ascii")


def map_marc8_field(f: Field) -> Field:
    if f.control_field:
        f.data = marc8_to_unicode(f.data)
    else:
        f.subfields = [Subfield(subfield.code, marc8_to_unicode(subfield.value)) for subfield in f.subfields]
    return f
