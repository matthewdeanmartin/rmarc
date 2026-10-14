"""Small regressions for optional backends; run with and without the fast extra."""

import builtins
import importlib.util
import json
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import rmarc
from rmarc import _compat, marcxml


@pytest.fixture(params=[False, True], ids=["stdlib", "lxml"])
def xml_backend(request, monkeypatch):
    if request.param:
        etree = pytest.importorskip("lxml.etree")
        monkeypatch.setattr(marcxml, "lxml_ET", etree)
    else:
        monkeypatch.setattr(marcxml, "lxml_ET", None)
    monkeypatch.setattr(marcxml, "HAS_LXML", request.param)


def sample_record():
    record = rmarc.Record()
    record.add_field(rmarc.Field("001", data="identifier & <one>"))
    record.add_field(
        rmarc.Field(
            "245",
            indicators=rmarc.Indicators("1", "0"),
            subfields=[rmarc.Subfield("a", "Cafe\u0301 & <title>"), rmarc.Subfield("a", "二")],
        )
    )
    return record


@pytest.mark.parametrize("namespace", [False, True])
def test_xml_namespace_and_unicode_roundtrip(xml_backend, namespace):
    record = sample_record()
    encoded = marcxml.record_to_xml(record, namespace=namespace)
    node = ET.fromstring(encoded)  # noqa: S314 - generated in this test
    assert node.tag == (f"{{{marcxml.MARC_XML_NS}}}record" if namespace else "record")
    if namespace:
        assert node.attrib[f"{{{marcxml.XSI_NS}}}schemaLocation"] == marcxml.MARC_XML_SCHEMA
    [decoded] = marcxml.parse_xml_to_array(BytesIO(encoded), strict=namespace)
    assert decoded.as_dict() == record.as_dict()


def test_xml_normalization_and_strict_namespace(xml_backend):
    encoded = marcxml.record_to_xml(sample_record(), namespace=True)
    [decoded] = marcxml.parse_xml_to_array(BytesIO(encoded), strict=True, normalize_form="NFC")
    assert decoded["245"].get_subfields("a") == ["Café & <title>", "二"]
    unqualified = marcxml.record_to_xml(sample_record())
    assert marcxml.parse_xml_to_array(BytesIO(unqualified), strict=True) == []


def test_xml_callback_order_across_files(xml_backend):
    first = sample_record()
    second = sample_record()
    second["001"].data = "second"
    seen = []
    marcxml.map_xml(
        lambda record: seen.append(record["001"].data),
        BytesIO(marcxml.record_to_xml(first)),
        BytesIO(marcxml.record_to_xml(second)),
    )
    assert seen == ["identifier & <one>", "second"]


def test_xml_writer_collection_roundtrip(xml_backend):
    stream = BytesIO()
    writer = rmarc.XMLWriter(stream)
    writer.write(sample_record())
    writer.write(sample_record())
    writer.close(close_fh=False)
    assert not stream.closed
    decoded = marcxml.parse_xml_to_array(BytesIO(stream.getvalue()), strict=True)
    assert [record.as_dict() for record in decoded] == [sample_record().as_dict()] * 2


@pytest.mark.parametrize("accelerated", [False, True], ids=["stdlib", "orjson"])
def test_json_optional_import_and_control_character_fallback(monkeypatch, accelerated):
    """Load a private copy so disabling imports cannot poison other tests."""
    if accelerated:
        pytest.importorskip("orjson")
    original_import = builtins.__import__

    def controlled_import(name, *args, **kwargs):
        if not accelerated and name in {"orjson", "lxml.etree"}:
            raise ImportError("optional backend deliberately absent")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", controlled_import)
    spec = importlib.util.spec_from_file_location("isolated_compat", Path(_compat.__file__))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.HAS_ORJSON is accelerated
    if not accelerated:
        assert module.lxml_ET is None
    for payload in ['{"value":"a\tb"}', b'{"value":"a\tb"}']:
        assert module.json_loads(payload) == {"value": "a\tb"}
    value = {"title": "Café 二", "repeat": [None, True, 123]}
    assert json.loads(module.json_dumps(value)) == value
    with pytest.raises(ValueError):
        module.json_loads(b'{"broken":')


def test_xml_translates_raw_marc8_control_and_subfield_values(xml_backend):
    record = rmarc.Record()
    record.add_field(rmarc.RawField("001", data=bytes([0xE2, ord("e")])))
    record.add_field(
        rmarc.RawField("245", indicators=rmarc.Indicators(" ", " "), subfields=[rmarc.Subfield("a", bytes([0xA1]))])
    )
    encoded = marcxml.record_to_xml(record)
    [decoded] = marcxml.parse_xml_to_array(BytesIO(encoded))
    assert decoded["001"].data == "é"
    assert decoded["245"]["a"] == "Ł"
