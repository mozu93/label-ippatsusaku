# 郵便番号自動補完 バックグラウンド化・進捗表示・キャッシュ Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 郵便番号自動補完（〒 自動補完）をバックグラウンドスレッドで実行し、進捗表示とキャンセルを可能にする。また同一住所への再問い合わせを省略するメモリキャッシュを追加する。

**Architecture:** `app/utils/postal_lookup.py` の `lookup_postal_code()` にモジュールレベルのメモリキャッシュを追加する（呼び出し側からは透過的）。`app/ui/direct_label_dialog.py` に既存の `_VersionCheckThread`/`_DownloadThread`（`app/ui/update_banner.py`）と同じ `QThread` サブクラス方式でワーカースレッドを追加し、`QProgressDialog`（進捗表示＋キャンセルボタン標準搭載）と組み合わせる。

**Tech Stack:** Python, PyQt6（`QThread`, `pyqtSignal`, `QProgressDialog`）, pytest

## Global Constraints

- キャッシュはプロセス生存中のみ有効（永続化しない）。キーは `address.strip()` の完全一致（表記ゆれ吸収は対象外）。
- バックグラウンド処理は1件ずつ順番に行う（並列化しない）。
- キャンセルは「現在通信中の1件」が終わった直後に反映する（通信の強制中断はしない）。キャンセルしても、それまでに補完済みの結果はテーブルに残す。
- フリガナ補完（`_fill_kana`）は対象外。変更しない。
- 対象設計書: `docs/superpowers/specs/2026-07-07-postal-lookup-background-design.md`

---

### Task 1: `lookup_postal_code` にメモリキャッシュを追加する

**Files:**
- Modify: `app/utils/postal_lookup.py`
- Test: `tests/test_postal_lookup.py`（新規作成）

**Interfaces:**
- Produces: `lookup_postal_code(address: str) -> str | None`（シグネチャ・戻り値は変更なし。内部でキャッシュを透過的に使う）。`_postal_cache: dict[str, str | None]`（モジュールレベル、テストからクリアできるよう公開）。

- [ ] **Step 1: 失敗するテストを書く**

新規ファイル `tests/test_postal_lookup.py` を作成する:

```python
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import app.utils.postal_lookup as pl


@pytest.fixture(autouse=True)
def _clear_cache():
    pl._postal_cache.clear()
    yield
    pl._postal_cache.clear()


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_lookup_postal_code_caches_same_address(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"1000001")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    r1 = pl.lookup_postal_code("東京都千代田区")
    r2 = pl.lookup_postal_code("東京都千代田区")

    assert r1 == "100-0001"
    assert r2 == "100-0001"
    assert len(calls) == 1


def test_lookup_postal_code_different_addresses_each_call_api(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"1000001")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    pl.lookup_postal_code("東京都千代田区")
    pl.lookup_postal_code("大阪府大阪市")

    assert len(calls) == 2


def test_lookup_postal_code_not_found_result_is_cached(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    r1 = pl.lookup_postal_code("存在しない住所")
    r2 = pl.lookup_postal_code("存在しない住所")

    assert r1 is None
    assert r2 is None
    assert len(calls) == 1
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_postal_lookup.py -v`
Expected: `AttributeError: module 'app.utils.postal_lookup' has no attribute '_postal_cache'` で全件 FAIL

- [ ] **Step 3: `postal_lookup.py` にキャッシュを実装する**

`app/utils/postal_lookup.py` の以下のブロックを:

```python
_API_URL = "https://api.excelapi.org/post/zipcode"
_HEARTRAILS_URL = "http://geoapi.heartrails.com/api/json"
_TIMEOUT = 5  # seconds


def lookup_postal_code(address: str) -> str | None:
    """
    住所文字列から郵便番号（XXX-XXXX 形式）を返す。
    見つからない・通信失敗の場合は None。
    """
    addr = address.strip()
    if not addr:
        return None
    params = urllib.parse.urlencode({"address": addr})
    try:
        with urllib.request.urlopen(f"{_API_URL}?{params}", timeout=_TIMEOUT) as resp:
            code = resp.read().decode("utf-8").strip()
        if not code:
            return None
        # 7桁 → XXX-XXXX に整形
        digits = code.replace("-", "")
        if len(digits) == 7 and digits.isdigit():
            return f"{digits[:3]}-{digits[3:]}"
        return code if code else None
    except Exception:
        return None
```

以下に置き換える:

```python
_API_URL = "https://api.excelapi.org/post/zipcode"
_HEARTRAILS_URL = "http://geoapi.heartrails.com/api/json"
_TIMEOUT = 5  # seconds

# 住所 → 郵便番号（またはNone=未特定）のメモリキャッシュ。
# プロセス生存中のみ有効（永続化しない）。キーは strip() 済み文字列の完全一致。
_postal_cache: dict[str, str | None] = {}


def lookup_postal_code(address: str) -> str | None:
    """
    住所文字列から郵便番号（XXX-XXXX 形式）を返す。
    見つからない・通信失敗の場合は None。
    同一住所への再問い合わせはキャッシュから返す（未特定=Noneもキャッシュする）。
    """
    addr = address.strip()
    if not addr:
        return None
    if addr in _postal_cache:
        return _postal_cache[addr]
    result = _lookup_postal_code_uncached(addr)
    _postal_cache[addr] = result
    return result


def _lookup_postal_code_uncached(addr: str) -> str | None:
    params = urllib.parse.urlencode({"address": addr})
    try:
        with urllib.request.urlopen(f"{_API_URL}?{params}", timeout=_TIMEOUT) as resp:
            code = resp.read().decode("utf-8").strip()
        if not code:
            return None
        # 7桁 → XXX-XXXX に整形
        digits = code.replace("-", "")
        if len(digits) == 7 and digits.isdigit():
            return f"{digits[:3]}-{digits[3:]}"
        return code if code else None
    except Exception:
        return None
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_postal_lookup.py -v`
Expected: 3件 PASS

- [ ] **Step 5: 既存テストが壊れていないことを確認する**

Run: `pytest tests/ -v`
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add app/utils/postal_lookup.py tests/test_postal_lookup.py
git commit -m "feat: lookup_postal_codeにメモリキャッシュを追加"
```

---

### Task 2: 郵便番号自動補完をバックグラウンドスレッド化する

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

**Interfaces:**
- Consumes: `lookup_postal_code(address: str) -> str | None`（Task 1）
- Produces: `_PostalLookupThread`（`QThread` サブクラス。`progress = pyqtSignal(int, object)`、`finished_all = pyqtSignal(int, int, int)`、`request_cancel()` メソッド）

このタスクはPyQt UIの変更であり、既存の自動テスト対象外（`direct_label_dialog.py` にはテストファイルがない）。検証は構文チェックと、`QT_QPA_PLATFORM=offscreen` を使ったheadlessでのスレッド動作確認で行う。

- [ ] **Step 1: import文を追加する**

`app/ui/direct_label_dialog.py:8-18` の以下のブロックを:

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
from PyQt6.QtCore import Qt, QEvent, QPoint
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut, QAction
```

以下に置き換える:

```python
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QButtonGroup,
    QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
    QComboBox, QLineEdit, QSpinBox,
    QApplication, QProgressDialog,
    QCheckBox, QWidget, QFrame, QMenu,
)
from PyQt6.QtCore import Qt, QEvent, QPoint, QThread, pyqtSignal
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut, QAction
```

- [ ] **Step 2: `_PostalLookupThread` クラスを追加する**

`app/ui/direct_label_dialog.py:40-44` の以下のブロックを:

```python
from app.utils.app_config import (
    get_label_save_path,
    get_direct_label_save_path, set_direct_label_save_path,
    get_label_offset,
)



class DirectLabelDialog(QDialog):
```

以下に置き換える:

```python
from app.utils.app_config import (
    get_label_save_path,
    get_direct_label_save_path, set_direct_label_save_path,
    get_label_offset,
)


class _PostalLookupThread(QThread):
    """郵便番号自動補完をバックグラウンドで1件ずつ順番に実行するワーカー"""
    progress     = pyqtSignal(int, object)   # (row, zipcode_or_None)
    finished_all = pyqtSignal(int, int, int)  # (filled, skipped, cancelled_remaining)

    def __init__(self, targets: list, parent=None):
        super().__init__(parent)
        self._targets = targets   # [(row, address), ...]
        self._cancel_requested = False

    def request_cancel(self):
        self._cancel_requested = True

    def run(self):
        from app.utils.postal_lookup import lookup_postal_code
        filled = skipped = 0
        for i, (row, address) in enumerate(self._targets):
            if self._cancel_requested:
                remaining = len(self._targets) - i
                self.finished_all.emit(filled, skipped, remaining)
                return
            zipcode = lookup_postal_code(address)
            if zipcode:
                filled += 1
            else:
                skipped += 1
            self.progress.emit(row, zipcode)
        self.finished_all.emit(filled, skipped, 0)


class DirectLabelDialog(QDialog):
```

- [ ] **Step 3: 「〒 自動補完」ボタンを `self._btn_postal` に昇格する**

`app/ui/direct_label_dialog.py:283-288` の以下のブロックを:

```python
        btn_postal = _tb("〒 自動補完")
        btn_postal.setToolTip(
            "住所が入力されていて郵便番号が空の行に、\n"
            "zipcloud API（インターネット接続必要）で郵便番号を補完します。"
        )
        btn_postal.clicked.connect(self._fill_postal_codes)
```

以下に置き換える:

```python
        self._btn_postal = _tb("〒 自動補完")
        self._btn_postal.setToolTip(
            "住所が入力されていて郵便番号が空の行に、\n"
            "zipcloud API（インターネット接続必要）で郵便番号を補完します。"
        )
        self._btn_postal.clicked.connect(self._fill_postal_codes)
```

`app/ui/direct_label_dialog.py:308-316` の以下のブロックを:

```python
        for widget in [
            btn_paste, btn_csv,
            None,       # sep
            btn_add, btn_del, btn_clear,
            None,       # sep
            btn_postal, btn_kana,
            None,       # sep
            self._btn_undo,
        ]:
```

以下に置き換える:

```python
        for widget in [
            btn_paste, btn_csv,
            None,       # sep
            btn_add, btn_del, btn_clear,
            None,       # sep
            self._btn_postal, btn_kana,
            None,       # sep
            self._btn_undo,
        ]:
```

- [ ] **Step 4: `_fill_postal_codes` を書き換える**

`app/ui/direct_label_dialog.py:697-730` の以下のブロックを:

```python
    def _fill_postal_codes(self):
        from app.utils.postal_lookup import lookup_postal_code
        from PyQt6.QtWidgets import QApplication

        targets = [
            row for row in range(self.table.rowCount())
            if not (self.table.item(row, self.COL_POSTAL) or QTableWidgetItem()).text().strip()
            and (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip()
        ]
        if not targets:
            QMessageBox.information(self, "郵便番号補完",
                                    "補完対象の行がありません。\n"
                                    "（郵便番号が空で住所が入力されている行が対象です）")
            return

        self._btn_export.setEnabled(False)
        filled = skipped = 0
        for row in targets:
            address = (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip()
            QApplication.processEvents()
            zipcode = lookup_postal_code(address)
            if zipcode:
                item = self.table.item(row, self.COL_POSTAL)
                if item:
                    item.setText(zipcode)
                filled += 1
            else:
                skipped += 1

        self._btn_export.setEnabled(True)
        msg = f"{filled} 件の郵便番号を補完しました。"
        if skipped:
            msg += f"\n（{skipped} 件は住所から特定できませんでした）"
        QMessageBox.information(self, "郵便番号補完", msg)
```

以下に置き換える:

```python
    def _fill_postal_codes(self):
        targets = [
            (row, (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip())
            for row in range(self.table.rowCount())
            if not (self.table.item(row, self.COL_POSTAL) or QTableWidgetItem()).text().strip()
            and (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip()
        ]
        if not targets:
            QMessageBox.information(self, "郵便番号補完",
                                    "補完対象の行がありません。\n"
                                    "（郵便番号が空で住所1が入力されている行が対象です）")
            return

        self._btn_postal.setEnabled(False)
        self._btn_export.setEnabled(False)

        progress_dlg = QProgressDialog("郵便番号を検索中...", "キャンセル", 0, len(targets), self)
        progress_dlg.setWindowModality(Qt.WindowModality.WindowModal)
        progress_dlg.setMinimumDuration(0)
        progress_dlg.setValue(0)

        self._postal_thread = _PostalLookupThread(targets, self)

        def _on_progress(row, zipcode):
            count = progress_dlg.value() + 1
            progress_dlg.setLabelText(f"郵便番号を検索中... ({count}/{len(targets)}件)")
            progress_dlg.setValue(count)
            if zipcode:
                item = self.table.item(row, self.COL_POSTAL)
                if item:
                    item.setText(zipcode)

        def _on_finished(filled, skipped, cancelled_remaining):
            progress_dlg.close()
            self._btn_postal.setEnabled(True)
            self._btn_export.setEnabled(True)
            if cancelled_remaining > 0:
                msg = (f"キャンセルしました。{filled} 件の郵便番号を補完しました。\n"
                       f"（{skipped} 件は住所から特定できませんでした、"
                       f"{cancelled_remaining} 件は未処理です）")
            else:
                msg = f"{filled} 件の郵便番号を補完しました。"
                if skipped:
                    msg += f"\n（{skipped} 件は住所から特定できませんでした）"
            QMessageBox.information(self, "郵便番号補完", msg)

        self._postal_thread.progress.connect(_on_progress)
        self._postal_thread.finished_all.connect(_on_finished)
        progress_dlg.canceled.connect(self._postal_thread.request_cancel)
        self._postal_thread.start()
```

- [ ] **Step 5: 構文エラーがないことを確認する**

Run: `python -c "import ast; ast.parse(open('app/ui/direct_label_dialog.py', encoding='utf-8').read())"`
Expected: エラーなく終了（出力なし）

- [ ] **Step 6: headlessでスレッドの動作を確認する**

`QT_QPA_PLATFORM=offscreen` で実際にダイアログをインスタンス化し、`_PostalLookupThread` を直接動かして `progress`/`finished_all` シグナルとテーブル反映を確認する（外部APIへの実通信は避け、`app.utils.postal_lookup.lookup_postal_code` をモンキーパッチして完結させる）:

```bash
QT_QPA_PLATFORM=offscreen PYTHONIOENCODING=utf-8 python -c "
import sys, time
sys.stdout.reconfigure(encoding='utf-8')
from PyQt6.QtWidgets import QApplication
app = QApplication(sys.argv)

import app.utils.postal_lookup as pl
def fake_lookup(address):
    return None if address == 'unknown' else '100-0001'
pl.lookup_postal_code = fake_lookup

from app.ui.direct_label_dialog import DirectLabelDialog
dlg = DirectLabelDialog()
dlg._add_row(['株式会社テスト', '', '', '', '山田太郎', '', '東京都千代田区1-1', ''])
dlg._add_row(['株式会社テスト2', '', '', '', '鈴木花子', '', 'unknown', ''])

progress_events = []
finished_events = []
dlg._fill_postal_codes()
dlg._postal_thread.progress.connect(lambda row, zc: progress_events.append((row, zc)))
dlg._postal_thread.finished_all.connect(lambda f, s, c: finished_events.append((f, s, c)))
dlg._postal_thread.wait(5000)
app.processEvents()

print('progress events (order may vary by timing, check count):', len(progress_events))
print('finished events:', finished_events)
print('row0 postal cell:', (dlg.table.item(0, dlg.COL_POSTAL) or None) and dlg.table.item(0, dlg.COL_POSTAL).text())
print('row1 postal cell (expect empty, since not found):', (dlg.table.item(1, dlg.COL_POSTAL) or None) and dlg.table.item(1, dlg.COL_POSTAL).text())
print('btn_postal enabled after finish:', dlg._btn_postal.isEnabled())
"
```

Expected出力（最も重要なのは最終状態の3行。`progress events`/`finished events` の件数はスクリプト側の外部シグナル接続タイミングに依存するため参考情報）:
```
row0 postal cell: 100-0001
row1 postal cell (expect empty, since not found): None
btn_postal enabled after finish: True
```

> 補足: このスクリプトは `_fill_postal_codes()` 呼び出し**後**に外部の `progress`/`finished_all` リスナーを接続しているため、スレッドが速く完了した場合はそれらのイベントを取りこぼすことがある（`progress_events`/`finished_events` の件数が0になり得る）。これはダイアログ内部の実装（Step 4のコードでは接続を `start()` の前に済ませている）とは無関係な、検証スクリプト特有の注意点。判定は必ず `dlg.table` の内容と `dlg._btn_postal.isEnabled()` の最終状態（上記3行）で行うこと。

- [ ] **Step 7: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: 郵便番号自動補完をバックグラウンドスレッド化し進捗表示・キャンセルに対応"
```

---

### Task 3: 全体の回帰確認

**Files:** なし（確認のみ）

- [ ] **Step 1: 全自動テストを実行する**

Run: `pytest tests/ -v`
Expected: 全テスト PASS

- [ ] **Step 2: 手動でエンドツーエンド確認する（可能な場合）**

`python main.py` でアプリを起動し、「新規作成（直接入力）」で住所を複数行入力後、「〒 自動補完」を押して進捗ダイアログが表示されること、キャンセルボタンを押すとその時点までの結果が残ったまま処理が止まることを目視確認する。

GUI操作ができない環境の場合は、Task 2 Step 6 のheadless検証で代替する（すでに実施済みのため、このステップでは再実行のみでよい）。
