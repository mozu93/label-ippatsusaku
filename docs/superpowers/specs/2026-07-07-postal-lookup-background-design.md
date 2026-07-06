# 郵便番号自動補完の改善（バックグラウンド化・進捗表示・キャンセル・キャッシュ） 設計書

**作成日:** 2026-07-07
**対象バージョン:** 次期リリース（予定）

---

## 1. 概要

現在の「〒 自動補完」機能（`app/ui/direct_label_dialog.py:_fill_postal_codes`）は、UIスレッド上で対象行を1件ずつ同期的に `lookup_postal_code()`（外部API・タイムアウト5秒）へ問い合わせている。行数が多いと画面がほぼ固まったように見え、途中でのキャンセルもできない。

本機能では、この処理をバックグラウンドスレッドに移し、進捗表示とキャンセルを可能にする。また、同一住所への再問い合わせを省略するメモリキャッシュを追加する。フリガナ補完（ローカルライブラリ処理で高速なため）は対象外とする。

---

## 2. 仕様詳細

### 2.1 キャッシュ（`app/utils/postal_lookup.py`）

`lookup_postal_code()` の呼び出し結果をモジュールレベルの辞書でキャッシュする。

```python
_postal_cache: dict[str, str | None] = {}

def lookup_postal_code(address: str) -> str | None:
    addr = address.strip()
    if not addr:
        return None
    if addr in _postal_cache:
        return _postal_cache[addr]
    result = _lookup_postal_code_uncached(addr)
    _postal_cache[addr] = result
    return result
```

- キーは `address.strip()` した文字列そのもの（既存の正規化ロジックはないため、単純な完全一致でよい。表記ゆれの吸収は対象外＝YAGNI）
- 見つからなかった場合（`None`）もキャッシュする。同一住所を含む行が複数あるとき、毎回失敗リクエストを送らずに済む
- キャッシュはプロセスが生きている間（アプリを閉じるまで）保持される。永続化はしない
- 既存の `lookup_postal_code` のシグネチャ・戻り値・例外処理（通信失敗時 `None` を返す）は変更しない。呼び出し側からは透過的

### 2.2 バックグラウンド実行用ワーカー（`app/ui/direct_label_dialog.py`）

`app/ui/update_banner.py` の `_VersionCheckThread`/`_DownloadThread` と同じ `QThread` サブクラス方式を踏襲する。

```python
class _PostalLookupThread(QThread):
    progress = pyqtSignal(int, object)   # (row, zipcode_or_None)
    finished_all = pyqtSignal(int, int, int)  # (filled, skipped, cancelled_remaining)

    def __init__(self, targets: list[tuple[int, str]], parent=None):
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
```

- `finished` は `QThread` 組み込みシグナルと名前が衝突するため `finished_all` とする
- 1件ずつ順番に処理する（並列化しない）。ループの先頭でキャンセルフラグを確認し、要求があれば即座に打ち切る（**現在通信中の1件を強制中断はしない** — チェックはリクエストの合間にのみ行う）
- `progress` シグナルはメインスレッド側のスロットで受け、テーブルの該当行に即座に反映する（キャンセルしても、それまでの結果は残る）

### 2.3 `_fill_postal_codes` の書き換え

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

- `self._btn_postal`（現行コードでは `btn_postal` というローカル変数、`self` 属性ではない）は、ハンドラから無効化できるよう `self._btn_postal` としてインスタンス属性に昇格させる（`_build_toolbar()` 側の変更）
- `QProgressDialog` の「キャンセル」ボタンは組み込みの `canceled` シグナルを持つため、追加のボタン実装は不要
- 完了メッセージのロジックは設計どおり、キャンセル時とそうでない時で分岐する

### 2.4 スコープ外

- フリガナ補完（`_fill_kana`）は対象外。ローカルライブラリ（pykakasi）による変換で、通信を伴わず高速なため、体感上の課題がない
- キャッシュの永続化（アプリ再起動をまたいだ保持）
- 複数件の並列問い合わせ（1件ずつの順次処理を維持）
- 住所の表記ゆれ吸収（キャッシュキーの正規化）

---

## 3. 実装方針

**対象ファイル:**
- 修正: `app/utils/postal_lookup.py`（`lookup_postal_code` にメモリキャッシュを追加）
- 修正: `app/ui/direct_label_dialog.py`（`_PostalLookupThread` の追加、`_fill_postal_codes` の書き換え、`_btn_postal` のインスタンス属性化、`QThread`/`QProgressDialog`/`Qt` のimport追加）

---

## 4. テスト

`tests/test_postal_lookup.py`（新規作成）:
- 同一住所で `lookup_postal_code` を2回呼んだとき、実際のHTTP問い合わせ（`urllib.request.urlopen`）が1回しか発生しないことを、`urlopen` をモックして確認するテスト
- 異なる住所では毎回問い合わせが発生することを確認するテスト
- 見つからなかった場合（`None`）もキャッシュされ、2回目はモックが呼ばれないことを確認するテスト

`app/ui/direct_label_dialog.py` 側（`_PostalLookupThread` とダイアログ配線）はPyQt UIで既存の自動テスト対象外のため、実装後に `QT_QPA_PLATFORM=offscreen` を用いたheadless実行で、スレッドが正しい `progress`/`finished_all` シグナルを発行し、テーブルに反映されることを確認する。実機でのネットワーク通信を伴う目視確認（進捗ダイアログの表示・キャンセルボタンの動作）は、可能であればユーザー側で最終確認する。
