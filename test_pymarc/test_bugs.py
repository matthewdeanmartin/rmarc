
import pytest
from rmarc.marc8 import marc8_to_unicode
from rmarc.record import Record

def test_trailing_combining_character():
    # 0xE2 is combining acute accent in ANSEL (MARC-8 G1)
    # If it's at the end of the string, it should ideally be preserved 
    # as a combining character in Unicode, or at least not crash.
    # But in the current Rust implementation, it seems to be lost because
    # combinings are only flushed when a non-combining character is seen.
    
    marc8_data = b"e\xe2" # 'e' followed by combining acute? 
    # Wait, MARC-8 puts combining BEFORE.
    # So \xe2e is 'é'.
    # What if it's "e\xe2"?
    
    result = marc8_to_unicode(b"e\xe2")
    # Current behavior expected: "e" (the \xe2 is lost)
    # Desired behavior: "e\u0301" (or similar)
    
    assert result == "e\u0301", f"Expected 'e' with combining acute, got {result!r}"

def test_utf8_encoding_when_leader_not_a():
    # Record with leader[9] = ' ' (MARC-8) but we force utf-8 via encoding parameter
    
    field001 = b"UTF-8\xc3\xa9" # 'é' (2 bytes) -> total 7 bytes
    field_data = field001 + b"\x1e" # 8 bytes
    
    directory = b"001" + b"0008" + b"00000" # 12 bytes
    directory_block = directory + b"\x1e" # 13 bytes
    
    base_address = 24 + 13 # 37
    record_length = base_address + 8 + 1 # 46 (including record terminator)
    
    leader = f"{record_length:05}     22{base_address:05}   4500".encode('ascii')
    #          012345678901234567890123
    # Pos 9 is ' '.
    
    marc_record = leader + directory_block + field_data + b"\x1d"
    
    # We pass file_encoding="utf-8"
    rec = Record(marc_record, file_encoding="utf-8")
    
    f001 = rec['001']
    # If it fails, f001.data will be bytes b'UTF-8\xc3\xa9' instead of str
    assert isinstance(f001.data, str), f"Expected str, got {type(f001.data)}: {f001.data!r}"
    assert f001.data == "UTF-8\u00e9"

def test_utf8_data_field_when_leader_not_a():
    # Record with leader[9] = ' ' (MARC-8) but we force utf-8 via encoding parameter
    
    # Data field 245 with subfield $a containing UTF-8
    # Indicators '  ' (2 bytes) + 0x1F + 'a' + "Value\xc3\xa9" (7 bytes) = 11 bytes
    field_content = b"  \x1faValue\xc3\xa9" 
    field_data = field_content + b"\x1e" # 12 bytes
    
    directory = b"245" + b"0012" + b"00000" # 12 bytes
    directory_block = directory + b"\x1e" # 13 bytes
    
    base_address = 24 + 13 # 37
    record_length = base_address + 12 + 1 # 50
    
    leader = f"{record_length:05}     22{base_address:05}   4500".encode('ascii')
    marc_record = leader + directory_block + field_data + b"\x1d"
    
    rec = Record(marc_record, file_encoding="utf-8")
    
    f245 = rec['245']
    val = f245['a']
    assert isinstance(val, str), f"Expected str, got {type(val)}: {val!r}"
    assert val == "Value\u00e9"
