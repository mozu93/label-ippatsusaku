# コード重複除去 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `_CheckableHeader`・`_MODE_LABEL`・ボタンスタイル・`_do_paste`/`_do_csv` の重複を除去し、`app/ui/widgets.py` を共有コンポーネント置き場として新設する。

**Architecture:** 新規 `widgets.py` に共有UIコンポーネントを集約。既存ファイルからは重複定義を削除して import に置換。ロジック変更なし。

**Tech Stack:** Python 3.11, PyQt6, pytest

---

## ファイル構成

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `app/ui/widgets.py` | 新規作成 | `CheckableHeader`・`MODE_LABEL` を定義 |
| `app/ui/theme.py` | 変更 | `BTN_OUTLINE`（白地・青枠アウトラインボタン）を追加 |
| `app/ui/label_list.py` | 変更 | `_CheckableHeader`・`_MODE_LABEL` を削除、import に置換 |
| `app/ui/direct_label_dialog.py` | 変更 | スタイル独自定義を削除、`_CheckableHeader` を削除、`_import_rows` メソッドを抽出 |
| `tests/test_widgets.py` | 新規作成 | `MODE_LABEL` の内容テスト |

---

## Task 1: `app/ui/widgets.py` を新規作成する

**Files:**
- Create: `app/ui/widgets.py`
- Create: `tests/test_widgets.py`

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_widgets.py` を新規作成:

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

```
pytest tests/test_widgets.py -v
```

期待結果: `ModuleNotFoundError: No module named 'app.ui.widgets'`

- [ ] **Step 3: `app/ui/widgets.py` を作成する**

```python
# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QHeaderView, QStyle, QStyleOptionButton
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtCore import QRect

MODE_LABEL: dict[str, str] = {
    "normal":    "宛名(氏名あり)",
    "no_person": "宛名(氏名なし)",
    "simple":    "事業所名のみ",
    "nametag":   "名札",
    "split4":    "卓上プレート",
}


class CheckableHeader(QHeaderView):
    """列0にチェックボックスを描画するカスタムヘッダー"""
    toggled = pyqtSignal(bool)
    sort_requested = pyqtSignal(int)

    def __init__(self, parent=None, initial_checked: bool = False):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = initial_checked
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool):
        self._checked = checked
        self.viewport().update()

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()
        if logical_index == 0:
            opt = QStyleOptionButton()
            cb = 14
            opt.rect = QRect(
                rect.x() + (rect.width() - cb) // 2,
                rect.y() + (rect.height() - cb) // 2,
                cb, cb,
            )
            opt.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            opt.state |= (QStyle.StateFlag.State_On if self._checked
                          else QStyle.StateFlag.State_Off)
            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter)

    def mousePressEvent(self, event):
        idx = self.logicalIndexAt(event.pos())
        if idx == 0:
            self._checked = not self._checked
            self.viewport().update()
            self.toggled.emit(self._checked)
        else:
            super().mousePressEvent(event)
            self.sort_requested.emit(idx)
```

- [ ] **Step 4: テストを実行してパスを確認する**

```
pytest tests/test_widgets.py -v
```

期待結果: `3 passed`

- [ ] **Step 5: コミットする**

```bash
git add app/ui/widgets.py tests/test_widgets.py
git commit -m "feat: 共有UIコンポーネントモジュールを新設 (widgets.py)"
```

---

## Task 2: `theme.py` に `BTN_OUTLINE` を追加する

**Files:**
- Modify: `app/ui/theme.py`

> **背景:** `direct_label_dialog.py` の `_BTN_SECONDARY` は白地・青枠のアウトラインボタン。
> `theme.py` の `BTN_SECONDARY` は濃いグレー地・白文字のフィルドボタンで別物。
> 新たに `BTN_OUTLINE` として追加する。

- [ ] **Step 1: `theme.py` の末尾に `BTN_OUTLINE` を追加する**

`app/ui/theme.py` の `BTN_GHOST` 定義（L83）の直後に追加:

```python
# アウトラインボタン（白地・青枠・青文字）
BTN_OUTLINE = (
    f"QPushButton {{ background: white; color: {C_PRIMARY}; "
    f"border: 1px solid {C_PRIMARY}; border-radius: 4px; "
    f"font-size: 13px; font-family: '{FONT_FAMILY}'; padding: 0 20px; }}"
    f"QPushButton:hover {{ background: {C_PRIMARY_LIGHT}; }}"
    f"QPushButton:disabled {{ color: #BDBDBD; border-color: #BDBDBD; }}"
)
```

- [ ] **Step 2: 既存テストが通ることを確認する**

```
pytest tests/ -v
```

期待結果: `27 passed`（既存24 + Task1の3）

- [ ] **Step 3: コミットする**

```bash
git add app/ui/theme.py
git commit -m "feat: BTN_OUTLINEスタイルをtheme.pyに追加"
```

---

## Task 3: `label_list.py` の重複を除去する

**Files:**
- Modify: `app/ui/label_list.py:1-72` （`_CheckableHeader` 削除、import 追加）
- Modify: `app/ui/label_list.py:219-268` （`_MODE_LABEL` ローカル定義を削除）

- [ ] **Step 1: import 行を更新する**

`label_list.py` の先頭 import ブロックを変更する。

変更前（L14-22）:
```python
from app.database.models import get_session, LabelBatch
from app.ui.pagination_bar import PaginationBar
from app.ui.theme import (
    BTN_PRIMARY, BTN_DANGER,
    TABLE_STYLE, PAGE_TITLE_STYLE, PAGE_MARGIN,
    C_TEXT_SUB, BTN_H, BTN_H_SM, ROW_H,
    font_page_title,
)
```

変更後:
```python
from app.database.models import get_session, LabelBatch
from app.ui.pagination_bar import PaginationBar
from app.ui.theme import (
    BTN_PRIMARY, BTN_DANGER,
    TABLE_STYLE, PAGE_TITLE_STYLE, PAGE_MARGIN,
    C_TEXT_SUB, BTN_H, BTN_H_SM, ROW_H,
    font_page_title,
)
from app.ui.widgets import CheckableHeader, MODE_LABEL
```

- [ ] **Step 2: `_CheckableHeader` クラス定義を削除する**

`label_list.py` の L33-72（`class _CheckableHeader` 全体）を削除する。

削除対象（L33-72）:
```python
class _CheckableHeader(QHeaderView):
    """列0にチェックボックスを描画するカスタムヘッダー"""
    toggled = pyqtSignal(bool)
    sort_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = False
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool):
        ...（以下全て削除）
```

- [ ] **Step 3: `_CheckableHeader` のインスタンス化を `CheckableHeader` に変更する**

`label_list.py` の `_init_ui` メソッド内（削除後の行番号が変わるため grep で確認）:

変更前:
```python
self._chk_header = _CheckableHeader(self.table)
```

変更後:
```python
self._chk_header = CheckableHeader(self.table)
```

- [ ] **Step 4: `_on_sort` の `_MODE_LABEL` ローカル定義を削除する**

`_on_sort` メソッド内のローカル変数定義を削除して `MODE_LABEL` を使う。

変更前（`_on_sort` 内）:
```python
_MODE_LABEL = {
    "normal":    "宛名(氏名あり)",
    "no_person": "宛名(氏名なし)",
    "simple":    "事業所名のみ",
    "nametag":   "名札",
    "split4":    "卓上プレート",
}
if col == COL_ID:
    ...
elif col == COL_MODE:
    key = lambda b: _MODE_LABEL.get(b.label_mode, b.label_mode or "")
```

変更後:
```python
if col == COL_ID:
    ...
elif col == COL_MODE:
    key = lambda b: MODE_LABEL.get(b.label_mode, b.label_mode or "")
```

- [ ] **Step 5: `_render` の `MODE_LABEL` ローカル定義を削除する**

`_render` メソッド内のローカル変数定義を削除して `MODE_LABEL` を使う。

変更前（`_render` 内）:
```python
def _render(self, counts: dict, batches: list | None = None):
    self.table.setRowCount(0)
    MODE_LABEL = {
        "normal":    "宛名(氏名あり)",
        "no_person": "宛名(氏名なし)",
        "simple":    "事業所名のみ",
        "nametag":   "名札",
        "split4":    "卓上プレート",
    }
    display_batches = batches if batches is not None else self._batches
```

変更後:
```python
def _render(self, counts: dict, batches: list | None = None):
    self.table.setRowCount(0)
    display_batches = batches if batches is not None else self._batches
```

- [ ] **Step 6: 不要になった import を確認・削除する**

`label_list.py` の先頭 import から `pyqtSignal` が `_CheckableHeader` でしか使われていなかった場合は削除する。

現在の import（L12）:
```python
from PyQt6.QtCore import Qt, pyqtSignal, QRect
```

`LabelListWidget` 内で `pyqtSignal` を使っていないので削除:
```python
from PyQt6.QtCore import Qt, QRect
```

- [ ] **Step 7: テストを実行して確認する**

```
pytest tests/ -v
```

期待結果: `27 passed`

- [ ] **Step 8: コミットする**

```bash
git add app/ui/label_list.py
git commit -m "refactor: label_list.pyの_CheckableHeaderと_MODE_LABELをwidgets.pyから共有"
```

---

## Task 4: `direct_label_dialog.py` の重複を除去する

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

### 4-A: スタイル定義を theme.py からの import に置き換える

- [ ] **Step 1: import ブロックを更新する**

`direct_label_dialog.py` の先頭 import ブロックに theme と widgets の import を追加する。

追加（既存の `from app.utils.app_config import ...` の前に挿入）:

```python
from app.ui.theme import BTN_PRIMARY, BTN_DANGER, BTN_OUTLINE
from app.ui.widgets import CheckableHeader
```

- [ ] **Step 2: ローカルスタイル定義 3 つを削除する**

`direct_label_dialog.py` の L37-53 を丸ごと削除する:

```python
_BTN_PRIMARY = (
    "QPushButton { background: #1565C0; color: white; border-radius: 4px; "
    "padding: 0 20px; font-size: 13px; min-height: 34px; }"
    "QPushButton:hover { background: #1976D2; }"
    "QPushButton:disabled { background: #BDBDBD; }"
)
_BTN_SECONDARY = (
    "QPushButton { background: white; color: #1565C0; border: 1px solid #1565C0; "
    "border-radius: 4px; padding: 0 20px; font-size: 13px; min-height: 34px; }"
    "QPushButton:hover { background: #E3F2FD; }"
    "QPushButton:disabled { color: #BDBDBD; border-color: #BDBDBD; }"
)
_BTN_DANGER = (
    "QPushButton { background: #D32F2F; color: white; border-radius: 4px; "
    "padding: 0 16px; font-size: 12px; min-height: 28px; }"
    "QPushButton:hover { background: #B71C1C; }"
)
```

- [ ] **Step 3: ファイル内の `_BTN_*` 参照を置換する**

ファイル内の参照を一括置換する（合計3箇所）:

| 変更前 | 変更後 |
|---|---|
| `_BTN_PRIMARY` | `BTN_PRIMARY` |
| `_BTN_SECONDARY` | `BTN_OUTLINE` |
| `_BTN_DANGER` | `BTN_DANGER` |

### 4-B: `_CheckableHeader` クラス定義を削除する

- [ ] **Step 4: `_CheckableHeader` クラス定義を削除する**

`direct_label_dialog.py` の `class _CheckableHeader` 全体（L56-95、削除後は行番号が変わる）を削除する。

削除対象（クラス全体）:
```python
class _CheckableHeader(QHeaderView):
    """列0にチェックボックスを描画するカスタムヘッダー"""
    toggled = pyqtSignal(bool)
    sort_requested = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = True
        ...（クラス末尾まで全て削除）
```

- [ ] **Step 5: `_CheckableHeader` のインスタンス化を `CheckableHeader` に変更する**

`_init_ui` メソッド内（grep で確認）:

変更前:
```python
self._chk_header = _CheckableHeader(self.table)
```

変更後（`initial_checked=True` を渡す）:
```python
self._chk_header = CheckableHeader(self.table, initial_checked=True)
```

- [ ] **Step 6: 不要になった import を削除する**

`_CheckableHeader` で使っていた `QHeaderView`, `QStyle`, `QStyleOptionButton`, `QRect`, `pyqtSignal` が他で使われていないか確認し、不要なものを削除する。

確認コマンド:
```
grep -n "QHeaderView\|QStyle\|QStyleOptionButton\|QRect\|pyqtSignal" app/ui/direct_label_dialog.py
```

`QHeaderView` は `DirectLabelDialog._init_ui` 内の `setSectionResizeMode` で引き続き使用する。
`QRect` と `QStyleOptionButton` と `QStyle` は `CheckableHeader` 削除後は不要になるので削除する。
`pyqtSignal` も `CheckableHeader` 削除後は不要になるので削除する。

`QEvent` と `QRect` の import:
```python
from PyQt6.QtCore import Qt, QEvent, QRect, pyqtSignal
```
↓
```python
from PyQt6.QtCore import Qt, QEvent
```

`QStyle, QStyleOptionButton` の import:
```python
from PyQt6.QtWidgets import (
    ...
    QStyle, QStyleOptionButton,
    ...
)
```
から `QStyle, QStyleOptionButton` を削除する。

### 4-C: `_do_paste` / `_do_csv` を共通メソッドに抽出する

- [ ] **Step 7: `_import_rows` メソッドを追加する**

`_do_paste` の直前に新メソッドを挿入する:

```python
def _import_rows(self, headers: list, data_rows: list) -> None:
    """ColumnMappingDialog を表示して行データを取り込む共通処理"""
    if not headers:
        QMessageBox.information(self, "取込結果", "取込可能なデータがありませんでした。")
        return

    dlg = ColumnMappingDialog(headers, data_rows[:5], self._current_mode(), self)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    mapping = dlg.get_mapping()
    rows = []
    for row in data_rows:
        def _get(field_id, _row=row):
            idx = mapping.get(field_id)
            return _row[idx] if idx is not None and idx < len(_row) else ""
        dr = DirectRow(
            company_name=_get("company_name"),
            company_kana=_get("company_kana"),
            postal_code =_get("postal_code"),
            address1    =_get("address1"),
            title       =_get("title"),
            person_name =_get("person_name"),
        )
        if dr.company_name:
            rows.append(dr)
    self._fill_rows(rows)
```

- [ ] **Step 8: `_do_paste` を簡略化する**

変更前（`_do_paste` 全体）:
```python
def _do_paste(self):
    from PyQt6.QtWidgets import QApplication
    text = QApplication.clipboard().text()
    if not text.strip():
        QMessageBox.information(self, "貼り付け", "クリップボードにテキストがありません。")
        return
    try:
        headers, data_rows = parse_raw_clipboard(text)
    except Exception as e:
        QMessageBox.critical(self, "エラー", f"貼り付けデータの解析に失敗しました：\n{e}")
        return
    if not headers:
        QMessageBox.information(self, "貼り付け", "取込可能なデータがありませんでした。")
        return

    dlg = ColumnMappingDialog(headers, data_rows[:5], self._current_mode(), self)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    mapping = dlg.get_mapping()
    rows = []
    for row in data_rows:
        def _get(field_id, _row=row):
            idx = mapping.get(field_id)
            return _row[idx] if idx is not None and idx < len(_row) else ""
        dr = DirectRow(
            company_name=_get("company_name"),
            company_kana=_get("company_kana"),
            postal_code =_get("postal_code"),
            address1    =_get("address1"),
            title       =_get("title"),
            person_name =_get("person_name"),
        )
        if dr.company_name:
            rows.append(dr)
    self._fill_rows(rows)
```

変更後:
```python
def _do_paste(self):
    from PyQt6.QtWidgets import QApplication
    text = QApplication.clipboard().text()
    if not text.strip():
        QMessageBox.information(self, "貼り付け", "クリップボードにテキストがありません。")
        return
    try:
        headers, data_rows = parse_raw_clipboard(text)
    except Exception as e:
        QMessageBox.critical(self, "エラー", f"貼り付けデータの解析に失敗しました：\n{e}")
        return
    self._import_rows(headers, data_rows)
```

- [ ] **Step 9: `_do_csv` を簡略化する**

変更前（`_do_csv` 全体）:
```python
def _do_csv(self):
    path, _ = QFileDialog.getOpenFileName(
        self, "CSV ファイルを選択", "", "CSV ファイル (*.csv);;すべてのファイル (*)"
    )
    if not path:
        return
    try:
        with open(path, "rb") as f:
            headers, data_rows = parse_raw_csv_bytes(f.read())
    except Exception as e:
        QMessageBox.critical(self, "エラー", f"CSV 読み込みエラー：\n{e}")
        return
    if not headers:
        QMessageBox.information(self, "CSV 取込", "取込可能なデータがありませんでした。")
        return

    dlg = ColumnMappingDialog(headers, data_rows[:5], self._current_mode(), self)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return

    mapping = dlg.get_mapping()
    rows = []
    for row in data_rows:
        def _get(field_id, _row=row):
            idx = mapping.get(field_id)
            return _row[idx] if idx is not None and idx < len(_row) else ""
        dr = DirectRow(
            company_name=_get("company_name"),
            company_kana=_get("company_kana"),
            postal_code =_get("postal_code"),
            address1    =_get("address1"),
            title       =_get("title"),
            person_name =_get("person_name"),
        )
        if dr.company_name:
            rows.append(dr)
    self._fill_rows(rows)
```

変更後:
```python
def _do_csv(self):
    path, _ = QFileDialog.getOpenFileName(
        self, "CSV ファイルを選択", "", "CSV ファイル (*.csv);;すべてのファイル (*)"
    )
    if not path:
        return
    try:
        with open(path, "rb") as f:
            headers, data_rows = parse_raw_csv_bytes(f.read())
    except Exception as e:
        QMessageBox.critical(self, "エラー", f"CSV 読み込みエラー：\n{e}")
        return
    self._import_rows(headers, data_rows)
```

- [ ] **Step 10: テストを実行して確認する**

```
pytest tests/ -v
```

期待結果: `27 passed`

- [ ] **Step 11: コミットする**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "refactor: direct_label_dialogのスタイル重複・_CheckableHeader重複・_do_paste/_do_csv重複を除去"
```

---

## Task 5: 最終検証

- [ ] **Step 1: 重複が残っていないことを grep で確認する**

```bash
# _CheckableHeader の重複確認（widgets.py のみに存在すればOK）
grep -rn "class.*CheckableHeader" app/

# _MODE_LABEL / MODE_LABEL のローカル定義確認（label_list.py・direct_label_dialog.py に残っていないこと）
grep -n "MODE_LABEL\s*=" app/ui/label_list.py app/ui/direct_label_dialog.py

# _BTN_* の残存確認（0件であること）
grep -n "_BTN_" app/ui/direct_label_dialog.py
```

期待結果:
- `_CheckableHeader`: `app/ui/widgets.py` の1箇所のみ
- `MODE_LABEL =`: 0件
- `_BTN_`: 0件

- [ ] **Step 2: 全テストを実行する**

```
pytest tests/ -v
```

期待結果: `27 passed`

- [ ] **Step 3: アプリを起動して動作確認する**

```
python main.py
```

確認項目:
- [ ] 一覧画面が表示される
- [ ] 「＋ 新規作成」ボタンをクリックしてダイアログが開く
- [ ] 「貼り付けから取込」ボタンが機能する（クリップボードに何か入れてテスト）
- [ ] 「CSV から取込」ボタンが機能する
- [ ] モード切り替えラジオボタンが機能する
- [ ] チェックボックスヘッダーのトグルが機能する（一覧画面・ダイアログ両方）
- [ ] ヘッダークリックでソートが機能する

- [ ] **Step 4: 最終コミット**

```bash
git add .
git commit -m "refactor: コード重複除去完了 - widgets.py新設・BTN_OUTLINE追加・_import_rows抽出"
```
