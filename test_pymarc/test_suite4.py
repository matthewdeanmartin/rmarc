import unittest
from rmarc.field import Field, Subfield, Indicators
from rmarc.record import Record
from rmarc.exceptions import (
    RecordLengthInvalid,
    TruncatedRecord,
    EndOfRecordNotFound,
    RecordLeaderInvalid,
    FieldNotFound,
    MissingLinkedFields,
    WriteNeedsRecord,
    BadLeaderValue
)
from rmarc.reader import MARCReader
from rmarc.writer import MARCWriter
from io import BytesIO

class TestSuite4(unittest.TestCase):
    def test_reader_exceptions_truncated(self):
        # Record length says 26, but only 20 bytes provided
        data = b'00026' + b' ' * 15
        reader = MARCReader(data)
        rec = next(reader)
        self.assertIsNone(rec)
        self.assertIsInstance(reader.current_exception, TruncatedRecord)

    def test_reader_exceptions_invalid_length(self):
        # Not a number in first 5 bytes
        data = b'ABCDE' + b' ' * 20
        reader = MARCReader(data)
        rec = next(reader)
        self.assertIsNone(rec)
        self.assertIsInstance(reader.current_exception, RecordLengthInvalid)

    def test_reader_exceptions_no_eor(self):
        # Length 26, but no \x1d at the end
        data = b'00026' + b' ' * 21
        reader = MARCReader(data)
        rec = next(reader)
        self.assertIsNone(rec)
        self.assertIsInstance(reader.current_exception, EndOfRecordNotFound)

    def test_record_remove_field_not_found(self):
        r = Record()
        f = Field(tag='001', data='1')
        with self.assertRaises(FieldNotFound):
            r.remove_field(f)

    def test_linked_fields(self):
        r = Record()
        # Field with linkage to 880
        # Subfield 6 contains "880-01"
        f100 = Field(tag='100', indicators=['1', ' '], subfields=[
            Subfield('6', '880-01'),
            Subfield('a', 'Author')
        ])
        r.add_field(f100)
        
        # Linked 880 field
        # Subfield 6 contains "100-01"
        f880 = Field(tag='880', indicators=['1', ' '], subfields=[
            Subfield('6', '100-01'),
            Subfield('a', 'Linked Author')
        ])
        r.add_field(f880)
        
        linked = r.get_linked_fields(f100)
        self.assertEqual(len(linked), 1)
        self.assertEqual(linked[0]['a'], 'Linked Author')

    def test_missing_linked_fields(self):
        r = Record()
        f100 = Field(tag='100', indicators=['1', ' '], subfields=[
            Subfield('6', '880-01'),
            Subfield('a', 'Author')
        ])
        r.add_field(f100)
        
        with self.assertRaises(MissingLinkedFields):
            r.get_linked_fields(f100)

    def test_writer_needs_record(self):
        out = BytesIO()
        writer = MARCWriter(out)
        with self.assertRaises(WriteNeedsRecord):
            writer.write("not a record")

    def test_bad_leader_value(self):
        r = Record()
        # Record length should be 5 chars
        with self.assertRaises(BadLeaderValue):
            r.leader.record_length = "123"
        
        # Position out of bounds or too long value at position
        # Leader is 24 chars. Position 23 + value of length 2 = 25 > 24.
        with self.assertRaises(BadLeaderValue):
            r.leader[23] = "XY"

    def test_field_getitem_keyerror(self):
        f = Field(tag='245', subfields=[Subfield('a', 'Title')])
        with self.assertRaises(KeyError):
            val = f['b']
        
        # Control field doesn't have subfields
        f001 = Field(tag='001', data='123')
        with self.assertRaises(KeyError):
            val = f001['a']

    def test_field_setitem_keyerror(self):
        f = Field(tag='245', subfields=[Subfield('a', 'Title')])
        # No such subfield
        with self.assertRaises(KeyError):
            f['b'] = 'New Subtitle'
        
        # Multiple subfields with same code
        f.add_subfield('a', 'Another Title')
        with self.assertRaises(KeyError):
            f['a'] = 'Replacement'

    def test_record_getitem_keyerror(self):
        r = Record()
        with self.assertRaises(KeyError):
            val = r['999']

if __name__ == '__main__':
    unittest.main()
