"""From XML to MARC21 and back again (pymarc compatible)."""

__all__ = [
    "XmlHandler",
    "parse_xml",
    "map_xml",
    "parse_xml_to_array",
    "record_to_xml",
    "record_to_xml_node",
]

import unicodedata
import xml.etree.ElementTree as ET
from xml.sax import make_parser
from xml.sax.handler import ContentHandler, feature_namespaces

from rmarc._compat import HAS_LXML, lxml_ET
from rmarc.field import Field, Indicators
from rmarc.leader import Leader
from rmarc.marc8 import MARC8ToUnicode
from rmarc.record import Record

XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
MARC_XML_NS = "http://www.loc.gov/MARC21/slim"
MARC_XML_SCHEMA = "http://www.loc.gov/MARC21/slim http://www.loc.gov/standards/marcxml/schema/MARC21slim.xsd"


class XmlHandler(ContentHandler):
    """XML Handler."""

    def __init__(self, strict=False, normalize_form=None):
        self.records = []
        self._record = None
        self._field = None
        self._subfield_code = None
        self._text = []
        self._strict = strict
        self.normalize_form = normalize_form

    def startElementNS(self, name, qname, attrs):
        if self._strict and name[0] != MARC_XML_NS:
            return

        element = name[1]
        self._text = []

        if element == "record":
            self._record = Record()
        elif element == "controlfield":
            tag = attrs.getValue((None, "tag"))
            self._field = Field(tag)
        elif element == "datafield":
            tag = attrs.getValue((None, "tag"))
            ind1 = attrs.get((None, "ind1"), " ")
            ind2 = attrs.get((None, "ind2"), " ")
            self._field = Field(tag, Indicators(ind1, ind2))
        elif element == "subfield":
            self._subfield_code = attrs[(None, "code")]

    def endElementNS(self, name, qname):
        if self._strict and name[0] != MARC_XML_NS:
            return

        element = name[1]
        if self.normalize_form is not None:
            text = unicodedata.normalize(self.normalize_form, "".join(self._text))
        else:
            text = "".join(self._text)

        if element == "record" and self._record:
            self.process_record(self._record)
            self._record = None
        elif element == "leader" and self._record:
            self._record.leader = Leader(text)
        elif element == "controlfield" and self._record and self._field:
            self._field.data = text
            self._record.add_field(self._field)
            self._field = None
        elif element == "datafield" and self._record and self._field:
            self._record.add_field(self._field)
            self._field = None
        elif element == "subfield" and self._field and self._subfield_code:
            self._field.add_subfield(self._subfield_code, text)
            self._subfield_code = None

        self._text = []

    def characters(self, content):
        self._text.append(content)

    def process_record(self, record):
        self.records.append(record)


def parse_xml(xml_file, handler):
    if HAS_LXML:
        from lxml import sax as _lxml_sax

        tree = lxml_ET.parse(xml_file)
        _lxml_sax.saxify(tree, handler)
    else:
        parser = make_parser()
        parser.setContentHandler(handler)
        parser.setFeature(feature_namespaces, 1)
        parser.parse(xml_file)


def map_xml(function, *files):
    handler = XmlHandler()
    handler.process_record = function
    for xml_file in files:
        parse_xml(xml_file, handler)


def parse_xml_to_array(xml_file, strict=False, normalize_form=None):
    handler = XmlHandler(strict, normalize_form)
    parse_xml(xml_file, handler)
    return handler.records


def record_to_xml(record, quiet=False, namespace=False):
    node = record_to_xml_node(record, quiet, namespace)
    if HAS_LXML:
        return lxml_ET.tostring(node)
    return ET.tostring(node)


def record_to_xml_node(record, quiet=False, namespace=False):
    _ET = lxml_ET if HAS_LXML else ET

    marc8 = MARC8ToUnicode(quiet=quiet)

    def translate(data):
        if type(data) is str:
            return data
        else:
            return marc8.translate(data)

    if namespace and HAS_LXML:
        # lxml manages namespaces natively; declare via nsmap on the element
        NSMAP = {None: MARC_XML_NS, "xsi": XSI_NS}
        root = _ET.Element("record", nsmap=NSMAP)
        root.set(f"{{{XSI_NS}}}schemaLocation", MARC_XML_SCHEMA)
    else:
        root = _ET.Element("record")
        if namespace:
            root.set("xmlns", MARC_XML_NS)
            root.set("xmlns:xsi", XSI_NS)
            root.set("xsi:schemaLocation", MARC_XML_SCHEMA)
    leader = _ET.SubElement(root, "leader")
    leader.text = str(record.leader)
    for field in record:
        if field.control_field:
            control_field = _ET.SubElement(root, "controlfield")
            control_field.set("tag", field.tag)
            control_field.text = translate(field.data)
        else:
            data_field = _ET.SubElement(root, "datafield")
            data_field.set("ind1", field.indicators.first)
            data_field.set("ind2", field.indicators.second)
            data_field.set("tag", field.tag)
            for subfield in field:
                data_subfield = _ET.SubElement(data_field, "subfield")
                data_subfield.set("code", subfield.code)
                data_subfield.text = translate(subfield.value)

    return root
