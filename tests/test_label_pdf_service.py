# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.services.label_pdf_service import generate_label_pdf


class _FakeEntry:
    """generate_label_pdf が参照する属性のみを持つ簡易エントリ"""
    def __init__(self, company_name="テスト株式会社", entry_mode="split4"):
        self.company_name    = company_name
        self.postal_code     = ""
        self.address1        = ""
        self.address2        = ""
        self.title           = ""
        self.person_name     = ""
        self.entry_mode      = entry_mode
        self.barcode_address = ""


_EXPECTED_X = A4[0] - 7 * mm


def _dashed_vlines(page):
    """ページ内の縦方向・点線（dashes指定あり）の描画パスを返す"""
    result = []
    for d in page.get_drawings():
        dashes = (d.get("dashes") or "").strip()
        if dashes in ("", "[] 0"):
            continue
        rect = d["rect"]
        if abs(rect.x0 - rect.x1) < 0.01:  # 縦線のみ対象
            result.append(d)
    return result


def test_a4_4split_has_cut_guide_line(tmp_path):
    out = str(tmp_path / "plate.pdf")
    generate_label_pdf(
        entries=[_FakeEntry()],
        output_path=out,
        batch_mode="split4",
        layout_key="a4_4split",
    )
    doc = fitz.open(out)
    lines = _dashed_vlines(doc[0])
    assert len(lines) == 1
    rect = lines[0]["rect"]
    assert rect.x0 == pytest.approx(_EXPECTED_X, abs=0.5)
    assert rect.y0 == pytest.approx(0.0, abs=0.5)
    assert rect.y1 == pytest.approx(A4[1], abs=0.5)


def test_a4_4split_cut_guide_on_every_page(tmp_path):
    out = str(tmp_path / "plate_multi.pdf")
    # a4_4split は各entryを2スロットに展開（per_page=4）。
    # 3件 → 6スロット → 2ページになる。
    generate_label_pdf(
        entries=[_FakeEntry() for _ in range(3)],
        output_path=out,
        batch_mode="split4",
        layout_key="a4_4split",
    )
    doc = fitz.open(out)
    assert doc.page_count == 2
    for page in doc:
        assert len(_dashed_vlines(page)) == 1


def test_other_layout_has_no_cut_guide_line(tmp_path):
    out = str(tmp_path / "normal.pdf")
    generate_label_pdf(
        entries=[_FakeEntry(entry_mode="simple")],
        output_path=out,
        batch_mode="simple",
        layout_key="a_one_28185",
    )
    doc = fitz.open(out)
    assert _dashed_vlines(doc[0]) == []
