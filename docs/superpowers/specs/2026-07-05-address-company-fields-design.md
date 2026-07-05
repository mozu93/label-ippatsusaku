# 宛名ラベル：住所2・事業所名2の入力対応／氏名折り返し 設計書

**作成日:** 2026-07-05
**対象バージョン:** 次期リリース（予定）

---

## 1. 概要

「宛名ラベル 新規作成」ダイアログ（`DirectLabelDialog`）で、以下3点を改善する。

1. 住所を「住所1」「住所2」の2つの入力欄に分けられるようにする（DBスキーマ・PDF描画は既に対応済みだが、UI側の入力導線が欠けている）
2. 事業所名を「事業所名」「事業所名2」の2つの入力欄に分けられるようにする（新規機能。DBスキーマ追加が必要）
3. 氏名欄に「役職名＋氏名＋敬称」が結合された長いテキストを入れた場合に、適切に折り返して表示する（現状はフォント縮小のみで折り返さない）

対象は主に3列レイアウト（A-ONE 28185）・2列レイアウト（A-ONE 28187）で使う `normal` モードだが、事業所名2は仕組み上 `no_person`/`nametag`/`simple` でも自動的に利用可能になる。

---

## 2. 仕様詳細

### 2.1 住所2の入力対応

**現状:** `app/database/models.py` の `LabelEntry.address2`、`app/utils/label_import.py` の `DirectRow.address2` / `_DIR_ADDR2` / 6列フォールバックは既に実装済み。`app/services/label_pdf_service.py` の `_draw_normal` / `_draw_no_person` も住所1（折り返しあり）→住所2（折り返しなし・単一行）の順に描画済み。**UI（`direct_label_dialog.py` のテーブルと `column_mapping_dialog.py` の列マッピング）にのみ導線がなく、常に空文字が渡されている。**

**変更内容（`app/ui/direct_label_dialog.py`）:**
- 列定数に `COL_ADDR2` を追加し、既存 `COL_ADDR` は `COL_ADDR1` にリネーム
- `_COLS` に「住所2」列を追加し、既存「住所」表記は「住所1」に変更
- `_REQUIRED_COLS`：住所2はどのモードでも必須にしない（住所1のみ必須のまま）
- `_HIDDEN_COLS`：住所1が非表示になるモード（`simple`/`nametag`/`split4`）では住所2も同様に非表示
- `_load_batch`：`e.address1` と `e.address2` を結合せず、2つのセルにそれぞれ設定する（現状は1セルに連結していた処理を廃止）
- `_fill_rows`：`DirectRow.address2` を専用列に反映する（現状は住所1と連結していた処理を廃止）
- `_import_rows`：`DirectRow(..., address2=_get("address2"), ...)` を追加
- `_preview_pdf` / `_export`：ハードコードされている `"address2": ""` を実際のセル値に変更
- `_fill_postal_codes` / `_populate_barcode_addr`：住所1のみ参照する（住所2は見ない。既存の単一列版と挙動は変わらない）

**変更内容（`app/ui/column_mapping_dialog.py`）:**
- `_FIELDS` に `("address2", "住所2")` を追加。既存 `("address1", "住所")` は `("address1", "住所1")` に変更
- `_FIELD_HINTS` に `"address2": "任意"` を追加（必須にしない）
- `_auto_detect()` の `field_keys` に `"address2": _DIR_ADDR2` を追加（`app.utils.label_import` から import）

`app/utils/label_import.py` は変更不要。

### 2.2 事業所名2の追加

**現状:** `company_name2` に相当するカラムがDBに存在しない。新規追加が必要。

**DBスキーマ（`app/database/models.py`）:**
- `LabelEntry` に `company_name2 = Column(String(200), default="")` を追加
- `init_db()` に `company_kana` 追加時と同じパターンで移行コードを追加：
  ```python
  if "company_name2" not in cols:
      conn.execute(text("ALTER TABLE label_entries ADD COLUMN company_name2 VARCHAR(200) DEFAULT ''"))
      conn.commit()
  ```
  起動時に自動追加され、既存データは空文字で初期化されるため既存データへの影響はない。

**PDF生成（`app/services/label_pdf_service.py`）:** 変更不要。既存の事業所名描画ロジック（`_draw_normal`/`_draw_no_person`/`_draw_nametag`/`_draw_simple`）は `"\n"` 区切りの複数行入力と自動折り返しに既に対応している。`_draw_label` 内で以下のように結合するだけで、既存ロジックをそのまま再利用する：

```python
company = entry.company_name or ""
company2 = getattr(entry, "company_name2", "") or ""
if company2:
    company = f"{company}\n{company2}" if company else company2
```

**UI（`app/ui/direct_label_dialog.py`）:**
- 「事業所名」列の隣に新規「事業所名2」列を追加（列定数を振り直し）
- 必須項目にはしない（事業所名のみ必須のまま）
- 表示・非表示のモード別制御は事業所名と同じ扱い（常時表示）
- `_load_batch` / `_fill_rows` / `_import_rows` / `_preview_pdf` / `_export` に `company_name2` を配線

**CSV/貼り付け（`app/utils/label_import.py` + `column_mapping_dialog.py`）:**
- `DirectRow` に `company_name2: str = ""` を追加
- 認識ヘッダー `_DIR_COMPANY2 = {"事業所名2", "会社名2", "company2"}` を追加
- `_extract_direct_row` / `_cols_to_direct_row` に `company_name2` の取り出しを追加
- 列マッピングダイアログに `("company_name2", "事業所名2")`（任意）を追加
- ヘッダーなし時の列数フォールバック（`_FALLBACK_COLS`）には追加しない（フリガナ・バーコード住所と同様に対象外とする既存方針を踏襲）

### 2.3 氏名ブロックの折り返し・敬称重複防止

対象は `app/services/label_pdf_service.py` の `_draw_normal` 内、氏名描画部分のみ（`no_person`/`nametag`/`simple`/`split4` は対象外）。

**敬称重複防止:** 氏名テキスト（前後の空白を除去した上で）の末尾が「様」であれば、自動追加の「　様」を付与しない。

```python
person_stripped = person.strip()
suffix = "" if person_stripped.endswith("様") else "　様"
name_line = person_stripped + suffix
```

**折り返し（最大2行）:** 基準サイズ（9pt）で1行に収まるなら、事業所名と同様に最大11pt（既存の `name_max_fs`）まで拡大して1行描画。収まらない場合は9ptで最大2行に折り返す。2行目もなお収まらない極端に長いテキストは、9pt→7ptまで0.5pt刻みで縮小しながら2行に収める（それでも入り切らない場合はラベル枠のクリップパス — 既存の安全策 — に任せる）。

```python
name_avail = inner_w - (indent2 - P)
WRAP_FS = 9.0
MIN_FS  = 7.0

if stringWidth(name_line, font, WRAP_FS) <= name_avail:
    fs = _fit_text(name_line, font, name_max_fs, name_avail, min_size=WRAP_FS)
    name_y = max(y0 + P * 0.8, cur_y)
    c.setFont(font, fs)
    c.setFillColor(black)
    c.drawString(x0 + indent2, name_y, name_line)
else:
    fs = WRAP_FS
    line1, line2 = _split_line(name_line, font, fs, name_avail)
    while line2 and stringWidth(line2, font, fs) > name_avail and fs > MIN_FS:
        fs -= 0.5
        line1, line2 = _split_line(name_line, font, fs, name_avail)
    line_h_name = fs * 1.15
    y_line2 = max(y0 + P * 0.8, cur_y - line_h_name)
    y_line1 = y_line2 + line_h_name
    c.setFont(font, fs)
    c.setFillColor(black)
    c.drawString(x0 + indent2, y_line1, line1)
    c.drawString(x0 + indent2, y_line2, line2)
```

`cur_y` は所属・事業所名ブロックの後に残っている描画開始位置（上から下へ流れる既存の変数）。所属・役職欄が別途入力されている通常ケースでは、1行に収まる限り挙動は変わらない。

---

## 3. 実装方針

**対象ファイル:**
- 修正: `app/database/models.py`（`company_name2` カラム追加・移行コード）
- 修正: `app/services/label_pdf_service.py`（`_draw_label` の事業所名結合、`_draw_normal` の氏名ブロック）
- 修正: `app/utils/label_import.py`（`DirectRow.company_name2`、`_DIR_COMPANY2`、抽出関数2箇所）
- 修正: `app/ui/column_mapping_dialog.py`（`address2`・`company_name2` のフィールド追加）
- 修正: `app/ui/direct_label_dialog.py`（列定数の追加・振り直し、`_COLS`、`_REQUIRED_COLS`、`_HIDDEN_COLS`、`_load_batch`、`_fill_rows`、`_import_rows`、`_preview_pdf`、`_export`）

---

## 4. テスト

- `tests/test_label_pdf_service.py`：
  - `_draw_label` 呼び出し時に `company_name` + `company_name2` が `"\n"` 結合されて描画関数に渡ることを確認するテスト
  - 氏名が「様」で終わる場合に「　様」が二重に追加されないことを確認するテスト
  - 長い氏名が2行に折り返されることを確認するテスト（1行の場合との比較）
- `tests/test_models.py`：`company_name2` カラムの読み書きを確認する既存パターンへの追加
- `app/ui/direct_label_dialog.py` / `column_mapping_dialog.py` はPyQt UIで既存の自動テスト対象外のため、実装後に実際にアプリを起動し、直接入力ダイアログでの住所2・事業所名2の入力／貼り付け／CSV列マッピング／PDFプレビュー（3列・2列レイアウト）を手動確認する。
