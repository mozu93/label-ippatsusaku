# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.label_import import _extract_direct_row, _cols_to_direct_row, DirectRow


def test_extract_direct_row_reads_company_name2():
    row = {"事業所名": "株式会社テスト", "事業所名2": "○○支店", "氏名": "山田太郎"}
    dr = _extract_direct_row(row)
    assert dr.company_name == "株式会社テスト"
    assert dr.company_name2 == "○○支店"


def test_extract_direct_row_company_name2_optional():
    row = {"事業所名": "株式会社テスト", "氏名": "山田太郎"}
    dr = _extract_direct_row(row)
    assert dr.company_name2 == ""


def test_cols_to_direct_row_with_company_name2():
    dr = _cols_to_direct_row(
        ["株式会社テスト", "○○支店", "山田太郎"],
        ["company_name", "company_name2", "person_name"],
    )
    assert dr.company_name == "株式会社テスト"
    assert dr.company_name2 == "○○支店"
    assert dr.person_name == "山田太郎"
