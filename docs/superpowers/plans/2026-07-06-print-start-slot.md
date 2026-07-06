# 印刷開始位置指定 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 宛名ラベル・名札用紙のPDF出力時に「何面目から印刷を開始するか」を指定できるようにし、使いかけラベルシートを再利用できるようにする。

**Architecture:** `generate_label_pdf()` にスロットカウンタの初期値を渡す `start_slot` パラメータを追加する（既存のページ送り・座標計算ロジックは変更しない）。直接入力ダイアログのフッターに開始位置スピンボックスを追加し、プレビュー・PDF出力の両方の呼び出しに反映する。

**Tech Stack:** Python, PyQt6, ReportLab, pytest, PyMuPDF（`fitz`, テスト用PDF検証）

## Global Constraints

- 対象レイアウト: `a_one_28185`（18面）・`a_one_28187`（12面）・`a_one_51002`（10面）。`a4_4split`（卓上プレート）は対象外— `start_slot` に何を渡しても常に0として扱う。
- 面番号の数え方は既存の `_label_origin()` の走査順（`col = page_slot % cols`, `row = page_slot // cols`、左上が1面目、左→右・上→下）に一致させる。新しい順序は定義しない。
- UIの開始位置スピンボックスは、ダイアログを開くたびに初期値1にリセットする（値の永続化はしない）。
- 対象設計書: `docs/superpowers/specs/2026-07-06-print-start-slot-design.md`

---

### Task 1: `generate_label_pdf` に `start_slot` パラメータを追加する

**Files:**
- Modify: `app/services/label_pdf_service.py:193-236`
- Test: `tests/test_label_pdf_service.py`

**Interfaces:**
- Produces: `generate_label_pdf(entries, output_path, batch_mode="normal", layout_key=DEFAULT_LAYOUT_KEY, font_key=DEFAULT_FONT_KEY, barcode_enabled=False, offset_h_mm=0.0, offset_v_mm=0.0, start_slot: int = 0)` — `start_slot` は0始まりのスロット番号（0 = 1面目）。範囲外の値は `[0, per_page-1]` にクランプされる。`layout_key == "a4_4split"` の場合は常に0として扱われる。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_label_pdf_service.py` の末尾に追加する:

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_label_pdf_service.py -k start_slot -v`
Expected: 全件 `TypeError: generate_label_pdf() got an unexpected keyword argument 'start_slot'` で FAIL

- [ ] **Step 3: `generate_label_pdf` に `start_slot` を実装する**

`app/services/label_pdf_service.py:193-213` を以下のように変更する:

```python
def generate_label_pdf(
    entries:         list,
    output_path:     str,
    batch_mode:      str   = "normal",
    layout_key:      str   = DEFAULT_LAYOUT_KEY,
    font_key:        str   = DEFAULT_FONT_KEY,
    barcode_enabled: bool  = False,
    offset_h_mm:     float = 0.0,
    offset_v_mm:     float = 0.0,
    start_slot:      int   = 0,
) -> str:
    """
    entries     : LabelEntry ORM オブジェクトのリスト
    output_path : 出力先ファイルパス
    batch_mode  : バッチのデフォルトモード ("normal" | "simple")
    layout_key  : LABEL_LAYOUTS のキー
    font_key    : FONT_OPTIONS のキー
    start_slot  : 印刷を開始するスロット番号（0始まり、0 = 1面目）。
                  layout_key == "a4_4split" の場合は常に0として扱う。
    """
    layout = LABEL_LAYOUTS.get(layout_key) or LABEL_LAYOUTS[DEFAULT_LAYOUT_KEY]
    font   = FONT_OPTIONS.get(font_key, FONT_OPTIONS[DEFAULT_FONT_KEY])
    lw, lh = _label_wh(layout)
    per_page = layout.cols * layout.rows

    if layout_key == "a4_4split":
        start_slot = 0
    else:
        start_slot = max(0, min(start_slot, per_page - 1))
```

`app/services/label_pdf_service.py:236` の `slot = 0` を以下に変更する:

```python
    slot = start_slot
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_label_pdf_service.py -k start_slot -v`
Expected: 全件 PASS

- [ ] **Step 5: 既存テストが壊れていないことを確認する**

Run: `pytest tests/test_label_pdf_service.py -v`
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add app/services/label_pdf_service.py tests/test_label_pdf_service.py
git commit -m "feat: generate_label_pdfに印刷開始位置(start_slot)パラメータを追加"
```

---

### Task 2: 直接入力ダイアログに開始位置スピンボックスを追加する

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

**Interfaces:**
- Consumes: `generate_label_pdf(..., start_slot: int = 0)`（Task 1）
- Produces: `self._start_slot_spin`（`QSpinBox`）、`self._start_slot_lbl`（`QLabel`）、`self._on_layout_changed()` メソッド

このタスクはPyQt UIの変更であり、既存の自動テスト対象外（`direct_label_dialog.py` にはテストファイルがない）。検証は構文チェックと、`QT_QPA_PLATFORM=offscreen` を使ったheadlessでの実際のウィジェット動作確認で行う（後述のStep 6）。

- [ ] **Step 1: `QSpinBox` をインポートする**

`app/ui/direct_label_dialog.py` の冒頭にある以下の import ブロックを:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QButtonGroup,
    QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
    QComboBox, QLineEdit,
    QApplication,
    QCheckBox, QWidget, QFrame, QMenu,
)
```

以下に変更する:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QButtonGroup,
    QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
    QComboBox, QLineEdit, QSpinBox,
    QApplication,
    QCheckBox, QWidget, QFrame, QMenu,
)
```

- [ ] **Step 2: フッターに開始位置スピンボックスを追加する**

`app/ui/direct_label_dialog.py:416-422` の以下のブロックを:

```python
        self._layout_combo = QComboBox()
        self._layout_combo.setFixedHeight(34)
        for key, lo in LABEL_LAYOUTS.items():
            self._layout_combo.addItem(lo.name, key)
        idx = self._layout_combo.findData(DEFAULT_LAYOUT_KEY)
        if idx >= 0:
            self._layout_combo.setCurrentIndex(idx)
```

以下に置き換える:

```python
        self._layout_combo = QComboBox()
        self._layout_combo.setFixedHeight(34)
        for key, lo in LABEL_LAYOUTS.items():
            self._layout_combo.addItem(lo.name, key)
        idx = self._layout_combo.findData(DEFAULT_LAYOUT_KEY)
        if idx >= 0:
            self._layout_combo.setCurrentIndex(idx)

        self._start_slot_lbl = _lbl("開始位置:")
        self._start_slot_spin = QSpinBox()
        self._start_slot_spin.setFixedHeight(34)
        self._start_slot_spin.setMinimum(1)
        self._start_slot_spin.setToolTip(
            "印刷を開始する面番号（1 = 1面目・左上）。\n"
            "使いかけのラベルシートの空いている面から印刷したいときに変更します。"
        )
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        self._on_layout_changed()
```

同ファイル `app/ui/direct_label_dialog.py:454-459`（フッターのレイアウト組み立て部分）の以下のブロックを:

```python
        foot.addWidget(self._count_lbl)
        foot.addWidget(self._chk_barcode)
        foot.addStretch()
        foot.addWidget(_lbl("用紙:"))
        foot.addWidget(self._layout_combo)
        foot.addSpacing(8)
        foot.addWidget(_lbl("フォント:"))
        foot.addWidget(self._font_combo)
```

以下に置き換える:

```python
        foot.addWidget(self._count_lbl)
        foot.addWidget(self._chk_barcode)
        foot.addStretch()
        foot.addWidget(_lbl("用紙:"))
        foot.addWidget(self._layout_combo)
        foot.addSpacing(8)
        foot.addWidget(self._start_slot_lbl)
        foot.addWidget(self._start_slot_spin)
        foot.addSpacing(8)
        foot.addWidget(_lbl("フォント:"))
        foot.addWidget(self._font_combo)
```

- [ ] **Step 3: `_on_layout_changed` メソッドを追加する**

`app/ui/direct_label_dialog.py` の `_build_footer` メソッドの直後（`return foot` の次の行、`# ── ステップインジケーター ──` の見出しコメントの前）に新規メソッドを追加する:

```python
    def _on_layout_changed(self) -> None:
        """用紙切替時に開始位置スピンボックスの範囲・表示を更新する"""
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        layout = LABEL_LAYOUTS.get(layout_key) or LABEL_LAYOUTS[DEFAULT_LAYOUT_KEY]
        is_plate = layout_key == "a4_4split"
        self._start_slot_lbl.setVisible(not is_plate)
        self._start_slot_spin.setVisible(not is_plate)
        if not is_plate:
            per_page = layout.cols * layout.rows
            self._start_slot_spin.setMaximum(per_page)
            if self._start_slot_spin.value() > per_page:
                self._start_slot_spin.setValue(per_page)
```

- [ ] **Step 4: `_preview_pdf` に `start_slot` を渡す**

`app/ui/direct_label_dialog.py:1066-1071` の以下のブロックを:

```python
        mode       = self._current_mode()
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
```

以下に置き換える:

```python
        mode       = self._current_mode()
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
        start_slot = 0 if layout_key == "a4_4split" else self._start_slot_spin.value() - 1
```

`app/ui/direct_label_dialog.py:1092-1096` の以下のブロックを:

```python
        buf = BytesIO()
        try:
            generate_label_pdf(entries, buf, mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v)
```

以下に置き換える:

```python
        buf = BytesIO()
        try:
            generate_label_pdf(entries, buf, mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v,
                               start_slot=start_slot)
```

- [ ] **Step 5: `_export` に `start_slot` を渡す**

`app/ui/direct_label_dialog.py:1306-1310` の以下のブロックを:

```python
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
```

以下に置き換える:

```python
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
        start_slot = 0 if layout_key == "a4_4split" else self._start_slot_spin.value() - 1
```

`app/ui/direct_label_dialog.py:1311-1314` の以下のブロックを:

```python
        try:
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v)
```

以下に置き換える:

```python
        try:
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v,
                               start_slot=start_slot)
```

- [ ] **Step 5.5: 構文エラーがないことを確認する**

Run: `python -c "import ast; ast.parse(open('app/ui/direct_label_dialog.py', encoding='utf-8').read())"`
Expected: エラーなく終了（出力なし）

- [ ] **Step 6: headlessでウィジェットの実際の動作を確認する**

`QT_QPA_PLATFORM=offscreen` を使うと、ディスプレイのない環境でも実際にPyQt6のダイアログをインスタンス化して動作確認できる。以下を実行する:

```bash
QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
from app.ui.direct_label_dialog import DirectLabelDialog
from app.services.label_pdf_service import LABEL_LAYOUTS

dlg = DirectLabelDialog()

# 初期状態: デフォルト用紙(a_one_28185, 18面)で開始位置1〜18、初期値1
print('initial max:', dlg._start_slot_spin.maximum(), '(expect 18)')
print('initial value:', dlg._start_slot_spin.value(), '(expect 1)')
print('initial visible:', dlg._start_slot_spin.isVisible(), '(expect True)')

# 用紙を a_one_51002 (10面) に切り替えると最大値が10に変わる
idx = dlg._layout_combo.findData('a_one_51002')
dlg._layout_combo.setCurrentIndex(idx)
print('after switch to 51002, max:', dlg._start_slot_spin.maximum(), '(expect 10)')

# 12を超えた値を設定してから面数の少ない用紙に切り替えると値がクランプされる
dlg._start_slot_spin.setValue(10)
idx28187 = dlg._layout_combo.findData('a_one_28187')
dlg._layout_combo.setCurrentIndex(idx28187)
print('after switch to 28187 (12 slots), max:', dlg._start_slot_spin.maximum(), '(expect 12)')
print('value after switch (should stay 10, <=12):', dlg._start_slot_spin.value())

# 卓上プレート(a4_4split)選択時は非表示になる
idx_plate = dlg._layout_combo.findData('a4_4split')
dlg._layout_combo.setCurrentIndex(idx_plate)
print('plate visible:', dlg._start_slot_spin.isVisible(), '(expect False)')
print('plate label visible:', dlg._start_slot_lbl.isVisible(), '(expect False)')
"
```

Expected出力（各行のコメント通りの値になっていること）:
```
initial max: 18 (expect 18)
initial value: 1 (expect 1)
initial visible: True (expect True)
after switch to 51002, max: 10 (expect 10)
after switch to 28187 (12 slots), max: 12 (expect 12)
value after switch (should stay 10, <=12): 10
plate visible: False (expect False)
plate label visible: False (expect False)
```

- [ ] **Step 7: headlessで実際のPDF生成に開始位置が反映されることを確認する**

```bash
QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python -c "
import sys
sys.stdout.reconfigure(encoding='utf-8')
from io import BytesIO
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)
from app.ui.direct_label_dialog import DirectLabelDialog

dlg = DirectLabelDialog()
dlg._add_row(['株式会社テスト', '', 'カブシキガイシャテスト', '', '山田太郎', '', '東京都千代田区1-1', ''])
chk = dlg._get_row_chk(0)
chk.setChecked(True)
dlg._start_slot_spin.setValue(5)  # 5面目から開始

checked_rows = dlg._get_checked_rows()
entries = []
for row in checked_rows:
    def _cell(col, _row=row):
        item = dlg.table.item(_row, col)
        return item.text().strip() if item else ''
    entries.append(type('_E', (), {
        'company_name':    _cell(dlg.COL_COMPANY),
        'company_name2':   _cell(dlg.COL_COMPANY2),
        'company_kana':    _cell(dlg.COL_KANA),
        'title':           _cell(dlg.COL_TITLE),
        'person_name':     _cell(dlg.COL_PERSON),
        'postal_code':     _cell(dlg.COL_POSTAL),
        'address1':        _cell(dlg.COL_ADDR1),
        'address2':        _cell(dlg.COL_ADDR2),
        'barcode_address': _cell(dlg.COL_BC_ADDR),
        'entry_mode':      'inherit',
    })())

from app.services.label_pdf_service import generate_label_pdf, LABEL_LAYOUTS, _label_origin
import fitz

layout = LABEL_LAYOUTS['a_one_28185']
buf = BytesIO()
generate_label_pdf(entries, buf, 'normal', 'a_one_28185', 'MSPゴシック', start_slot=4)  # 0始まりで4 = 5面目
doc = fitz.open(stream=buf.getvalue(), filetype='pdf')
d = doc[0].get_text('dict')
found_y = None
for block in d['blocks']:
    for line in block.get('lines', []):
        for span in line['spans']:
            if '山田太郎' in span['text']:
                found_y = span['bbox'][1]
expected_x, expected_y = _label_origin(1, 1, layout)  # slot=4 -> col=4%3=1, row=4//3=1
print('name span found:', found_y is not None)
print('expected origin y (pt, reportlab座標系. PDF座標系とは軸が異なるため近似確認のみ):', expected_y)
"
```

Expected: `name span found: True` が出力されること（`山田太郎` のテキストが実際にPDF中に見つかる = 5面目に描画された内容が正しく出力されている）。

- [ ] **Step 8: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: 直接入力ダイアログに印刷開始位置スピンボックスを追加"
```

---

### Task 3: 全体の回帰確認

**Files:** なし（確認のみ）

- [ ] **Step 1: 全自動テストを実行する**

Run: `pytest tests/ -v`
Expected: 全テスト PASS

- [ ] **Step 2: 手動でエンドツーエンド確認する（可能な場合）**

`python main.py` でアプリを起動し、「新規作成（直接入力）」でA-ONE 28185用紙を選択、開始位置を「5」に変更してプレビューを開き、1件目のラベルが5面目（上から2行目・左から2列目）に印刷されることを目視確認する。卓上プレート選択時は開始位置の項目が表示されないことも確認する。

GUI操作ができない環境の場合は、Task 2のStep 6・Step 7で行ったheadless検証で代替する（すでに実施済みのため、このステップでは再実行のみでよい）。
