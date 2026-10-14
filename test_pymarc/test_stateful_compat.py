"""Compare realistic edit histories, including aliases retained across reloads."""

from unittest.mock import patch

import pymarc
import pytest
import rmarc
from hypothesis import settings
from hypothesis import strategies as st
from hypothesis.stateful import Bundle, RuleBasedStateMachine, invariant, rule, run_state_machine_as_test

TEXT = st.text(alphabet="abc XYZ012éö二&:/.-", max_size=30)
TAGS = st.sampled_from(["245", "500", "650"])


class CatalogEdits(RuleBasedStateMachine):
    fields = Bundle("retained_fields")
    lists = Bundle("retained_field_lists")

    def __init__(self):
        super().__init__()
        self.records = [pymarc.Record(), rmarc.Record()]
        self.retained_fields = []
        self.retained_lists = []

    @rule(target=fields, tag=TAGS, text=TEXT)
    def add_field_and_retain_reference(self, tag, text):
        pair = []
        for module, record in zip((pymarc, rmarc), self.records, strict=True):
            field = module.Field(tag, indicators=module.Indicators(" ", "0"), subfields=[module.Subfield("a", text)])
            record.add_ordered_field(field)
            pair.append(field)
        self.retained_fields.append(pair)
        return pair

    @rule(target=lists)
    def retain_live_fields_list(self):
        pair = [record.get_fields() for record in self.records]
        assert all(alias is record.fields for alias, record in zip(pair, self.records, strict=True))
        self.retained_lists.append(pair)
        return pair

    @rule(pair=fields, code=st.sampled_from(["a", "b", "x"]), text=TEXT)
    def edit_retained_field(self, pair, code, text):
        # The field may have been removed or belong to a record replaced by reload.
        for module, field in zip((pymarc, rmarc), pair, strict=True):
            field.subfields.append(module.Subfield(code, text))
            field.indicators = module.Indicators("1", "0")

    @rule(pair=fields, text=TEXT)
    def replace_subfields_through_slice(self, pair, text):
        for module, field in zip((pymarc, rmarc), pair, strict=True):
            alias = field.subfields
            alias[:] = [module.Subfield("a", text)]
            assert alias is field.subfields

    @rule(pair=lists, reverse=st.booleans())
    def edit_retained_fields_list(self, pair, reverse):
        for alias in pair:
            if reverse:
                alias.reverse()
            elif alias:
                alias.pop(0)

    @rule(tag=TAGS)
    def remove_all_matching_fields(self, tag):
        for record in self.records:
            record.remove_fields(tag)

    @rule(status=st.sampled_from(["n", "c", "d"]))
    def edit_leader(self, status):
        for record in self.records:
            record.leader[5] = status

    @rule()
    def serialize_and_reload(self):
        # Empty records serialize, but pymarc intentionally refuses to read them.
        if not self.records[0].fields:
            return
        encoded = [record.as_marc() for record in self.records]
        assert encoded[0] == encoded[1]
        self.records = [module.Record(data) for module, data in zip((pymarc, rmarc), encoded, strict=True)]

    @invariant()
    def observable_state_matches_after_every_action(self):
        expected, actual = self.records
        assert actual.as_dict() == expected.as_dict()
        assert actual.as_marc() == expected.as_marc()
        assert str(actual.leader) == str(expected.leader)
        assert actual.title == expected.title
        assert [str(field) for field in actual.get_fields("245", "650")] == [
            str(field) for field in expected.get_fields("245", "650")
        ]
        for reference, candidate in self.retained_fields:
            assert candidate.as_marc("utf-8") == reference.as_marc("utf-8")
        for reference, candidate in self.retained_lists:
            assert [str(field) for field in candidate] == [str(field) for field in reference]


@pytest.mark.parametrize("native", [True, False], ids=["rust", "python"])
def test_catalog_edit_histories(native):
    with patch.object(rmarc.record, "_HAS_RUST_CODEC", native):
        run_state_machine_as_test(
            CatalogEdits, settings=settings(max_examples=80, stateful_step_count=35, deadline=None)
        )
