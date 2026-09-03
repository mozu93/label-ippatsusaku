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


def test_layout_person_line_short_name_fits_one_line():
    lines, fs = svc._layout_person_line("山田太郎", "MSPGothic", 11.0, 80 * mm)
    assert lines == ["山田太郎　様"]
    assert fs == pytest.approx(11.0)


def test_layout_person_line_existing_honorific_not_duplicated():
    lines, fs = svc._layout_person_line("山田太郎様", "MSPGothic", 11.0, 80 * mm)
    assert lines == ["山田太郎様"]


def test_layout_person_line_existing_honorific_with_whitespace():
    lines, fs = svc._layout_person_line("山田太郎様  ", "MSPGothic", 11.0, 80 * mm)
    assert lines == ["山田太郎様"]


def test_layout_person_line_long_text_wraps_to_two_lines():
    long_name = "代表取締役社長　山田太郎様"
    lines, fs = svc._layout_person_line(long_name, "MSPGothic", 11.0, 25 * mm)
    assert len(lines) == 2
    assert "".join(lines) == long_name
    assert fs <= 9.0


def test_layout_person_line_two_lines_fit_within_avail_width():
    long_name = "代表取締役社長　山田太郎様"
    avail_w = 25 * mm
    lines, fs = svc._layout_person_line(long_name, "MSPGothic", 11.0, avail_w)
    from reportlab.pdfbase.pdfmetrics import stringWidth
    for line in lines:
        assert stringWidth(line, "MSPGothic", fs) <= avail_w + 0.01


def test_draw_normal_wraps_long_person_name_into_two_drawstring_calls():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    c = Canvas(BytesIO())
    drawn = []
    orig_draw_string = c.drawString
    def _spy(x, y, text, **kw):
        drawn.append((x, y, text))
        return orig_draw_string(x, y, text, **kw)
    c.drawString = _spy

    long_name = "特別顧問兼代表取締役社長最高経営責任者　山田太郎様"
    svc._draw_normal(c, x0=0, y0=0, w=70 * mm, h=42.3 * mm,
                      company="", postal="", addr1="", addr2="",
                      title="", person=long_name, font="MSPGothic")

    # company/postal/addr1/addr2/title が全て空のため、drawString 呼び出しは
    # 氏名ブロックの分だけになる（1行なら1件、2行なら2件）
    assert len(drawn) == 2
    ys = {round(y, 1) for _, y, _ in drawn}
    assert len(ys) == 2
    top, bottom = sorted(drawn, key=lambda d: -d[1])
    assert top[2] + bottom[2] == long_name


def test_draw_normal_short_person_name_single_drawstring_call():
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    c = Canvas(BytesIO())
    drawn = []
    orig_draw_string = c.drawString
    def _spy(x, y, text, **kw):
        drawn.append((x, y, text))
        return orig_draw_string(x, y, text, **kw)
    c.drawString = _spy

    svc._draw_normal(c, x0=0, y0=0, w=70 * mm, h=42.3 * mm,
                      company="", postal="", addr1="", addr2="",
                      title="", person="山田太郎", font="MSPGothic")

    assert len(drawn) == 1
    assert drawn[0][2] == "山田太郎　様"


_LONG_ADDR1 = (
    "東京都千代田区丸の内一丁目1番1号丸の内センタービルディング"
    "南館西棟高層階10階1001号室ABCオフィス内サンプル部門"
)


def _label_bottom_fitz(layout_key="a_one_28185"):
    """generate_label_pdf の1面目ラベルの下端をfitz座標系（Y軸上から下）で返す。"""
    layout = svc.LABEL_LAYOUTS[layout_key]
    _, y0 = svc._label_origin(0, 0, layout)
    return layout.page_h_mm * mm - y0


def _all_span_bboxes(path):
    doc = fitz.open(path)
    page = doc[0]
    d = page.get_text("dict")
    boxes = []
    for block in d["blocks"]:
        for line in block.get("lines", []):
            for span in line["spans"]:
                boxes.append((span["bbox"][1], span["bbox"][3], span["text"]))
    return boxes


def test_generate_label_pdf_long_address_does_not_overflow_label(tmp_path):
    """住所が長く自動折り返しの行数が増えても、後続要素（会社名・役職・氏名）
    がラベル下端の外側に描画されないことを確認する（はみ出し防止のリグレッション）。"""
    entry = _FakeEntry(company_name="テスト商事株式会社大阪支店営業第一課", entry_mode="normal")
    entry.postal_code  = "123-4567"
    entry.address1     = _LONG_ADDR1
    entry.address2     = "気付　株式会社サンプル内　総務部宛"
    entry.title        = "取締役執行役員営業本部長兼海外事業部担当"
    entry.person_name  = "山田太郎"

    out = str(tmp_path / "long_addr.pdf")
    generate_label_pdf([entry], out, batch_mode="normal", layout_key="a_one_28185")

    bottom = _label_bottom_fitz()
    boxes = _all_span_bboxes(out)
    assert boxes
    overflowing = [b for b in boxes if b[1] > bottom + 0.5]
    assert overflowing == []


def test_generate_label_pdf_long_address_does_not_overlap_person_line(tmp_path):
    """長い住所で会社名・役職が下に押し出されても、氏名行と重ならない
    （行間圧縮によって衝突を避けられている）ことを確認する。"""
    entry = _FakeEntry(company_name="テスト商事株式会社", entry_mode="normal")
    entry.postal_code  = "123-4567"
    entry.address1     = _LONG_ADDR1
    entry.title        = "営業部長"
    entry.person_name  = "山田太郎"

    out = str(tmp_path / "long_addr_overlap.pdf")
    generate_label_pdf([entry], out, batch_mode="normal", layout_key="a_one_28185")

    boxes = _all_span_bboxes(out)
    person_boxes = [b for b in boxes if "山田太郎" in b[2]]
    other_boxes  = [b for b in boxes if "山田太郎" not in b[2]]
    assert person_boxes and other_boxes
    # 氏名行の上端(top)が、それ以外の要素の下端(bottom)より下に来ないこと（重なり無し）
    person_top = min(b[0] for b in person_boxes)
    others_bottom = max(b[1] for b in other_boxes)
    assert person_top >= others_bottom - 0.5


def test_generate_label_pdf_no_person_long_address_does_not_overflow_label(tmp_path):
    """氏名なしモードでも、住所が長く折り返し行数が増えたときに事業所名／
    御中がラベル下端の外側に描画されないことを確認する。"""
    entry = _FakeEntry(company_name="テスト商事株式会社大阪支店営業第一課", entry_mode="no_person")
    entry.postal_code  = "123-4567"
    entry.address1     = _LONG_ADDR1 + "東西南北ビル"

    out = str(tmp_path / "long_addr_no_person.pdf")
    generate_label_pdf([entry], out, batch_mode="normal", layout_key="a_one_28185")

    bottom = _label_bottom_fitz()
    boxes = _all_span_bboxes(out)
    assert boxes
    overflowing = [b for b in boxes if b[1] > bottom + 0.5]
    assert overflowing == []


def test_generate_label_pdf_start_slot_shifts_first_entry_origin():
    """start_slot を指定すると、最初のエントリがそのスロットの座標に描画される"""
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = []

    def fake_draw_label(c, entry, x0, y0, w, h, mode, font, barcode_enabled=False):
        captured.append((x0, y0))

    orig = svc._draw_label
    svc._draw_label = fake_draw_label
    try:
        layout = svc.LABEL_LAYOUTS["a_one_28185"]
        buf = BytesIO()
        generate_label_pdf([_FakeEntry(entry_mode="normal")], buf,
                            batch_mode="normal", layout_key="a_one_28185",
                            start_slot=5)
    finally:
        svc._draw_label = orig

    # start_slot=5 (0始まり) → page_slot=5, col=5%3=2, row=5//3=1
    expected_x0, expected_y0 = svc._label_origin(2, 1, layout)
    assert captured[0] == pytest.approx((expected_x0, expected_y0))


def test_generate_label_pdf_start_slot_default_is_first_slot():
    """start_slot 省略時は従来通り1面目（col=0, row=0）から描画される"""
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = []

    def fake_draw_label(c, entry, x0, y0, w, h, mode, font, barcode_enabled=False):
        captured.append((x0, y0))

    orig = svc._draw_label
    svc._draw_label = fake_draw_label
    try:
        layout = svc.LABEL_LAYOUTS["a_one_28185"]
        buf = BytesIO()
        generate_label_pdf([_FakeEntry(entry_mode="normal")], buf,
                            batch_mode="normal", layout_key="a_one_28185")
    finally:
        svc._draw_label = orig

    expected_x0, expected_y0 = svc._label_origin(0, 0, layout)
    assert captured[0] == pytest.approx((expected_x0, expected_y0))


def test_generate_label_pdf_start_slot_crosses_page_boundary():
    """18面用紙で start_slot=17（最終面）から2件出力すると2ページ目に送られる"""
    out = None
    import tempfile, os
    fd, out = tempfile.mkstemp(suffix=".pdf")
    os.close(fd)
    try:
        generate_label_pdf(
            [_FakeEntry(entry_mode="normal"), _FakeEntry(entry_mode="normal")],
            out, batch_mode="normal", layout_key="a_one_28185", start_slot=17,
        )
        doc = fitz.open(out)
        assert doc.page_count == 2
        doc.close()
    finally:
        os.remove(out)


def test_generate_label_pdf_start_slot_clamped_when_out_of_range():
    """面数以上・負の値を渡してもクランプされ例外にならない"""
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    captured = []

    def fake_draw_label(c, entry, x0, y0, w, h, mode, font, barcode_enabled=False):
        captured.append((x0, y0))

    orig = svc._draw_label
    svc._draw_label = fake_draw_label
    try:
        layout = svc.LABEL_LAYOUTS["a_one_28185"]  # per_page = 18
        buf = BytesIO()
        generate_label_pdf([_FakeEntry(entry_mode="normal")], buf,
                            batch_mode="normal", layout_key="a_one_28185",
                            start_slot=999)
        # per_page-1 = 17 にクランプ → col=17%3=2, row=17//3=5
        expected_over = svc._label_origin(2, 5, layout)
        assert captured[-1] == pytest.approx(expected_over)

        captured.clear()
        buf2 = BytesIO()
        generate_label_pdf([_FakeEntry(entry_mode="normal")], buf2,
                            batch_mode="normal", layout_key="a_one_28185",
                            start_slot=-3)
        # 0 にクランプ
        expected_neg = svc._label_origin(0, 0, layout)
        assert captured[-1] == pytest.approx(expected_neg)
    finally:
        svc._draw_label = orig


def test_generate_label_pdf_start_slot_ignored_for_a4_4split():
    """卓上プレート（a4_4split）は start_slot を無視して常に先頭から出力する

    PDFバイト列にはReportLabが埋め込む生成時刻等が含まれ得るため、
    バイト比較ではなく実際の描画呼び出し（座標・回転状態）を比較する。
    """
    from io import BytesIO
    from reportlab.pdfgen.canvas import Canvas

    entry = _FakeEntry(company_name="テスト株式会社", entry_mode="split4")
    captured_runs = []

    def fake_draw_label(c, entry, x0, y0, w, h, mode, font, barcode_enabled=False):
        captured_runs[-1].append((round(x0, 3), round(y0, 3)))

    orig = svc._draw_label
    svc._draw_label = fake_draw_label
    try:
        captured_runs.append([])
        generate_label_pdf([entry], BytesIO(), batch_mode="split4", layout_key="a4_4split")
        captured_runs.append([])
        generate_label_pdf([entry], BytesIO(), batch_mode="split4", layout_key="a4_4split",
                            start_slot=5)
    finally:
        svc._draw_label = orig

    assert len(captured_runs[0]) > 0
    assert captured_runs[0] == captured_runs[1]
