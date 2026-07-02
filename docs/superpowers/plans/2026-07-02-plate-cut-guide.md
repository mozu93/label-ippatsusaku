# 卓上プレート裁断ガイド点線 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 卓上プレート（`split4` モード / `a4_4split` レイアウト）のPDF出力で、A4用紙の右端から7mm内側にページ全体を貫く縦の点線（裁断ガイド）を描画する。

**Architecture:** `app/services/label_pdf_service.py` に新規ヘルパー関数 `_draw_plate_cut_guide()` を追加し、`generate_label_pdf()` 内で `layout_key == "a4_4split"` のときだけ、各ページ開始時（最初のページ・`c.showPage()` 直後）に呼び出す。

**Tech Stack:** Python, ReportLab（PDF生成）, PyMuPDF/`fitz`（テストでのPDF内容検証）, pytest

## Global Constraints

- 対象レイアウトは `a4_4split`（卓上プレート）のみ。他のレイアウトの描画結果を一切変更しない。
- 点線の位置: A4用紙右端（幅210mm、`page_w = A4[0]`）から7mm内側 → `x = page_w - 7 * mm`
- 点線の範囲: ページ上端(y=0)からページ下端(y=`layout.page_h_mm * mm`)まで貫く1本の連続した線
- 点線のスタイル: 色は既存の `C_BORDER`（`#CCCCCC`）、線幅0.3mm、ダッシュパターン `[2.0*mm, 1.5*mm]`
- 複数ページになる場合、各ページ先頭で同様に1本ずつ描画する
- 設計書: `docs/superpowers/specs/2026-07-02-plate-cut-guide-design.md`

---

### Task 1: 裁断ガイド点線の実装とテスト

**Files:**
- Create: `tests/test_label_pdf_service.py`
- Modify: `app/services/label_pdf_service.py`（`_label_origin` 関数の後に新規関数を追加、`generate_label_pdf()` 内2箇所を修正）

**Interfaces:**
- Consumes: `app.services.label_pdf_service.generate_label_pdf(entries, output_path, batch_mode="normal", layout_key=DEFAULT_LAYOUT_KEY, font_key=DEFAULT_FONT_KEY, barcode_enabled=False) -> str`（既存関数、シグネチャ変更なし）
- Produces: `_draw_plate_cut_guide(c: Canvas, layout: LabelLayout, page_w: float) -> None`（新規プライベート関数、`generate_label_pdf()` 内でのみ使用）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_label_pdf_service.py` を新規作成する:

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `python -m pytest tests/test_label_pdf_service.py -v`
Expected: `test_a4_4split_has_cut_guide_line` と `test_a4_4split_cut_guide_on_every_page` が
`assert len(lines) == 1`（実際は0件）で FAIL する。`test_other_layout_has_no_cut_guide_line` は
既にガイド線が存在しないため PASS する。

- [ ] **Step 3: `_draw_plate_cut_guide` 関数を追加する**

`app/services/label_pdf_service.py` の `_label_origin` 関数（166行目、`return x, y` の直後の空行）の
直後に以下を挿入する:

```python

# ══════════════════════════════════════════════════════════════════════
#  裁断ガイド（卓上プレート専用）
# ══════════════════════════════════════════════════════════════════════

def _draw_plate_cut_guide(c: Canvas, layout: LabelLayout, page_w: float) -> None:
    """
    卓上プレート（a4_4split）専用：印刷後にカットする目安として、
    用紙右端から7mm内側にページ全体を貫く縦の点線を描画する。
    """
    x = page_w - 7.0 * mm
    page_h = layout.page_h_mm * mm
    c.saveState()
    c.setStrokeColor(C_BORDER)
    c.setLineWidth(0.3 * mm)
    c.setDash([2.0 * mm, 1.5 * mm])
    c.line(x, 0, x, page_h)
    c.restoreState()
```

- [ ] **Step 4: `generate_label_pdf()` からガイド描画関数を呼び出す**

同ファイルの `generate_label_pdf()` 内、`c.setTitle("宛名ラベル")` の行の直後に以下を追加する:

```python
    c.setTitle("宛名ラベル")

    if layout_key == "a4_4split":
        _draw_plate_cut_guide(c, layout, page_w)
```

さらに、ページ送り処理（`if slot > 0 and slot % per_page == 0: c.showPage()`）を以下のように変更する:

変更前:
```python
        if slot > 0 and slot % per_page == 0:
            c.showPage()
```

変更後:
```python
        if slot > 0 and slot % per_page == 0:
            c.showPage()
            if layout_key == "a4_4split":
                _draw_plate_cut_guide(c, layout, page_w)
```

- [ ] **Step 5: テストを実行して成功を確認する**

Run: `python -m pytest tests/test_label_pdf_service.py -v`
Expected: 3件すべて PASS

- [ ] **Step 6: 既存テストに影響がないことを確認する**

Run: `python -m pytest -v`
Expected: 全テスト PASS（既存のテストが壊れていないこと）

- [ ] **Step 7: コミット**

```bash
git add app/services/label_pdf_service.py tests/test_label_pdf_service.py
git commit -m "$(cat <<'EOF'
feat: 卓上プレートに裁断ガイドの点線を追加

印刷後に用紙右端をカットする際の目安として、A4用紙右端から7mm内側に
縦の点線ガイドを追加する。a4_4split（卓上プレート）レイアウトのみが対象。
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** 設計書（`2026-07-02-plate-cut-guide-design.md`）の 2.1（位置）・2.2（スタイル）・
  2.3（回転プレートとの関係）・3（実装方針）・4（テスト）・5（影響範囲）は全てTask 1のコードで
  実装・検証される。DBスキーマ変更やUI変更は設計書に含まれないため対応タスクなし。
- **Placeholder scan:** TODO/TBD等のプレースホルダーなし。全ステップに実行可能な完全なコードを記載。
- **Type consistency:** `_draw_plate_cut_guide(c, layout, page_w)` の呼び出し側（Step 4、2箇所）と
  定義側（Step 3）でシグネチャ・引数順序が一致していることを確認済み。
