# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.utils.customer_barcode import extract_address_code


@pytest.mark.parametrize("address,expected_code,expected_confident", [
    ("東京都千代田区霞が関1丁目3番2号",   "1-3-2",  True),
    ("東京都新宿区西新宿2丁目8番1号",     "2-8-1",  True),
    ("東京都千代田区霞が関１丁目３番２号", "1-3-2",  True),
    ("東京都渋谷区道玄坂2番地",           "2",      True),
    ("東京都港区六本木3-14-1",            "3-14-1", True),
    ("東京都港区六本木３－１４－１",       "3-14-1", True),
    ("東京都港区六本木ヒルズ森タワー",     "",       False),
    ("",                                   "",       False),
])
def test_extract_address_code(address, expected_code, expected_confident):
    code, confident = extract_address_code(address)
    assert code == expected_code
    assert confident == expected_confident


from app.utils.customer_barcode import calc_check_digit, build_barcode_chars


def test_calc_check_digit_basic():
    # チェックデジットは 0-9, '-', CC1-CC8 のどれか
    chars = list("1000013") + list("1-3-2") + ["CC4"] * 8
    check = calc_check_digit(chars)
    valid = [str(i) for i in range(10)] + ['-'] + [f'CC{i}' for i in range(1, 9)]
    assert check in valid


def test_calc_check_digit_multiple_of_19():
    # チェックデジットを含めた合計が 19 の倍数になること
    chars = list("1000013") + list("1-3-2") + ["CC4"] * 8
    check = calc_check_digit(chars)
    from app.utils.customer_barcode import _CHAR_VALUES
    total = sum(_CHAR_VALUES.get(c, 0) for c in chars) + _CHAR_VALUES.get(check, 0)
    assert total % 19 == 0


def test_build_barcode_chars_length():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert len(chars) == 23


def test_build_barcode_chars_start_stop():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert chars[0] == 'S'
    assert chars[-1] == 'STOP'


def test_build_barcode_chars_postal():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert chars[1:8] == list("1000013")


def test_build_barcode_chars_addr_pad():
    chars = build_barcode_chars("1000013", "1")
    payload_addr = chars[8:21]
    assert payload_addr[0] == '1'
    assert all(c == 'CC4' for c in payload_addr[1:])


def test_build_barcode_chars_invalid_postal():
    with pytest.raises(ValueError):
        build_barcode_chars("100", "1-3-2")
