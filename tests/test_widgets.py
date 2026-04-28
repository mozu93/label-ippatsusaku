# -*- coding: utf-8 -*-
from app.ui.widgets import MODE_LABEL


def test_mode_label_keys():
    expected = {"normal", "no_person", "simple", "nametag", "split4"}
    assert set(MODE_LABEL.keys()) == expected


def test_mode_label_values_are_strings():
    for key, val in MODE_LABEL.items():
        assert isinstance(val, str), f"{key} の値が文字列でない"


def test_mode_label_content():
    assert MODE_LABEL["normal"]    == "宛名(氏名あり)"
    assert MODE_LABEL["no_person"] == "宛名(氏名なし)"
    assert MODE_LABEL["simple"]    == "事業所名のみ"
    assert MODE_LABEL["nametag"]   == "名札"
    assert MODE_LABEL["split4"]    == "卓上プレート"
