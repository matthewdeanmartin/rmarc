# This file is part of pymarc. It is subject to the license terms in the
# LICENSE file found in the top-level directory of this distribution and at
# https://opensource.org/licenses/BSD-2-Clause. pymarc may be copied, modified,
# propagated, or distributed according to the terms contained in the LICENSE
# file.

"""The pymarc field file."""

import logging
import typing
from collections import defaultdict
from collections.abc import Iterator, Sequence
from typing import NamedTuple

from pymarc.constants import END_OF_FIELD, SUBFIELD_INDICATOR
from pymarc.marc8 import marc8_to_unicode

logger = logging.getLogger("pymarc")


class Subfield(NamedTuple):
    code: str
    value: str


class Indicators(NamedTuple):
    """A named tuple representing the indicators for a non-control field."""

    first: str
    second: str


class Field:
    """Field() pass in the field tag, indicators and subfields for the tag.

    .. code-block:: python

        field = Field(
            tag = '245',
            indicators = Indicators('0','1'),
            subfields = [
                Subfield(code='a', value='The pragmatic programmer : '),
                Subfield(code='b', value='from journeyman to master /'),
                Subfield(code='c', value='Andrew Hunt, David Thomas.'),
            ])

    If you want to create a control field, don't pass in the indicators
    and use a data parameter rather than a subfields parameter:

    .. code-block:: python

        field = Field(tag='001', data='fol05731351')
    """

    __slots__ = ("tag", "data", "_indicators", "subfields", "__pos", "control_field")

    def __init__(
        self,
        tag: str,
        indicators: Indicators | None = None,
        subfields: list[Subfield] | None = None,
        data: str | None = None,
    ):
        """Initialize a field `tag`."""
        # attempt to normalize integer tags if necessary
        try:
            self.tag = f"{int(tag):03}"
        except ValueError:
            self.tag = f"{tag}"

        if subfields and isinstance(subfields[0], str):
            raise ValueError(
                """The subfield input no longer accepts strings, and should use Subfield.
                   Please consult the documentation for details.
                """
            )

        self.subfields: list[Subfield] = []
        # Indicators are None if this is a control field.
        # This shadows the property "indicators" getter and setter below.
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
            elif (
                indicators
                and isinstance(indicators, list | tuple)
                and len(indicators) == 2
            ):
                self._indicators = Indicators(*indicators)
            else:
                # Fall back to setting the indicators through the setter. This will
                # raise a ValueError if the input is not valid.
                self.indicators = indicators

    @property
    def indicators(self) -> Indicators | None:
        """Return the field's indicators."""
        return self._indicators

    @indicators.setter
    def indicators(self, value: Sequence) -> None:
        """Set the field's indicators."""
        if value and isinstance(value, list | tuple) and len(value) != 2:
            raise ValueError(
                """The indicators input no longer accepts an iterable of arbitrary length. Use
                   the Indicators() named tuple instead. Please consult the documentation
                   for details.
                """
            )
        if value is not None:
            if isinstance(value, Indicators):
                self._indicators = value
            else:
                self._indicators = Indicators(*value)

    @classmethod
    def convert_legacy_subfields(cls, subfields: list[str]) -> list[Subfield]:
        """
        Converts older-style subfield lists into Subfield lists.

        Converts the old-style list of strings into a list of Subfields.
        As a class method this does not actually set any fields; it simply
        takes a list of strings and returns a list of Subfields.

        .. code-block:: python

            legacy_fields: list[str] = ['a', 'The pragmatic programmer : ',
                                        'b', 'from journeyman to master /',
                                        'c', 'Andrew Hunt, David Thomas']

            coded_fields: list[Subfield] = Field.convert_legacy_subfields(legacy_fields)

            myfield = Field(
                tag="245",
                indicators = ['0','1'],
                subfields=coded_fields
            )

        :param subfields: A list of [code, value, code, value]
        :return: A list of Subfield named tuples
        """
        # Make an iterator out of the incoming subfields.
        subf_it: Iterator[str] = iter(subfields)
        # This creates a tuple based on the next value of the iterator. In this case,
        # the subfield code will be the first element, and then the subfield value
        # will be the second.
        subf = zip(subf_it, subf_it, strict=True)
        # Create a coded subfield tuple of each (code, value) item in the incoming
        # subfields.
        return [Subfield._make(t) for t in subf]

    def __iter__(self):
        self.__pos = 0
        return self

    def __str__(self) -> str:
        """String representation of the field.

        A Field object in a string context will return the tag, indicators
        and subfield as a string. This follows MARCMaker format; see [1]
        and [2] for further reference. Special character mnemonic strings
        have yet to be implemented (see [3]), so be forewarned. Note also
        for complete MARCMaker compatibility, you will need to change your
        newlines to DOS format ('CRLF').

        [1] http://www.loc.gov/marc/makrbrkr.html#mechanics
        [2] http://search.cpan.org/~eijabb/MARC-File-MARCMaker/
        [3] http://www.loc.gov/marc/mnemonics.html
        """
        if self.control_field:
            _data: str = self.data.replace(" ", "\\") if self.data else ""
            return f"={self.tag}  {_data}"
        else:
            _ind = []
            _subf = []

            for indicator in self._indicators:  # type: ignore
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
        """A dict-like get method with a default value.

        Implements a non-raising getter for a subfield code that will
        return the value of the first subfield whose code is `key`. Returns
        the default value if the field is a control field or if the code is
        not present in the field.
        """
        try:
            return self[code]
        except KeyError:
            return default

    def __getitem__(self, code: str) -> str:
        """Retrieve the first subfield with a given subfield code in a field.

        Raises KeyError if `code` is not in the Field. If the field is a control
        field, also raise a KeyError.

        .. code-block:: python

            field['a']
        """
        if self.control_field:
            raise KeyError

        if code not in self:
            raise KeyError

        for subf in self.subfields:
            if subf.code == code:
                return subf.value
        # This should not occur, but just incase we've looped through
        # and couldn't find the code, default to raising KeyError.
        raise KeyError

    def __contains__(self, subfield: str) -> bool:
        """Allows a shorthand test of field membership.

        If the field is a control field, returns False.

        .. code-block:: python

            'a' in field

        """
        if self.control_field:
            return False

        # Tested and this variant works faster than using any().
        for s in self.subfields:  # noqa: SIM110
            if s.code == subfield:
                return True
        return False

    def __setitem__(self, code: str, value: str) -> None:
        """Set the values of the subfield code in a field.

        .. code-block:: python

            field['a'] = 'value'

        Raises KeyError if there is more than one subfield code, or
        if there is an attempt to set a subfield on a control field.
        """
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
            return subfield  # type: ignore
        except IndexError:
            raise StopIteration from None

    def value(self) -> str:
        """Returns the field's subfields (or data in the case of control fields) as a string."""
        if self.control_field:
            return self.data or ""

        return " ".join(subfield.value.strip() for subfield in self.subfields)

    def get_subfields(self, *codes) -> list[str]:
        """Get subfields matching `codes`.

        get_subfields() accepts one or more subfield codes and returns
        a list of subfield values.  The order of the subfield values
        in the list will be the order that they appear in the field.

        .. code-block:: python

            print(field.get_subfields('a'))
            print(field.get_subfields('a', 'b', 'z'))
        """
        if self.control_field:
            return []

        return [subfield.value for subfield in self.subfields if subfield.code in codes]

    def add_subfield(self, code: str, value: str, pos=None) -> None:
        """Adds a subfield code/value to the end of a field or at a position (pos).

        If pos is not supplied or out of range, the subfield will be added at the end.

        If the field is a control field, nothing will happen.

        .. code-block:: python

            field.add_subfield('u', 'http://www.loc.gov')
            field.add_subfield('u', 'http://www.loc.gov', 0)
        """
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
        """Deletes the first subfield with the specified 'code' and returns its value.

        .. code-block:: python

            value = field.delete_subfield('a')

        If no subfield is found with the specified code None is returned.
        """
        if self.control_field:
            return None

        if code not in self:
            return None

        index: int = [s.code for s in self.subfields].index(code)
        whole_field: Subfield = self.subfields.pop(index)

        return whole_field.value

    def subfields_as_dict(self) -> dict[str, list]:
        """Returns the subfields as a dictionary.

        Returns an empty dictionary if the field is a control field.

        The dictionary is a mapping of subfield codes and values. Since
        subfield codes can repeat the values are a list.
        """
        if self.control_field:
            return {}

        subs: defaultdict[str, list] = defaultdict(list)
        for field in self.subfields:
            subs[field.code].append(field.value)
        return dict(subs)

    def is_control_field(self) -> bool:
        """Returns true or false if the field is considered a control field.

        Prefer using the `control_field` property directly instead of this,
        which has been retained for legacy compatibility.

        Control fields lack indicators and subfields.
        """
        return self.control_field

    def linkage_occurrence_num(self) -> str | None:
        """Return the 'occurrence number' part of subfield 6, or None if not present."""
        ocn = self.get("6", "")
        return ocn.split("-")[1].split("/")[0] if ocn else None

    def as_marc(self, encoding: str) -> bytes:
        """Used during conversion of a field to raw marc."""
        if self.control_field:
            return f"{self.data}{END_OF_FIELD}".encode(encoding)

        _subf = []
        for subfield in self.subfields:
            _subf.append(f"{SUBFIELD_INDICATOR}{subfield.code}{subfield.value}")

        return (
            f"{self.indicator1}{self.indicator2}{''.join(_subf)}{END_OF_FIELD}".encode(
                encoding
            )
        )

    # alias for backwards compatibility
    as_marc21 = as_marc

    def format_field(self) -> str:
        """Returns the field's subfields (or data in the case of control fields) as a string.

        Like :func:`Field.value() <pymarc.field.Field.value>`, but prettier
        (adds spaces, formats subject headings).
        """
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
        """Returns True or False if the field is considered a subject field.

        Used by :func:`format_field() <pymarc.field.Field.format_field>` .
        """
        return self.tag.startswith("6")

    @property
    def indicator1(self) -> str:
        """Indicator 1.

        Returns an empty string if this is a control field.
        """
        return self._indicators.first if self._indicators else ""

    @indicator1.setter
    def indicator1(self, value: str) -> None:
        """Indicator 1 (setter).

        If this is a control field, this is a NoOp.
        """
        if self.control_field:
            self._indicators = None
        self._indicators = self._indicators._replace(first=value)  # type: ignore

    @property
    def indicator2(self) -> str:
        """Indicator 2.

        Returns an empty string if this is a control field.
        """
        return self._indicators.second if self._indicators else ""

    @indicator2.setter
    def indicator2(self, value: str) -> None:
        """Indicator 2 (setter).

        If this is a control field, this is a NoOp.
        """
        if self.control_field:
            self._indicators = None
        self._indicators = self._indicators._replace(second=value)  # type: ignore


class RawField(Field):
    """MARC field that keeps data in raw, un-decoded byte strings.

    Should only be used when input records are wrongly encoded.
    """

    def as_marc(self, encoding: str | None = None):
        """Used during conversion of a field to raw MARC."""
        if encoding is not None:
            logger.warning("Attempt to force a RawField into encoding %s", encoding)
        if self.control_field:
            return self.data + END_OF_FIELD.encode("ascii")  # type: ignore
        marc: bytes = self.indicator1.encode("ascii") + self.indicator2.encode("ascii")
        for subfield in self.subfields:
            marc += (
                SUBFIELD_INDICATOR.encode("ascii")
                + subfield.code.encode("ascii")
                + subfield.value  # type: ignore
            )
        return marc + END_OF_FIELD.encode("ascii")


def map_marc8_field(f: Field) -> Field:
    """Map MARC8 field."""
    if f.control_field:
        f.data = marc8_to_unicode(f.data)
    else:
        f.subfields = [
            Subfield(subfield.code, marc8_to_unicode(subfield.value))
            for subfield in f.subfields
        ]
    return f
