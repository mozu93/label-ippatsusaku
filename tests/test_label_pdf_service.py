# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import fitz
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.services.label_pdf_service import generate_label_pdf
from app.services import label_pdf_service as svc


class _FakeEntry:
    """generate_label_pdf が参照する属性のみを持つ簡易エントリ"""
    def __init__(self, company_name="テスト株式会社", entry_mode="split4", company_name2=""):
        self.company_name    = company_name
        self.company_name2   = company_name2
        self.postal_code     = ""
        self.address1        = ""
        self.address2        = ""
        self.title           = ""
        self.person_name     = ""
        self.entry_mode      = entry_mode
        self.barcode_address = ""


_EXPECTED_X = A4[0] - 11 * mm


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


def test_label_origin_applies_offset():
    layout = svc.LABEL_LAYOUTS["a_one_28185"]
    x0, y0 = svc._label_origin(0, 0, layout)
    x1, y1 = svc._label_origin(0, 0, layout, offset_h_mm=3.0, offset_v_mm=-2.0)
    assert x1 == pytest.approx(x0 + 3.0 * mm)
    assert y1 == pytest.approx(y0 + 2.0 * mm)


def test_label_origin_default_offset_is_unchanged():
    layout = svc.LABEL_LAYOUTS["a_one_28185"]
    x0, y0 = svc._label_origin(1, 2, layout)
    x1, y1 = svc._label_origin(1, 2, layout, 0.0, 0.0)
    assert x0 == pytest.approx(x1)
    assert y0 == pytest.approx(y1)


def test_draw_label_applies_safety_margin_for_normal_mode():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = {}

    def fake_draw_normal(c, x0, y0, w, h, *args, **kwargs):
        captured.update(x0=x0, y0=y0, w=w, h=h)

    orig = svc._draw_normal
    svc._draw_normal = fake_draw_normal
    try:
        c = Canvas(BytesIO())
        entry = _FakeEntry(entry_mode="normal")
        svc._draw_label(c, entry, x0=10.0, y0=20.0, w=200.0, h=100.0, mode="normal")
    finally:
        svc._draw_normal = orig

    assert captured["x0"] == pytest.approx(10.0 + svc._SAFETY_H)
    assert captured["y0"] == pytest.approx(20.0 + svc._SAFETY_V)
    assert captured["w"]  == pytest.approx(200.0 - 2 * svc._SAFETY_H)
    assert captured["h"]  == pytest.approx(100.0 - 2 * svc._SAFETY_V)


def test_draw_label_applies_plate_safety_margin_for_split4_mode():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = {}

    def fake_draw_split4(c, x0, y0, w, h, *args, **kwargs):
        captured.update(x0=x0, y0=y0, w=w, h=h)

    orig = svc._draw_split4
    svc._draw_split4 = fake_draw_split4
    try:
        c = Canvas(BytesIO())
        entry = _FakeEntry(entry_mode="split4")
        svc._draw_label(c, entry, x0=10.0, y0=20.0, w=200.0, h=100.0, mode="split4")
    finally:
        svc._draw_split4 = orig

    assert captured["x0"] == pytest.approx(10.0 + svc._SAFETY_PLATE)
    assert captured["y0"] == pytest.approx(20.0 + svc._SAFETY_PLATE)
    assert captured["w"]  == pytest.approx(200.0 - 2 * svc._SAFETY_PLATE)
    assert captured["h"]  == pytest.approx(100.0 - 2 * svc._SAFETY_PLATE)


def test_generate_label_pdf_offset_shifts_rendered_text(tmp_path):
    """generate_label_pdf の offset_h_mm/offset_v_mm が実際のPDF描画位置に
    正しく反映されることを、fitzでテキスト位置を読み取って確認する結合テスト。

    reportlab(Y軸: 下から上)とfitz(テキストbbox: Y軸上から下)の座標系の違いを
    実測した上で導出した関係式を使う:
      fitz上でのXの差分 = offset_h_mm * mm （符号反転なし）
      fitz上でのYの差分 = offset_v_mm * mm （Y軸反転が2回起きるため符号反転なしで一致）
    """
    entry = _FakeEntry(company_name="オフセットテスト株式会社", entry_mode="normal")
    entry.postal_code = "1000001"
    entry.address1 = "東京都千代田区"

    out0 = str(tmp_path / "base.pdf")
    out1 = str(tmp_path / "offset.pdf")

    generate_label_pdf([entry], out0, batch_mode="normal", layout_key="a_one_28185")
    generate_label_pdf([entry], out1, batch_mode="normal", layout_key="a_one_28185",
                        offset_h_mm=5.0, offset_v_mm=-3.0)

    def _find_span_xy(path, text):
        doc = fitz.open(path)
        page = doc[0]
        d = page.get_text("dict")
        for block in d["blocks"]:
            for line in block.get("lines", []):
                for span in line["spans"]:
                    if text in span["text"]:
                        return span["bbox"][0], span["bbox"][1]
        raise AssertionError(f"{text!r} not found in {path}")

    x0, y0 = _find_span_xy(out0, "1000001")
    x1, y1 = _find_span_xy(out1, "1000001")

    assert x1 - x0 == pytest.approx(5.0 * mm, abs=0.5)
    assert y1 - y0 == pytest.approx(-3.0 * mm, abs=0.5)


def test_draw_label_combines_company_name_and_name2():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = {}

    def fake_draw_normal(c, x0, y0, w, h, company, *args, **kwargs):
        captured["company"] = company

    orig = svc._draw_normal
    svc._draw_normal = fake_draw_normal
    try:
        c = Canvas(BytesIO())
        entry = _FakeEntry(company_name="株式会社テスト", entry_mode="normal",
                           company_name2="○○支店")
        svc._draw_label(c, entry, x0=0.0, y0=0.0, w=200.0, h=100.0, mode="normal")
    finally:
        svc._draw_normal = orig

    assert captured["company"] == "株式会社テスト\n○○支店"


def test_draw_label_company_name2_empty_does_not_add_newline():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = {}

    def fake_draw_normal(c, x0, y0, w, h, company, *args, **kwargs):
        captured["company"] = company

    orig = svc._draw_normal
    svc._draw_normal = fake_draw_normal
    try:
        c = Canvas(BytesIO())
        entry = _FakeEntry(company_name="株式会社テスト", entry_mode="normal")
        svc._draw_label(c, entry, x0=0.0, y0=0.0, w=200.0, h=100.0, mode="normal")
    finally:
        svc._draw_normal = orig

    assert captured["company"] == "株式会社テスト"


def test_draw_label_tolerates_missing_company_name2_attribute():
    """company_name2属性がないエントリでもgetattr()で安全に処理できることを確認"""
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    # company_name2属性を持たないミニマルなエントリオブジェクト
    NoCompany2Entry = type("_NoCompany2Entry", (), {
        "company_name": "株式会社テスト",
        "postal_code": "",
        "address1": "",
        "address2": "",
        "title": "",
        "person_name": "",
        "entry_mode": "normal",
        "barcode_address": "",
    })
    entry = NoCompany2Entry()

    # _draw_label がAttributeErrorを発生させず、正常に動作することを確認
    c = Canvas(BytesIO())
    # getattr(entry, "company_name2", "") が正しく "" を返すことで、
    # 例外が発生しない
    svc._draw_label(c, entry, x0=0.0, y0=0.0, w=200.0, h=100.0, mode="normal")
