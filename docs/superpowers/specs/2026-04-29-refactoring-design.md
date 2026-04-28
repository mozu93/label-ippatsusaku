# リファクタリング設計: コード重複除去

**日付**: 2026-04-29  
**対象バージョン**: v1.2.7  
**目的**: コードの重複を除去し、保守性を向上させる

---

## 背景

以下の重複・不整合が確認された：

1. `_CheckableHeader` クラスが `label_list.py` と `direct_label_dialog.py` に全く同じコードで2重定義されている
2. `_MODE_LABEL` 辞書が `label_list.py` 内で2回定義されている（`_on_sort` と `_render`）
3. ボタンスタイル（`_BTN_PRIMARY`, `_BTN_SECONDARY`, `_BTN_DANGER`）が `direct_label_dialog.py` に独自定義されているが、`theme.py` の定数と重複している
4. `_do_paste` と `_do_csv` の処理フローが `direct_label_dialog.py` 内でほぼ同一

---

## 変更方針

ロジックの変更はしない。重複コードを「削除して import に置き換える」のみ。動作は変わらない。

---

## 変更ファイル一覧

| ファイル | 変更種別 | 内容 |
|---|---|---|
| `app/ui/widgets.py` | 新規作成 | 共有UIコンポーネント置き場 |
| `app/ui/theme.py` | 変更 | `BTN_SECONDARY` を追加 |
| `app/ui/label_list.py` | 変更 | `_CheckableHeader`・`_MODE_LABEL` を削除、import に置換 |
| `app/ui/direct_label_dialog.py` | 変更 | スタイル独自定義を削除、`_import_rows` メソッドを抽出 |

---

## 詳細設計

### 1. `app/ui/widgets.py`（新規）

共有UIコンポーネントを集約する新規ファイル。

**`CheckableHeader` クラス**（旧 `_CheckableHeader`）

- 現在 `label_list.py:33` と `direct_label_dialog.py:56` にほぼ同じコードが存在
- 差異あり: `label_list.py` は初期値 `False`、`direct_label_dialog.py` は初期値 `True`
- `__init__` に `initial_checked: bool = False` パラメータを追加して両方に対応する
- 両ファイルから `from app.ui.widgets import CheckableHeader` で使う
- `direct_label_dialog.py` 側は `CheckableHeader(self.table, initial_checked=True)` として呼ぶ

**`MODE_LABEL` 定数**

```python
MODE_LABEL: dict[str, str] = {
    "normal":    "宛名(氏名あり)",
    "no_person": "宛名(氏名なし)",
    "simple":    "事業所名のみ",
    "nametag":   "名札",
    "split4":    "卓上プレート",
}
```

- 現在 `label_list.py` の `_on_sort`（L224）と `_render`（L262）に2回定義されている
- こちらに1つだけ定義し、両メソッドから import して使う

---

### 2. `app/ui/theme.py`（変更）

`BTN_SECONDARY` スタイル定数を追加する。

```python
BTN_SECONDARY = (
    "QPushButton { background: white; color: #1565C0; border: 1px solid #1565C0; "
    "border-radius: 4px; padding: 0 20px; font-size: 13px; min-height: 34px; }"
    "QPushButton:hover { background: #E3F2FD; }"
    "QPushButton:disabled { color: #BDBDBD; border-color: #BDBDBD; }"
)
```

---

### 3. `app/ui/label_list.py`（変更）

- `_CheckableHeader` クラス定義（L33-72）を削除
- `from app.ui.widgets import CheckableHeader, MODE_LABEL` を追加
- `_on_sort` の `_MODE_LABEL` ローカル変数定義を削除、`MODE_LABEL` に置換
- `_render` の `MODE_LABEL` ローカル変数定義を削除、`MODE_LABEL` に置換
- `_CheckableHeader` のインスタンス化箇所を `CheckableHeader` に変更

---

### 4. `app/ui/direct_label_dialog.py`（変更）

**スタイル整理（L37-53）**

- `_BTN_PRIMARY`, `_BTN_DANGER` の独自定義を削除
- `_BTN_SECONDARY` の独自定義を削除
- `from app.ui.theme import BTN_PRIMARY, BTN_SECONDARY, BTN_DANGER` を追加
- ファイル内での参照名を `BTN_*` に統一（`_BTN_*` → `BTN_*`）

**`_CheckableHeader` 整理**

- クラス定義（L56-95）を削除
- `from app.ui.widgets import CheckableHeader` を追加
- インスタンス化箇所を `CheckableHeader(...)` に変更

**`_do_paste`/`_do_csv` の共通化**

- 共通フロー（`ColumnMappingDialog` 表示 → `mapping` 取得 → `DirectRow` リスト構築 → `_fill_rows` 呼び出し）を `_import_rows(headers, data_rows)` メソッドに抽出
- `_do_paste` はクリップボード読み込み後に `_import_rows` を呼ぶだけにする
- `_do_csv` はファイル読み込み後に `_import_rows` を呼ぶだけにする

---

## 完了条件

- [ ] 全既存テストが通る
- [ ] アプリが起動して一覧画面が表示される
- [ ] 新規作成・編集・PDF出力が動作する
- [ ] 重複コードが残っていない（grep で確認）
