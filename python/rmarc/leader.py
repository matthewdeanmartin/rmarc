"""The rmarc.leader file (pymarc compatible)."""

from rmarc.constants import LEADER_LEN
from rmarc.exceptions import BadLeaderValue, RecordLeaderInvalid


class Leader:
    """Mutable leader."""

    def __init__(self, leader: str) -> None:
        if len(leader) != LEADER_LEN:
            raise RecordLeaderInvalid
        self.leader = leader

    def __getitem__(self, item):
        if isinstance(item, (slice, int)):
            return self.leader[item]
        return getattr(self, item)

    def __setitem__(self, item, value: str) -> None:
        if isinstance(item, slice):
            self._replace_values(position=item.start, value=value)
        elif isinstance(item, int):
            self._replace_values(position=item, value=value)
        else:
            setattr(self, item, value)

    def __str__(self) -> str:
        return self.leader

    def __eq__(self, other) -> bool:
        if isinstance(other, Leader):
            return self.leader == other.leader
        if isinstance(other, str):
            return self.leader == other
        return NotImplemented

    def __hash__(self):
        return hash(self.leader)

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

    def __len__(self):
        return len(self.leader)

    def _replace_values(self, position: int, value: str) -> None:
        if position < 0:
            raise IndexError("Position must be positive")
        after = position + len(value)
        if after > LEADER_LEN:
            raise BadLeaderValue(f"{value} is too long to be inserted at {position}")
        self.leader = self.leader[:position] + value + self.leader[after:]

    @property
    def record_length(self) -> str:
        return self.leader[:5]

    @record_length.setter
    def record_length(self, value: str) -> None:
        if len(value) != 5:
            raise BadLeaderValue(f"Record length is 4 chars field, got {value}")
        self._replace_values(position=0, value=value)

    @property
    def record_status(self) -> str:
        return self.leader[5]

    @record_status.setter
    def record_status(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Record status is 1 char field, got {value}")
        self._replace_values(position=5, value=value)

    @property
    def type_of_record(self) -> str:
        return self.leader[6]

    @type_of_record.setter
    def type_of_record(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Type of record is 1 char field, got {value}")
        self._replace_values(position=6, value=value)

    @property
    def bibliographic_level(self) -> str:
        return self.leader[7]

    @bibliographic_level.setter
    def bibliographic_level(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Bibliographic level is 1 char field, got {value}")
        self._replace_values(position=7, value=value)

    @property
    def type_of_control(self) -> str:
        return self.leader[8]

    @type_of_control.setter
    def type_of_control(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Type of control is 1 char field, got {value}")
        self._replace_values(position=8, value=value)

    @property
    def coding_scheme(self) -> str:
        return self.leader[9]

    @coding_scheme.setter
    def coding_scheme(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Character coding scheme is 1 char field, got {value}"
            )
        self._replace_values(position=9, value=value)

    @property
    def indicator_count(self) -> str:
        return self.leader[10]

    @indicator_count.setter
    def indicator_count(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Indicator count is 1 char field, got {value}")
        self._replace_values(position=10, value=value)

    @property
    def subfield_code_count(self) -> str:
        return self.leader[11]

    @subfield_code_count.setter
    def subfield_code_count(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Subfield code count is 1 char field, got {value}")
        self._replace_values(position=11, value=value)

    @property
    def base_address(self) -> str:
        return self.leader[12:17]

    @base_address.setter
    def base_address(self, value: str) -> None:
        if len(value) != 5:
            raise BadLeaderValue(f"Base address of data is 4 chars field, got {value}")
        self._replace_values(position=12, value=value)

    @property
    def encoding_level(self) -> str:
        return self.leader[17]

    @encoding_level.setter
    def encoding_level(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(f"Encoding level is 1 char field, got {value}")
        self._replace_values(position=17, value=value)

    @property
    def cataloging_form(self) -> str:
        return self.leader[18]

    @cataloging_form.setter
    def cataloging_form(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Descriptive cataloging form is 1 char field, got {value}"
            )
        self._replace_values(position=18, value=value)

    @property
    def multipart_ressource(self) -> str:
        return self.leader[19]

    @multipart_ressource.setter
    def multipart_ressource(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Multipart resource record level is 1 char field, got {value}"
            )
        self._replace_values(position=19, value=value)

    @property
    def length_of_field_length(self) -> str:
        return self.leader[20]

    @length_of_field_length.setter
    def length_of_field_length(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Length of the length-of-field portion is 1 char field, got {value}"
            )
        self._replace_values(position=20, value=value)

    @property
    def starting_character_position_length(self) -> str:
        return self.leader[21]

    @starting_character_position_length.setter
    def starting_character_position_length(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Length of the starting-character-position portion is 1 char field, got {value}"
            )
        self._replace_values(position=21, value=value)

    @property
    def implementation_defined_length(self) -> str:
        return self.leader[22]

    @implementation_defined_length.setter
    def implementation_defined_length(self, value: str) -> None:
        if len(value) != 1:
            raise BadLeaderValue(
                f"Length of the implementation-defined portion is 1 char field, got {value}"
            )
        self._replace_values(position=22, value=value)
