# 住所2・事業所名2入力対応と氏名折り返し Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 宛名ラベル新規作成ダイアログで「住所2」「事業所名2」を別入力欄として入力できるようにし、氏名欄に長いテキスト（役職名＋氏名＋敬称の結合データ）が入っても適切に折り返して表示されるようにする。

**Architecture:** DB（`company_name2`列を新規追加）→ CSV/貼り付けパーサー（`label_import.py`）→ 列マッピングダイアログ → 直接入力ダイアログの表 → PDF生成（`label_pdf_service.py`）の順にデータが流れる。住所1/2はDB・パーサー・PDF生成が既に対応済みのため、UI（表とマッピングダイアログ）の配線のみを追加する。事業所名2は新規にDBスキーマから配線する。氏名折り返しは独立した描画ロジック変更で、他の変更に依存しない。

**Tech Stack:** Python, PyQt6, SQLAlchemy, ReportLab（PDF生成）, PyMuPDF（`fitz`, テスト用PDF検証）, pytest

## Global Constraints

- ダイアログ初期幅・最小幅は780px以下、初期高さ・最小高さは600px以下（本プロジェクトのCLAUDE.md規約）。ただし `direct_label_dialog.py` は既存で940×580を使用しており、本計画では列追加のみでウィンドウサイズは変更しない（既存逸脱に手を入れない）。
- DBスキーマ変更は `init_db()` の起動時マイグレーション方式（列有無チェック→`ALTER TABLE`）を踏襲し、既存データを破壊しない。
- 既存の安全余白・クリップパス・印刷位置補正の仕組みには一切手を加えない。
- 対象設計書: `docs/superpowers/specs/2026-07-05-address-company-fields-design.md`

---

### Task 1: DBスキーマに `company_name2` を追加する

**Files:**
- Modify: `app/database/models.py:56, 80-85`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `LabelEntry.company_name2: str`（デフォルト `""`）。以降のタスクはこのカラムに読み書きする。

- [ ] **Step 1: 失敗するテストを書く**

`tests/test_models.py` の `test_create_entry` を以下のように変更する（`company_name2` を追加）:

```python
def test_create_entry(session):
    batch = LabelBatch(batch_name="テスト", label_mode="normal")
    session.add(batch)
    session.flush()
    entry = LabelEntry(
        batch_id=batch.id,
        sort_order=0,
        client_id=None,
        company_name="株式会社テスト",
        company_name2="",
        postal_code="100-0001",
        address1="東京都千代田区",
        address2="",
        title="部長",
        person_name="山田太郎",
    )
    session.add(entry)
    session.commit()
    assert entry.id is not None
    assert entry.client_id is None
    assert entry.company_name2 == ""
```

同ファイルの末尾に新規テストを追加する:

```python
def test_create_entry_with_company_name2(session):
    batch = LabelBatch(batch_name="テスト2", label_mode="normal")
    session.add(batch)
    session.flush()
    entry = LabelEntry(
        batch_id=batch.id,
        sort_order=0,
        company_name="株式会社テスト",
        company_name2="○○支店",
    )
    session.add(entry)
    session.commit()
    assert entry.company_name2 == "○○支店"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_models.py -v`
Expected: `test_create_entry` と `test_create_entry_with_company_name2` が `TypeError: 'company_name2' is an invalid keyword argument for LabelEntry` で FAIL

- [ ] **Step 3: `LabelEntry` に列を追加する**

`app/database/models.py:50-51` を以下のように変更する（`company_name` の直後に追加）:

```python
    company_name    = Column(String(200), default="")
    company_name2   = Column(String(200), default="")
    company_kana    = Column(String(200), default="")
```

`app/database/models.py:79-82` の `company_kana` マイグレーションブロックの直後に、同じパターンで移行コードを追加する:

```python
        if "company_kana" not in cols:
            conn.execute(text("ALTER TABLE label_entries ADD COLUMN company_kana VARCHAR(200) DEFAULT ''"))
            conn.commit()
        if "company_name2" not in cols:
            conn.execute(text("ALTER TABLE label_entries ADD COLUMN company_name2 VARCHAR(200) DEFAULT ''"))
            conn.commit()
        if "barcode_address" not in cols:
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_models.py -v`
Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add app/database/models.py tests/test_models.py
git commit -m "feat: LabelEntryにcompany_name2カラムを追加"
```

---

### Task 2: PDF生成で事業所名1・2を結合して描画する

**Files:**
- Modify: `app/services/label_pdf_service.py:322-329`（`_draw_label` 内の変数組み立て部分）
- Test: `tests/test_label_pdf_service.py`

**Interfaces:**
- Consumes: `entry.company_name2`（Task 1 で追加された属性。`_FakeEntry` にも追加する）
- Produces: `_draw_label` に渡される `company` 変数は `company_name` と `company_name2` を `"\n"` 結合した文字列になる（既存の複数行描画ロジックがそのまま処理する）

- [ ] **Step 1: `_FakeEntry` に `company_name2` を追加し、失敗するテストを書く**

`tests/test_label_pdf_service.py` の `_FakeEntry.__init__` を以下のように変更する:

```python
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
```

同ファイルの末尾に新規テストを追加する:

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_label_pdf_service.py -k company_name2 -v`
Expected: `test_draw_label_combines_company_name_and_name2` が `AssertionError`（`captured["company"]` が `"株式会社テスト"` のままで `"\n○○支店"` が付与されていない）で FAIL

- [ ] **Step 3: `_draw_label` で事業所名を結合する**

`app/services/label_pdf_service.py:322-329` を以下のように変更する（`company` の組み立て直後に結合処理を追加）:

```python
    company      = entry.company_name or ""
    company2     = getattr(entry, "company_name2", "") or ""
    if company2:
        company = f"{company}\n{company2}" if company else company2
    postal       = entry.postal_code  or ""
    addr1        = entry.address1     or ""
    addr2        = entry.address2     or ""
    title        = entry.title        or ""
    person       = entry.person_name  or ""
    barcode_addr = getattr(entry, 'barcode_address', '') or ""
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_label_pdf_service.py -k company_name2 -v`
Expected: 2件 PASS

- [ ] **Step 5: 既存テストが壊れていないことを確認する**

Run: `pytest tests/test_label_pdf_service.py -v`
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add app/services/label_pdf_service.py tests/test_label_pdf_service.py
git commit -m "feat: PDF生成でcompany_name/company_name2を結合して描画する"
```

---

### Task 3: 氏名ブロックの折り返し・敬称重複防止

**Files:**
- Modify: `app/services/label_pdf_service.py:349-473`（`_draw_normal` 関数。氏名ブロックのみ変更）
- Test: `tests/test_label_pdf_service.py`

**Interfaces:**
- Produces: モジュール関数 `_layout_person_line(person: str, font: str, max_fs: float, avail_w: float, wrap_fs: float = 9.0, min_fs: float = 7.0) -> tuple[list[str], float]`
  - 戻り値は `(行のリスト, フォントサイズ)`。1行に収まれば `len(lines) == 1`、収まらなければ最大2行。
  - 敬称「様」が既に末尾にあれば追加しない。

- [ ] **Step 1: `_layout_person_line` の失敗するテストを書く**

`tests/test_label_pdf_service.py` の末尾に追加する:

```python
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
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_label_pdf_service.py -k layout_person_line -v`
Expected: 全件 `AttributeError: module 'app.services.label_pdf_service' has no attribute '_layout_person_line'` で FAIL

- [ ] **Step 3: `_layout_person_line` を実装する**

`app/services/label_pdf_service.py` の `_draw_normal` 関数の直前（342行目あたり、`# ── 通常モード` の見出しの前）に新規関数を追加する:

```python
def _layout_person_line(person: str, font: str, max_fs: float, avail_w: float,
                         wrap_fs: float = 9.0, min_fs: float = 7.0) -> tuple[list[str], float]:
    """
    氏名テキストのレイアウトを決定する（描画は行わない）。

    戻り値: (行のリスト（1行 or 最大2行）, フォントサイズ)
    敬称「様」が末尾に既にあれば追加しない（役職名＋氏名＋敬称が
    1セルに結合された業務データを想定）。avail_w に1行で収まらない
    場合は wrap_fs で2行に折り返し、それでも収まらなければ min_fs まで
    0.5pt刻みで縮小する。
    """
    person_stripped = person.strip()
    suffix = "" if person_stripped.endswith("様") else "　様"
    name_line = person_stripped + suffix

    if stringWidth(name_line, font, wrap_fs) <= avail_w:
        fs = _fit_text(name_line, font, max_fs, avail_w, min_size=wrap_fs)
        return [name_line], fs

    fs = wrap_fs
    line1, line2 = _split_line(name_line, font, fs, avail_w)
    while line2 and stringWidth(line2, font, fs) > avail_w and fs > min_fs:
        fs -= 0.5
        line1, line2 = _split_line(name_line, font, fs, avail_w)
    return [line1, line2], fs
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_label_pdf_service.py -k layout_person_line -v`
Expected: 5件 PASS

- [ ] **Step 5: `_draw_normal` の氏名ブロックを `_layout_person_line` を使うように書き換える失敗テストを書く**

`tests/test_label_pdf_service.py` の末尾に追加する:

```python
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
```

- [ ] **Step 6: テストを実行して失敗を確認する**

Run: `pytest tests/test_label_pdf_service.py -k draw_normal_wraps -v`
Expected: `test_draw_normal_wraps_long_person_name_into_two_drawstring_calls` が FAIL（現状は1回しか `drawString` されず `len(name_draws) == 1` で assert に失敗）

- [ ] **Step 7: `_draw_normal` の氏名ブロックを書き換える**

`app/services/label_pdf_service.py:451-465` の以下のブロックを:

```python
    # ── 氏名 + 様（役職あり: 少し余白、役職なし: 詰めて配置）──────────
    if person:
        name_line = f"{person}　様"
        name_fs   = _fit_text(name_line, font, name_max_fs, inner_w - (indent2 - P))
        name_y    = max(y0 + P * 0.8, cur_y)
        c.setFont(font, name_fs)
        c.setFillColor(black)
        c.drawString(x0 + indent2, name_y, name_line)
    else:
```

以下に置き換える:

```python
    # ── 氏名 + 様（役職あり: 少し余白、役職なし: 詰めて配置）──────────
    if person:
        name_avail = inner_w - (indent2 - P)
        lines, name_fs = _layout_person_line(person, font, name_max_fs, name_avail)
        c.setFont(font, name_fs)
        c.setFillColor(black)
        if len(lines) == 1:
            name_y = max(y0 + P * 0.8, cur_y)
            c.drawString(x0 + indent2, name_y, lines[0])
        else:
            line_h_name = name_fs * 1.15
            y_line2 = max(y0 + P * 0.8, cur_y - line_h_name)
            y_line1 = y_line2 + line_h_name
            c.drawString(x0 + indent2, y_line1, lines[0])
            c.drawString(x0 + indent2, y_line2, lines[1])
    else:
```

（後続の `gochu_fs = max(7.0, 10.0 * scale)` 以降の `else` ブロックは変更しない）

- [ ] **Step 8: テストを実行して成功を確認する**

Run: `pytest tests/test_label_pdf_service.py -v`
Expected: 全テスト PASS

- [ ] **Step 9: コミット**

```bash
git add app/services/label_pdf_service.py tests/test_label_pdf_service.py
git commit -m "feat: 氏名欄の折り返しと敬称重複防止に対応"
```

---

### Task 4: CSV/貼り付けパーサーに `company_name2` を追加する

**Files:**
- Modify: `app/utils/label_import.py:21-31, 193-231`
- Test: `tests/test_label_import.py`（新規作成）

**Interfaces:**
- Produces: `DirectRow.company_name2: str`、`_DIR_COMPANY2: set[str]`（`_extract_direct_row`・`_cols_to_direct_row` が参照する）

- [ ] **Step 1: 失敗するテストを書く**

新規ファイル `tests/test_label_import.py` を作成する:

```python
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.label_import import _extract_direct_row, _cols_to_direct_row, DirectRow


def test_extract_direct_row_reads_company_name2():
    row = {"事業所名": "株式会社テスト", "事業所名2": "○○支店", "氏名": "山田太郎"}
    dr = _extract_direct_row(row)
    assert dr.company_name == "株式会社テスト"
    assert dr.company_name2 == "○○支店"


def test_extract_direct_row_company_name2_optional():
    row = {"事業所名": "株式会社テスト", "氏名": "山田太郎"}
    dr = _extract_direct_row(row)
    assert dr.company_name2 == ""


def test_cols_to_direct_row_with_company_name2():
    dr = _cols_to_direct_row(
        ["株式会社テスト", "○○支店", "山田太郎"],
        ["company_name", "company_name2", "person_name"],
    )
    assert dr.company_name == "株式会社テスト"
    assert dr.company_name2 == "○○支店"
    assert dr.person_name == "山田太郎"
```

- [ ] **Step 2: テストを実行して失敗を確認する**

Run: `pytest tests/test_label_import.py -v`
Expected: 全件 FAIL（`DirectRow` に `company_name2` 属性がない、または `AttributeError`/`AssertionError`）

- [ ] **Step 3: `label_import.py` に `company_name2` を追加する**

`app/utils/label_import.py:21-31` の `DirectRow` を以下のように変更する:

```python
@dataclass
class DirectRow:
    """直接貼り付けモード用：住所を含むすべての情報を自前で持つ"""
    company_name: str = ""
    company_name2: str = ""
    company_kana: str = ""
    postal_code:  str = ""
    address1:     str = ""
    address2:     str = ""
    title:        str = ""
    person_name:  str = ""
```

`app/utils/label_import.py:192-199`（直接入力の列名マッピング定義）に `_DIR_COMPANY2` を追加する:

```python
# 直接入力の列名マッピング
_DIR_COMPANY  = {"企業名", "会社名", "事業所名", "company"}
_DIR_COMPANY2 = {"事業所名2", "会社名2", "company2"}
_DIR_KANA     = {"フリガナ", "読み", "よみ", "ふりがな", "kana"}
_DIR_POSTAL   = {"郵便番号", "postal", "zip"}
_DIR_ADDR1    = {"住所", "住所1", "address", "address1"}
_DIR_ADDR2    = {"住所2", "address2"}
_DIR_TITLE    = {"肩書", "所属", "役職", "部署", "所属・役職", "title", "department"}
_DIR_PERSON   = {"氏名", "名前", "担当者", "person", "name"}
```

`app/utils/label_import.py:211-231` の `_extract_direct_row` / `_cols_to_direct_row` を以下のように変更する:

```python
def _extract_direct_row(row_dict: dict) -> DirectRow:
    """ヘッダー付き辞書から DirectRow を生成する"""
    norm = {_normalize(k): v for k, v in row_dict.items()}

    def _pick(keys):
        for k in keys:
            v = norm.get(_normalize(k), "")
            v = _strip_excel_formula(v)
            if v:
                return v
        return ""

    return DirectRow(
        company_name=_pick(_DIR_COMPANY),
        company_name2=_pick(_DIR_COMPANY2),
        company_kana=_pick(_DIR_KANA),
        postal_code =_pick(_DIR_POSTAL),
        address1    =_pick(_DIR_ADDR1),
        address2    =_pick(_DIR_ADDR2),
        title       =_pick(_DIR_TITLE),
        person_name =_pick(_DIR_PERSON),
    )


def _cols_to_direct_row(cols: list[str], field_order: list[str]) -> DirectRow:
    """列値リストとフィールド名リストから DirectRow を生成する"""
    mapping = {field_order[i]: (cols[i].strip() if i < len(cols) else "")
               for i in range(len(field_order))}
    return DirectRow(
        company_name=mapping.get("company_name", ""),
        company_name2=mapping.get("company_name2", ""),
        company_kana=mapping.get("company_kana", ""),
        postal_code =mapping.get("postal_code",  ""),
        address1    =mapping.get("address1",      ""),
        address2    =mapping.get("address2",      ""),
        title       =mapping.get("title",         ""),
        person_name =mapping.get("person_name",   ""),
    )
```

- [ ] **Step 4: テストを実行して成功を確認する**

Run: `pytest tests/test_label_import.py -v`
Expected: 全テスト PASS

- [ ] **Step 5: 既存テストが壊れていないことを確認する**

Run: `pytest tests/ -v`
Expected: 全テスト PASS

- [ ] **Step 6: コミット**

```bash
git add app/utils/label_import.py tests/test_label_import.py
git commit -m "feat: CSV/貼り付けパーサーにcompany_name2の認識を追加"
```

---

### Task 5: 直接入力ダイアログの表に「事業所名2」「住所2」列を追加する（構造のみ）

**Files:**
- Modify: `app/ui/direct_label_dialog.py:58-84, 853-860`

**Interfaces:**
- Consumes: なし（このタスクは列定義のみを変更し、データ配線はTask 6で行う）
- Produces: 新しい列定数 `COL_COMPANY2`, `COL_ADDR1`（`COL_ADDR` からリネーム）, `COL_ADDR2`。以降のタスクはこれらの定数を使う。

このタスクはPyQt UIの構造変更であり、既存の自動テスト対象外（`direct_label_dialog.py` にはテストファイルがない）。各ステップの後、目視確認の代わりにPythonの構文チェックを行う。

- [ ] **Step 1: 列定数と `_COLS` を書き換える**

`app/ui/direct_label_dialog.py:58-84` を以下のように変更する:

```python
    COL_CHK      = 0
    COL_COMPANY  = 1
    COL_COMPANY2 = 2
    COL_KANA     = 3
    COL_TITLE    = 4
    COL_PERSON   = 5
    COL_POSTAL   = 6
    COL_ADDR1    = 7
    COL_ADDR2    = 8
    COL_BC_ADDR  = 9

    _REQUIRED_COLS: dict[str, set] = {
        "normal":    {COL_COMPANY, COL_PERSON, COL_ADDR1},
        "no_person": {COL_COMPANY, COL_ADDR1},
        "simple":    {COL_COMPANY},
        "nametag":   {COL_COMPANY, COL_PERSON},
        "split4":    {COL_COMPANY},
    }

    _COLS = [
        ("",              32,  QHeaderView.ResizeMode.Fixed),
        ("事業所名",      170, QHeaderView.ResizeMode.Stretch),
        ("事業所名2",     130, QHeaderView.ResizeMode.Interactive),
        ("フリガナ",      130, QHeaderView.ResizeMode.Interactive),
        ("所属・役職名",  130, QHeaderView.ResizeMode.Interactive),
        ("氏名",          120, QHeaderView.ResizeMode.Interactive),
        ("郵便番号",       90, QHeaderView.ResizeMode.Fixed),
        ("住所1",         180, QHeaderView.ResizeMode.Stretch),
        ("住所2",         130, QHeaderView.ResizeMode.Interactive),
        ("住所表示番号",  130, QHeaderView.ResizeMode.Fixed),
    ]
```

- [ ] **Step 2: `_HIDDEN_COLS` を書き換える**

`app/ui/direct_label_dialog.py:853-860` を以下のように変更する:

```python
    # モードごとに非表示にする列（COL_BC_ADDR は常時非表示のため除外）
    _HIDDEN_COLS: dict[str, set] = {
        "normal":    set(),
        "no_person": {COL_TITLE, COL_PERSON},
        "simple":    {COL_TITLE, COL_PERSON, COL_POSTAL, COL_ADDR1, COL_ADDR2},
        "nametag":   {COL_POSTAL, COL_ADDR1, COL_ADDR2},
        "split4":    {COL_TITLE, COL_PERSON, COL_POSTAL, COL_ADDR1, COL_ADDR2},
    }
```

- [ ] **Step 3: `COL_ADDR` を `COL_ADDR1` に一括リネームする**

`app/ui/direct_label_dialog.py` 内に残っている `self.COL_ADDR`（Step 1/2 で書き換えた箇所以外）をすべて `self.COL_ADDR1` に置換する。対象は以下の6箇所（Step 1実施前の行番号）:
- 540行目: `_populate_barcode_addr` 内 `addr = (self.table.item(row, self.COL_ADDR) ...)`
- 673行目: `_fill_postal_codes` 内の対象行フィルタ
- 684行目: `_fill_postal_codes` 内の `address = ...`
- 1082行目: `_preview_pdf` 内 `"address1": _cell(self.COL_ADDR)`
- 1241行目: `_export` 内 `"address1": _cell(self.COL_ADDR)`

置換は文字列 `self.COL_ADDR` → `self.COL_ADDR1` の単純な一括置換でよい（`self.COL_ADDR2` は元々存在しないため誤爆しない）。

- [ ] **Step 4: 構文エラーがないことを確認する**

Run: `python -c "import ast; ast.parse(open('app/ui/direct_label_dialog.py', encoding='utf-8').read())"`
Expected: エラーなく終了（出力なし）

- [ ] **Step 5: アプリを起動して表に2列増えていることを目視確認する**

Run: `python main.py`
「ラベル」→「新規作成（直接入力）」を開き、表の列見出しが
`事業所名 / 事業所名2 / フリガナ / 所属・役職名 / 氏名 / 郵便番号 / 住所1 / 住所2 / 住所表示番号`
の順になっていることを確認する。行を追加して各列に入力できることを確認する。

- [ ] **Step 6: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: 直接入力ダイアログの表に事業所名2・住所2列を追加"
```

---

### Task 6: 直接入力ダイアログのデータ配線（住所2・事業所名2をPDF/DBに反映）

**Files:**
- Modify: `app/ui/direct_label_dialog.py:763-775, 1071-1086, 1125-1161, 1230-1247`

**Interfaces:**
- Consumes: `COL_COMPANY2`, `COL_ADDR1`, `COL_ADDR2`（Task 5）、`DirectRow.company_name2`（Task 4）
- Produces: プレビュー・DB保存・バッチ読込のすべてで住所2・事業所名2が実際の値で往復する

このタスクもPyQt UI変更のため自動テスト対象外。目視確認を各ステップに含める。

- [ ] **Step 1: `_load_batch` を書き換える**

`app/ui/direct_label_dialog.py:763-775` の以下のブロックを:

```python
        for e in entries:
            addr = e.address1 or ""
            if e.address2:
                addr = addr + (" " if addr else "") + e.address2
            self._add_row([
                e.company_name    or "",
                e.company_kana    or "",
                e.title           or "",
                e.person_name     or "",
                e.postal_code     or "",
                addr,
                e.barcode_address or "",
            ])
```

以下に置き換える（住所1・住所2、事業所名・事業所名2をそれぞれ独立した列に設定する）:

```python
        for e in entries:
            self._add_row([
                e.company_name    or "",
                getattr(e, "company_name2", "") or "",
                e.company_kana    or "",
                e.title           or "",
                e.person_name     or "",
                e.postal_code     or "",
                e.address1        or "",
                e.address2        or "",
                e.barcode_address or "",
            ])
```

- [ ] **Step 2: `_preview_pdf` のエントリ組み立てを書き換える**

`app/ui/direct_label_dialog.py:1071-1086` の以下のブロックを:

```python
        entries = []
        for row in checked_rows:
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            entries.append(type("_E", (), {
                "company_name":    _cell(self.COL_COMPANY),
                "company_kana":    _cell(self.COL_KANA),
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR),
                "address2":        "",
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })())
```

以下に置き換える:

```python
        entries = []
        for row in checked_rows:
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            entries.append(type("_E", (), {
                "company_name":    _cell(self.COL_COMPANY),
                "company_name2":   _cell(self.COL_COMPANY2),
                "company_kana":    _cell(self.COL_KANA),
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR1),
                "address2":        _cell(self.COL_ADDR2),
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })())
```

- [ ] **Step 3: `_fill_rows` と `_import_rows` を書き換える**

`app/ui/direct_label_dialog.py:1125-1134` の以下のブロックを:

```python
        for dr in direct_rows:
            self._add_row([
                dr.company_name,
                dr.company_kana,
                dr.title,
                dr.person_name,
                dr.postal_code,
                dr.address1 + (" " + dr.address2 if dr.address2 else ""),
            ])
```

以下に置き換える:

```python
        for dr in direct_rows:
            self._add_row([
                dr.company_name,
                dr.company_name2,
                dr.company_kana,
                dr.title,
                dr.person_name,
                dr.postal_code,
                dr.address1,
                dr.address2,
            ])
```

`app/ui/direct_label_dialog.py:1136-1161` の `_import_rows` 内、`DirectRow(...)` の組み立てを:

```python
            dr = DirectRow(
                company_name=_get("company_name"),
                company_kana=_get("company_kana"),
                postal_code =_get("postal_code"),
                address1    =_get("address1"),
                title       =_get("title"),
                person_name =_get("person_name"),
            )
```

以下に置き換える:

```python
            dr = DirectRow(
                company_name=_get("company_name"),
                company_name2=_get("company_name2"),
                company_kana=_get("company_kana"),
                postal_code =_get("postal_code"),
                address1    =_get("address1"),
                address2    =_get("address2"),
                title       =_get("title"),
                person_name =_get("person_name"),
            )
```

- [ ] **Step 4: `_export` の保存用辞書組み立てを書き換える**

`app/ui/direct_label_dialog.py:1230-1247` の以下のブロックを:

```python
        all_entry_dicts = []
        for row in range(self.table.rowCount()):
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            all_entry_dicts.append({
                "sort_order":      row,
                "client_id":       None,
                "company_name":    _cell(self.COL_COMPANY),
                "company_kana":    _cell(self.COL_KANA),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR),
                "address2":        "",
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })
```

以下に置き換える:

```python
        all_entry_dicts = []
        for row in range(self.table.rowCount()):
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            all_entry_dicts.append({
                "sort_order":      row,
                "client_id":       None,
                "company_name":    _cell(self.COL_COMPANY),
                "company_name2":   _cell(self.COL_COMPANY2),
                "company_kana":    _cell(self.COL_KANA),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR1),
                "address2":        _cell(self.COL_ADDR2),
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })
```

- [ ] **Step 5: 構文エラーがないことを確認する**

Run: `python -c "import ast; ast.parse(open('app/ui/direct_label_dialog.py', encoding='utf-8').read())"`
Expected: エラーなく終了

- [ ] **Step 6: アプリを起動して住所2・事業所名2がPDFと再読込に反映されることを確認する**

Run: `python main.py`
1. 「新規作成（直接入力）」で1行追加し、事業所名＝「株式会社テスト」、事業所名2＝「○○支店」、住所1＝「東京都千代田区1-1」、住所2＝「○○ビル4F」、氏名＝「山田太郎」を入力する
2. レイアウトを「A-ONE 28185（3列）」にして「プレビュー」を押し、PDFに事業所名2行目・住所2行目が表示されることを確認する
3. レイアウトを「A-ONE 28187（2列）」に変えて同様に確認する
4. 「保存」してダイアログを閉じ、再度同じバッチを開いて事業所名2・住所2が別セルに正しく復元されることを確認する

- [ ] **Step 7: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: 直接入力ダイアログで住所2・事業所名2をPDF/DBに反映する"
```

---

### Task 7: 列マッピングダイアログに「住所2」「事業所名2」を追加する

**Files:**
- Modify: `app/ui/column_mapping_dialog.py:16-46, 121-140`

**Interfaces:**
- Consumes: `_DIR_COMPANY2`, `_DIR_ADDR2`（Task 4 で追加済み）
- Produces: `ColumnMappingDialog.get_mapping()` の戻り値に `"address2"`, `"company_name2"` キーが含まれる

- [ ] **Step 1: import文と `_FIELDS`／`_FIELD_HINTS` を書き換える**

`app/ui/column_mapping_dialog.py:16-19` を以下のように変更する:

```python
from app.utils.label_import import (
    _normalize, _DIR_COMPANY, _DIR_COMPANY2, _DIR_KANA, _DIR_POSTAL,
    _DIR_ADDR1, _DIR_ADDR2, _DIR_TITLE, _DIR_PERSON,
    _FALLBACK_COLS,
)
```

`app/ui/column_mapping_dialog.py:25-46` を以下のように変更する:

```python
    _FIELDS = [
        ("company_name",  "事業所名"),
        ("company_name2", "事業所名2"),
        ("company_kana",  "フリガナ（読み）"),
        ("title",         "所属・役職名"),
        ("person_name",   "氏名"),
        ("postal_code",   "郵便番号"),
        ("address1",      "住所1"),
        ("address2",      "住所2"),
    ]

    _REQUIRED_BY_MODE: dict[str, set] = {
        "normal":    {"company_name", "address1", "person_name"},
        "no_person": {"company_name", "address1"},
        "simple":    {"company_name"},
        "nametag":   {"company_name", "person_name"},
        "split4":    {"company_name"},
    }

    _FIELD_HINTS: dict[str, str] = {
        "company_name2": "任意",
        "company_kana":  "任意・自動入力可",
        "title":         "任意",
        "postal_code":   "任意・自動入力可",
        "address2":      "任意",
    }
```

- [ ] **Step 2: `_auto_detect()` を書き換える**

`app/ui/column_mapping_dialog.py:121-130` の以下のブロックを:

```python
    def _auto_detect(self) -> None:
        """ヘッダー名からフィールドを自動マッピングする"""
        field_keys = {
            "company_name": _DIR_COMPANY,
            "company_kana": _DIR_KANA,
            "postal_code":  _DIR_POSTAL,
            "address1":     _DIR_ADDR1,
            "title":        _DIR_TITLE,
            "person_name":  _DIR_PERSON,
        }
```

以下に置き換える:

```python
    def _auto_detect(self) -> None:
        """ヘッダー名からフィールドを自動マッピングする"""
        field_keys = {
            "company_name":  _DIR_COMPANY,
            "company_name2": _DIR_COMPANY2,
            "company_kana":  _DIR_KANA,
            "postal_code":   _DIR_POSTAL,
            "address1":      _DIR_ADDR1,
            "address2":      _DIR_ADDR2,
            "title":         _DIR_TITLE,
            "person_name":   _DIR_PERSON,
        }
```

- [ ] **Step 3: 構文エラーがないことを確認する**

Run: `python -c "import ast; ast.parse(open('app/ui/column_mapping_dialog.py', encoding='utf-8').read())"`
Expected: エラーなく終了

- [ ] **Step 4: アプリを起動して列マッピングダイアログを目視確認する**

Run: `python main.py`
「新規作成（直接入力）」→「CSV取込」または「貼り付け」で、ヘッダー行に「事業所名2」「住所2」を含まないデータを読み込ませ、列マッピングダイアログに「事業所名2」「住所2」の選択肢（任意）が表示されることを確認する。「住所1」の表示ラベルが「住所」から変わっていることも確認する。

- [ ] **Step 5: コミット**

```bash
git add app/ui/column_mapping_dialog.py
git commit -m "feat: 列マッピングダイアログに事業所名2・住所2を追加"
```

---

### Task 8: 全体の回帰確認

**Files:** なし（確認のみ）

- [ ] **Step 1: 全自動テストを実行する**

Run: `pytest tests/ -v`
Expected: 全テスト PASS

- [ ] **Step 2: 手動でエンドツーエンド確認する**

Run: `python main.py`
1. CSVファイル（ヘッダー: 事業所名, 事業所名2, 郵便番号, 住所1, 住所2, 所属・役職, 氏名）を用意し取込む → 自動マッピングされることを確認
2. 氏名に「特別顧問兼代表取締役社長　山田太郎様」のような長いテキストを直接入力し、3列（A-ONE 28185）・2列（A-ONE 28187）それぞれでプレビューし、2行に折り返って表示され「様」が二重にならないことを確認
3. 名札（A-ONE 51002）レイアウトでも事業所名2が事業所名の下段に表示されることを確認（対象外にしていないため）

- [ ] **Step 3: バージョン更新（任意、ユーザー確認の上で実施）**

`app/version.py` のバージョン番号を更新し、コミットする（このステップはユーザーに確認してから実施する）。
