import unittest
from rmarc.marc8 import marc8_to_unicode
from rmarc.record import Record
from rmarc.field import Field, Subfield

class TestSuite5(unittest.TestCase):
    def test_marc8_basic_ascii(self):
        # Basic ASCII in MARC8 is just ASCII
        self.assertEqual(marc8_to_unicode(b'Hello'), 'Hello')

    def test_marc8_ansel_accent(self):
        # Acute accent (0xe2) + 'a' = 'á'
        # MARC8 puts the accent BEFORE the character
        self.assertEqual(marc8_to_unicode(b'\xe2a'), 'á')
        
        # Grave accent (0xe1) + 'e' = 'è'
        self.assertEqual(marc8_to_unicode(b'\xe1e'), 'è')

    def test_marc8_multiple_accents(self):
        import unicodedata
        # 'a' with acute accent and cedilla
        # Cedilla (0xf0), Acute (0xe2), 'a'
        # result = unicodedata.normalize('NFC', 'a' + '\u0327' + '\u0301')
        expected = unicodedata.normalize('NFC', 'a\u0327\u0301')
        self.assertEqual(marc8_to_unicode(b'\xf0\xe2a'), expected)

    def test_marc8_escape_sequences(self):
        # Switch to Greek (G0 = 0x53 'S')? No, Greek is G0 = 0x53 according to some docs, 
        # but let's check CODESETS in marc8.py.
        # Actually, let's use something simple like 'Basic Latin' escape \x1b(B
        self.assertEqual(marc8_to_unicode(b'\x1b(BHello'), 'Hello')

    def test_record_with_marc8(self):
        # Test a record that needs MARC8 decoding
        # Leader index 9 is ' ' (MARC8)
        # 00055 is length: 24 (leader) + 24 (directory) + 1 (separator) + 6 (data) = 55
        # 00049 is base address: 24 (leader) + 24 (directory) + 1 (separator) = 49
        leader = b'00055    2200049   4500'
        # Field 245 with 'Française' in MARC8: Fran\xf0caise
        # Data: 00 (ind) + \x1f + a + Fran\xf0caise + \x1e
        # 00 (2) + \x1f (1) + a (1) + Fran (4) + \xf0 (1) + caise (5) + \x1e (1) = 16 bytes
        # Wait, 16 bytes for 245.
        # Plus 001 field: '1\x1e' (2 bytes)
        # Directory:
        # 001 0002 00000
        # 245 0016 00002
        # Total data: 2 + 16 = 18.
        # Total record: 24 (leader) + 24 (directory) + 1 (sep) + 18 (data) = 67.
        # Base address: 24 + 24 + 1 = 49.
        # Fixed leader: 24 bytes
        # 0-4: 00067
        # 5-8: spaces
        # 9: space (MARC8)
        # 10-11: 22
        # 12-16: 00049
        # 17-23:    4500
        leader = b'00067     2200049   4500'
        directory = b'001000200000245001600002'
        data = b'1\x1e00\x1faFran\xf0caise\x1e\x1d'
        marc_data = leader + directory + b'\x1e' + data
        r = Record(data=marc_data)

        self.assertEqual(r['001'].data, '1')
        self.assertEqual(r['245']['a'], 'Française')
        self.assertEqual(r.leader[9], ' ')


    def test_marc8_special_chars(self):
        # Polish L (0xa1 uppercase, 0xb1 lowercase)
        self.assertEqual(marc8_to_unicode(b'\xa1'), 'Ł')
        self.assertEqual(marc8_to_unicode(b'\xb1'), 'ł')
        
        # AE ligature (0xa5 uppercase, 0xb5 lowercase)
        self.assertEqual(marc8_to_unicode(b'\xa5'), 'Æ')
        self.assertEqual(marc8_to_unicode(b'\xb5'), 'æ')

    def test_marc8_mixed_ascii_ansel(self):
        # "Fran\xe2caise" -> "Française" if \xe2 was cedilla? 
        # Wait, 0xe2 is ACUTE. Cedilla is 0xf0.
        # "Fran\xf0caise" -> "Française"
        self.assertEqual(marc8_to_unicode(b'Fran\xf0caise'), 'Française')

    def test_marc8_to_unicode_with_str_input(self):
        # Should handle string input by encoding to latin-1 first
        self.assertEqual(marc8_to_unicode('Fran\xf0caise'), 'Française')

if __name__ == '__main__':
    unittest.main()
