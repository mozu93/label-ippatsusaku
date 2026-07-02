# 宛名ラベル印刷位置補正 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 姉妹アプリ `cci-billing-label` で実施された宛名ラベル印刷位置の補正（クリップパス・安全余白・ユーザー調整可能なオフセット設定）を本アプリに移植する。

**Architecture:** `label_pdf_service.py` の `_draw_label`/`_label_origin`/`generate_label_pdf` にクリップパス・安全余白・オフセットパラメータを追加し、`app_config.py` にオフセット値の永続化関数を追加、`main_window.py` にファイルメニューから開く新規ダイアログ `print_offset_dialog.py` を追加し、`direct_label_dialog.py` の2箇所のPDF生成呼び出しでオフセット値を読み込んで渡す。

**Tech Stack:** Python, PyQt6, ReportLab, pytest

## Global Constraints

- 対象モード: `normal` / `no_person` / `nametag` / `simple` の4モードのみ。`split4`（卓上プレート）は安全余白・オフセットの対象外。
- クリップパスは全モード共通（`split4` 含む）で `_draw_label` 内、モード分岐の前に適用する。
- 安全余白: 水平 `_SAFETY_H = 5.0 * mm`（左右各5mm）、垂直 `_SAFETY_V = 2.0 * mm`（上下各2mm）。
- オフセットパラメータ名: `generate_label_pdf(..., offset_h_mm: float = 0.0, offset_v_mm: float = 0.0)`。`_label_origin()` の `margin_left_mm` / `margin_top_mm` に加算する。
- オフセットの永続化は `app/utils/app_config.py`（JSON設定ファイル）に追加する関数 `get_label_offset(layout_key) -> tuple[float, float]` / `save_label_offset(layout_key, h_mm, v_mm) -> None` を使う。**既存の `_DEFAULTS` 辞書は変更しない**（ミュータブルな値を追加すると `dict(_DEFAULTS)` の浅いコピーにより `_DEFAULTS` 自体が書き換わるバグになるため）。
- 対象レイアウトキー: `a_one_28185`, `a_one_28187`, `a_one_51002`（`a4_4split` は除外）。
- 補正値の範囲: -15.0〜15.0mm、0.5mm刻み、小数点1桁。
- ファイルメニュー項目名: 「印刷位置補正...」。ダイアログクラス名: `PrintOffsetDialog`（`app/ui/print_offset_dialog.py`）、固定サイズ 480×400px。
- 設計書: `docs/superpowers/specs/2026-07-02-print-position-correction-design.md`

---

### Task 1: `app_config.py` にオフセット保存関数を追加

**Files:**
- Modify: `app/utils/app_config.py`
- Test: `tests/test_app_config.py`（新規）

**Interfaces:**
- Produces: `get_label_offset(layout_key: str) -> tuple[float, float]`,
  `save_label_offset(layout_key: str, h_mm: float, v_mm: float) -> None`
  （いずれも `app.utils.app_config` モジュールの公開関数。後続タスクが import して使う）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_app_config.py` を新規作成する:

```python
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils import app_config


def _use_tmp_config(monkeypatch, tmp_path):
    cfg_dir = str(tmp_path)
    monkeypatch.setattr(app_config, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", os.path.join(cfg_dir, "config.json"))


def test_get_label_offset_default_is_zero(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    h, v = app_config.get_label_offset("a_one_28185")
    assert h == 0.0
    assert v == 0.0


def test_save_and_get_label_offset_roundtrip(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 2.5, -1.0)
    h, v = app_config.get_label_offset("a_one_28185")
    assert h == 2.5
    assert v == -1.0


def test_save_label_offset_keeps_other_layouts_independent(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 1.0, 1.0)
    app_config.save_label_offset("a_one_28187", -2.0, 3.0)
    h1, v1 = app_config.get_label_offset("a_one_28185")
    h2, v2 = app_config.get_label_offset("a_one_28187")
    assert (h1, v1) == (1.0, 1.0)
    assert (h2, v2) == (-2.0, 3.0)


def test_save_label_offset_does_not_mutate_defaults(monkeypatch, tmp_path):
    """_DEFAULTS を変更しない設計であることの回帰テスト:
    保存後に _DEFAULTS['label_offset'] のようなキーが増えていないことを確認する。
    """
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_51002", 9.0, 9.0)
    assert "label_offset" not in app_config._DEFAULTS
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `python -m pytest tests/test_app_config.py -v`
Expected: `AttributeError: module 'app.utils.app_config' has no attribute 'get_label_offset'` で FAIL

- [ ] **Step 3: `app_config.py` に関数を追加する**

`app/utils/app_config.py` の末尾（`set_direct_label_save_path` の後）に以下を追加する:

```python


def get_label_offset(layout_key: str) -> tuple[float, float]:
    entry = _load().get("label_offset", {}).get(layout_key, {})
    return entry.get("h_mm", 0.0), entry.get("v_mm", 0.0)


def save_label_offset(layout_key: str, h_mm: float, v_mm: float) -> None:
    cfg = _load()
    cfg.setdefault("label_offset", {})[layout_key] = {"h_mm": h_mm, "v_mm": v_mm}
    _save(cfg)
```

`_DEFAULTS` 辞書は変更しない。

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `python -m pytest tests/test_app_config.py -v`
Expected: 4件 PASS

- [ ] **Step 5: コミット**

```bash
git add app/utils/app_config.py tests/test_app_config.py
git commit -m "$(cat <<'EOF'
feat: app_configにラベル印刷位置オフセットの保存機能を追加

レイアウトごとの横・縦オフセット(mm)をJSON設定ファイルに保存・読込する。
EOF
)"
```

---

### Task 2: `label_pdf_service.py` にクリップパス・安全余白・オフセットパラメータを追加

**Files:**
- Modify: `app/services/label_pdf_service.py`
- Test: `tests/test_label_pdf_service.py`（既存ファイルに追記）

**Interfaces:**
- Consumes: なし（Task 1とは独立したファイル）
- Produces: `generate_label_pdf(entries, output_path, batch_mode="normal", layout_key=DEFAULT_LAYOUT_KEY, font_key=DEFAULT_FONT_KEY, barcode_enabled=False, offset_h_mm: float = 0.0, offset_v_mm: float = 0.0) -> str`
  （`offset_h_mm`/`offset_v_mm` の2引数が追加される。Task 4がこれを呼び出す）

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_label_pdf_service.py` の末尾に以下を追記する（ファイル冒頭で
`from reportlab.lib.units import mm` は既にimport済み。`from app.services import label_pdf_service as svc`
を追加importする）:

```python
from app.services import label_pdf_service as svc


def test_label_origin_applies_offset():
    layout = svc.LABEL_LAYOUTS["a_one_28185"]
    x0, y0 = svc._label_origin(0, 0, layout)
    x1, y1 = svc._label_origin(0, 0, layout, offset_h_mm=3.0, offset_v_mm=-2.0)
    assert x1 == pytest.approx(x0 + 3.0 * mm)
    assert y1 == pytest.approx(y0 - 2.0 * mm)


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


def test_draw_label_skips_safety_margin_for_split4_mode():
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

    assert captured == {"x0": 10.0, "y0": 20.0, "w": 200.0, "h": 100.0}
```

`tests/test_label_pdf_service.py` の冒頭には既に `import pytest` と `_FakeEntry` クラスが
定義されている（`docs/superpowers/plans/2026-07-02-plate-cut-guide.md` Task 1で追加済み）ので、
そのまま再利用する。もし `pytest` の import が無ければファイル冒頭に追加すること。

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `python -m pytest tests/test_label_pdf_service.py -v -k "offset or safety_margin"`
Expected:
- `test_label_origin_applies_offset` は `TypeError: _label_origin() got an unexpected keyword argument 'offset_h_mm'` で FAIL
- `test_draw_label_applies_safety_margin_for_normal_mode` は `KeyError: 'x0'`
  （`captured` が空のまま）で FAIL

- [ ] **Step 3: `_label_origin` にオフセット引数を追加する**

`app/services/label_pdf_service.py` の `_label_origin` 関数（152〜165行目）を以下に置き換える:

```python
def _label_origin(col: int, row: int, layout: LabelLayout,
                   offset_h_mm: float = 0.0,
                   offset_v_mm: float = 0.0) -> tuple[float, float]:
    """ラベル左下隅の座標 (pt) を返す（row は上から 0 始まり）"""
    page_h = layout.page_h_mm * mm
    lw = layout.label_w_mm  * mm
    lh = layout.label_h_mm  * mm
    mt = (layout.margin_top_mm  + offset_v_mm) * mm
    ml = (layout.margin_left_mm + offset_h_mm) * mm
    gh = layout.gap_h_mm * mm
    gv = layout.gap_v_mm * mm
    offsets = layout.col_offsets_mm or []
    col_offset = offsets[col] * mm if col < len(offsets) else 0.0
    x = ml + col * (lw + gh) + col_offset
    y = page_h - mt - (row + 1) * lh - row * gv
    return x, y
```

- [ ] **Step 4: `generate_label_pdf` にオフセットパラメータを追加する**

同ファイルの `generate_label_pdf` 関数シグネチャ（191〜198行目）を以下に置き換える:

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
) -> str:
```

同関数内、`x0, y0 = _label_origin(col, row, layout)`（243行目付近）を以下に置き換える:

```python
        x0, y0 = _label_origin(col, row, layout, offset_h_mm, offset_v_mm)
```

- [ ] **Step 5: `_draw_label` にクリップパスと安全余白を追加する**

同ファイルの `_split_line` 関数の直後（296〜297行目の空行部分）に以下の定数を追加する:

```python

_SAFETY_H = 5.0 * mm   # 水平安全余白（左右各5mm）
_SAFETY_V = 2.0 * mm   # 垂直安全余白（上下各2mm）
```

続けて `_draw_label` 関数（298〜324行目）を以下に置き換える:

```python
def _draw_label(c, entry, x0: float, y0: float, w: float, h: float, mode: str,
                font: str = "MSPGothic", barcode_enabled: bool = False,
                plate_y_offset: float = 0.0):
    c.saveState()

    # ラベル枠の外にはみ出さないようクリップ
    clip = c.beginPath()
    clip.rect(x0, y0, w, h)
    c.clipPath(clip, stroke=0, fill=0)

    # 印刷ズレを考慮してセル内側に安全余白を設ける（卓上プレートは対象外）
    if mode == "split4":
        xs, ys, ws, hs = x0, y0, w, h
    else:
        xs = x0 + _SAFETY_H
        ys = y0 + _SAFETY_V
        ws = w  - 2 * _SAFETY_H
        hs = h  - 2 * _SAFETY_V

    company      = entry.company_name or ""
    postal       = entry.postal_code  or ""
    addr1        = entry.address1     or ""
    addr2        = entry.address2     or ""
    title        = entry.title        or ""
    person       = entry.person_name  or ""
    barcode_addr = getattr(entry, 'barcode_address', '') or ""

    if mode == "simple":
        _draw_simple(c, xs, ys, ws, hs, company, font)
    elif mode == "no_person":
        _draw_no_person(c, xs, ys, ws, hs, company, postal, addr1, addr2, font,
                        barcode_enabled, barcode_addr)
    elif mode == "nametag":
        _draw_nametag(c, xs, ys, ws, hs, company, title, person, font)
    elif mode == "split4":
        _draw_split4(c, xs, ys, ws, hs, company, font, plate_y_offset)
    else:
        _draw_normal(c, xs, ys, ws, hs, company, postal, addr1, addr2, title, person, font,
                     barcode_enabled, barcode_addr)

    c.restoreState()
```

- [ ] **Step 6: テストを実行して成功を確認する**

Run: `python -m pytest tests/test_label_pdf_service.py -v`
Expected: 全件 PASS（既存3件＋新規4件＝7件）

- [ ] **Step 7: 既存テストスイート全体を実行する**

Run: `python -m pytest -v`
Expected: 全件 PASS（回帰がないことを確認）

- [ ] **Step 8: コミット**

```bash
git add app/services/label_pdf_service.py tests/test_label_pdf_service.py
git commit -m "$(cat <<'EOF'
feat: ラベル印刷にクリップパス・安全余白・位置オフセットを追加

印刷ズレでラベル枠外にテキストがはみ出す問題を防ぐため、クリップパスと
安全余白（水平5mm・垂直2mm）を追加。また generate_label_pdf に
offset_h_mm/offset_v_mm を追加し、印刷位置を微調整できるようにする。
卓上プレート（split4）は対象外。
EOF
)"
```

---

### Task 3: 印刷位置補正ダイアログとファイルメニューの追加

**Files:**
- Create: `app/ui/print_offset_dialog.py`
- Modify: `app/ui/main_window.py`
- Test: `tests/test_print_offset_dialog.py`（新規）

**Interfaces:**
- Consumes: `app.utils.app_config.get_label_offset(layout_key) -> tuple[float, float]`,
  `app.utils.app_config.save_label_offset(layout_key, h_mm, v_mm) -> None`（Task 1で追加済み）、
  `app.services.label_pdf_service.LABEL_LAYOUTS: dict[str, LabelLayout]`（既存）、
  `app.ui.theme.BTN_PRIMARY: str`（既存）
- Produces: `PrintOffsetDialog(QDialog)` クラス（`app/ui/print_offset_dialog.py`）。
  インスタンス属性 `self._spins: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]]`
  （キーは `a4_4split` を除く `LABEL_LAYOUTS` のキー）と、メソッド `_save(self) -> None`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_print_offset_dialog.py` を新規作成する:

```python
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication, QMessageBox
_app = QApplication.instance() or QApplication(sys.argv)

from app.utils import app_config


def _use_tmp_config(monkeypatch, tmp_path):
    cfg_dir = str(tmp_path)
    monkeypatch.setattr(app_config, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", os.path.join(cfg_dir, "config.json"))


def test_dialog_excludes_split4_layout(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        assert "a4_4split" not in dlg._spins
        assert "a_one_28185" in dlg._spins
    finally:
        dlg.close()


def test_dialog_loads_existing_offset_into_spinboxes(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 3.0, -1.5)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        h_spin, v_spin = dlg._spins["a_one_28185"]
        assert h_spin.value() == 3.0
        assert v_spin.value() == -1.5
    finally:
        dlg.close()


def test_dialog_save_writes_all_layouts_to_app_config(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        h_spin, v_spin = dlg._spins["a_one_28187"]
        h_spin.setValue(4.5)
        v_spin.setValue(-2.0)
        dlg._save()
        h, v = app_config.get_label_offset("a_one_28187")
        assert h == 4.5
        assert v == -2.0
    finally:
        dlg.close()
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `python -m pytest tests/test_print_offset_dialog.py -v`
Expected: `ModuleNotFoundError: No module named 'app.ui.print_offset_dialog'` で全件 FAIL

- [ ] **Step 3: `app/ui/print_offset_dialog.py` を新規作成する**

```python
# -*- coding: utf-8 -*-
"""印刷位置補正ダイアログ（ファイルメニューから起動）"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QDoubleSpinBox, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from app.services.label_pdf_service import LABEL_LAYOUTS
from app.utils.app_config import get_label_offset, save_label_offset
from app.ui.theme import BTN_PRIMARY

_EXCLUDED_LAYOUT_KEYS = {"a4_4split"}

_DESC = (
    "印刷後にシールと印刷位置がずれる場合に補正します。\n"
    "内容が右にずれる → 横補正を負に　　内容が左にずれる → 横補正を正に\n"
    "内容が下にずれる → 縦補正を負に　　内容が上にずれる → 縦補正を正に"
)


def _make_spin(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(-15.0, 15.0)
    spin.setSingleStep(0.5)
    spin.setDecimals(1)
    spin.setValue(value)
    spin.setSuffix(" mm")
    spin.setFixedWidth(90)
    return spin


class PrintOffsetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("印刷位置補正")
        self.setFixedSize(480, 400)

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        desc = QLabel(_DESC)
        desc.setStyleSheet("color: #555; font-size: 11px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        self._spins: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}

        for key, layout in LABEL_LAYOUTS.items():
            if key in _EXCLUDED_LAYOUT_KEYS:
                continue
            h_mm, v_mm = get_label_offset(key)
            grp = QGroupBox(layout.name)
            lay = QVBoxLayout(grp)

            row = QHBoxLayout()
            row.addWidget(QLabel("横補正:"))
            h_spin = _make_spin(h_mm)
            row.addWidget(h_spin)
            row.addSpacing(20)
            row.addWidget(QLabel("縦補正:"))
            v_spin = _make_spin(v_mm)
            row.addWidget(v_spin)
            row.addStretch()
            lay.addLayout(row)

            root.addWidget(grp)
            self._spins[key] = (h_spin, v_spin)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)
        root.addStretch()

    def _save(self):
        for key, (h_spin, v_spin) in self._spins.items():
            save_label_offset(key, h_spin.value(), v_spin.value())
        QMessageBox.information(self, "保存完了", "印刷位置補正値を保存しました。")
        self.accept()
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `python -m pytest tests/test_print_offset_dialog.py -v`
Expected: 3件 PASS

- [ ] **Step 5: `main_window.py` にファイルメニューを追加する**

`app/ui/main_window.py` の `_setup_menu` メソッド（77〜89行目）を以下に置き換える:

```python
    def _setup_menu(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("ファイル")
        act_print_offset = QAction("印刷位置補正...", self)
        act_print_offset.triggered.connect(self._open_print_offset_dialog)
        file_menu.addAction(act_print_offset)

        help_menu = menubar.addMenu("ヘルプ")

        act_manual = QAction("マニュアルを開く", self)
        act_manual.triggered.connect(self._open_manual)
        help_menu.addAction(act_manual)

        help_menu.addSeparator()

        act_about = QAction("バージョン情報", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _open_print_offset_dialog(self):
        from app.ui.print_offset_dialog import PrintOffsetDialog
        dlg = PrintOffsetDialog(self)
        dlg.exec()
```

- [ ] **Step 6: インポート確認とテスト全体の実行**

Run: `python -c "import app.ui.main_window"`
Expected: エラーなく終了（構文・importエラーがないことの確認）

Run: `python -m pytest -v`
Expected: 全件 PASS（既存テスト＋Task 1〜3の新規テスト、回帰なし）

- [ ] **Step 7: コミット**

```bash
git add app/ui/print_offset_dialog.py app/ui/main_window.py tests/test_print_offset_dialog.py
git commit -m "$(cat <<'EOF'
feat: 印刷位置補正ダイアログをファイルメニューに追加

レイアウトごとの横・縦印刷位置補正をユーザーが設定できる
PrintOffsetDialog を新設し、ファイルメニューから開けるようにする。
卓上プレート（split4）は対象外。
EOF
)"
```

---

### Task 4: `direct_label_dialog.py` でオフセットを読み込みPDF生成に反映する

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

**Interfaces:**
- Consumes: `app.utils.app_config.get_label_offset(layout_key) -> tuple[float, float]`（Task 1）、
  `generate_label_pdf(..., offset_h_mm: float = 0.0, offset_v_mm: float = 0.0)`（Task 2）
- Produces: なし（最終呼び出し側、後続タスクなし）

- [ ] **Step 1: import に `get_label_offset` を追加する**

`app/ui/direct_label_dialog.py` の36〜39行目を以下に置き換える:

```python
from app.utils.app_config import (
    get_label_save_path,
    get_direct_label_save_path, set_direct_label_save_path,
    get_label_offset,
)
```

- [ ] **Step 2: プレビュー生成箇所（`_preview_pdf`）を修正する**

同ファイルの `_preview_pdf` メソッド内、以下の箇所（1062〜1064行目付近）:

```python
        mode       = self._current_mode()
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
```

を以下に置き換える:

```python
        mode       = self._current_mode()
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
```

続けて、同メソッド内の `generate_label_pdf` 呼び出し（1086〜1087行目付近）:

```python
            generate_label_pdf(entries, buf, mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked())
```

を以下に置き換える:

```python
            generate_label_pdf(entries, buf, mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v)
```

- [ ] **Step 3: PDF保存箇所を修正する**

同ファイル内、PDF保存メソッドの以下の箇所（1292〜1293行目付近）:

```python
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
```

を以下に置き換える:

```python
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
```

続けて、同メソッド内の `generate_label_pdf` 呼び出し（1295行目付近）:

```python
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked())
```

を以下に置き換える:

```python
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v)
```

- [ ] **Step 4: インポート確認とテスト全体の実行**

Run: `python -c "import app.ui.direct_label_dialog"`
Expected: エラーなく終了（構文・importエラーがないことの確認。このファイルはDB接続や
既存のQDialogサブクラスの複雑な初期化を伴うため、本プロジェクトの既存テストにも
専用の自動テストは存在しない。手動確認は本タスク完了後に
`docs/superpowers/plans/2026-07-03-print-position-correction.md` 実行者が
アプリを起動し、ファイルメニューで補正値を設定 → 宛名ラベル作成画面でPDFプレビュー/保存を行い、
印字位置が補正値どおりに移動することを目視確認する）

Run: `python -m pytest -v`
Expected: 全件 PASS（回帰がないことを確認）

- [ ] **Step 5: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "$(cat <<'EOF'
feat: PDF生成時に印刷位置補正値を読み込んで反映する

ラベル発行ダイアログのプレビュー・PDF保存の両方で、選択中レイアウトの
印刷位置補正値をapp_configから読み込みgenerate_label_pdfに渡す。
卓上プレート（split4）選択時は常に補正値0とする。
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** 設計書 2.1（クリップパス）・2.2（安全余白）・2.3（オフセット）は
  Task 2 で実装・テスト。2.4（`app_config.py` への永続化）は Task 1。2.5（ダイアログUI）は
  Task 3。2.6（呼び出し箇所への反映）は Task 4。設計書の「全影響範囲」節（split4除外・
  デフォルト0.0で現状維持）は各タスクのテストで明示的に確認している。
- **Placeholder scan:** TODO/TBD等のプレースホルダーなし。全ステップに実行可能な完全なコードを記載。
  Task 4 の手動確認手順のみ自動テストがないが、これは理由（DirectLabelDialogの複雑な初期化に
  対する既存テスト自体が本プロジェクトに存在しないこと）を明記した上での意図的な判断であり、
  プレースホルダーではない。
- **Type consistency:** `get_label_offset`/`save_label_offset` のシグネチャ（Task 1で定義）は
  Task 3・Task 4 の呼び出し側と一致。`generate_label_pdf` の `offset_h_mm`/`offset_v_mm`
  （Task 2で定義）は Task 4 の呼び出し側と一致。`_label_origin` の新規引数名・デフォルト値も
  一致していることを確認済み。
