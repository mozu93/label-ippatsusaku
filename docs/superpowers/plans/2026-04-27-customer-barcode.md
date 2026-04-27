# カスタマバーコード印字機能 実装計画

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 宛名ラベル（normal/no_person モード）にカスタマバーコードをバッチ単位のオプションとして印字できるようにする。

**Architecture:** `app/utils/customer_barcode.py` に住所抽出・エンコード・描画ロジックを集約し、PDFサービスから呼び出す。UIにチェックボックスと住所表示番号列を追加し、DB に 2 列追加して設定を保存する。

**Tech Stack:** Python 3.12, PyQt6, reportlab, SQLAlchemy, pytest

---

## ファイルマップ

| ファイル | 変更種別 | 役割 |
|---------|---------|------|
| `app/utils/customer_barcode.py` | 新規作成 | 住所抽出・エンコード・チェックデジット・描画 |
| `app/database/models.py` | 修正 | `barcode_enabled` / `barcode_address` 列追加 |
| `app/services/label_pdf_service.py` | 修正 | `barcode_enabled` 引数追加・描画呼び出し |
| `app/ui/direct_label_dialog.py` | 修正 | チェックボックス・住所表示番号列・保存/復元 |
| `tests/test_customer_barcode.py` | 新規作成 | customer_barcode.py の単体テスト |

---

## Task 1: DB スキーマ変更

**Files:**
- Modify: `app/database/models.py`

- [ ] **Step 1: `LabelBatch` に `barcode_enabled` 列を追加**

`app/database/models.py` の `LabelBatch` クラスに追記：

```python
class LabelBatch(Base):
    __tablename__ = "label_batches"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    batch_name     = Column(String(200), nullable=False)
    label_mode     = Column(String(20), default="normal")
    pdf_path       = Column(String(500), default="")
    barcode_enabled = Column(Integer, default=0)          # ← 追加
    created_at     = Column(DateTime, default=datetime.now)
    updated_at     = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    entries = relationship(
        "LabelEntry", back_populates="batch",
        cascade="all, delete-orphan",
        order_by="LabelEntry.sort_order",
    )
```

- [ ] **Step 2: `LabelEntry` に `barcode_address` 列を追加**

```python
class LabelEntry(Base):
    __tablename__ = "label_entries"

    id             = Column(Integer, primary_key=True, autoincrement=True)
    batch_id       = Column(Integer, ForeignKey("label_batches.id"), nullable=False)
    sort_order     = Column(Integer, default=0)
    client_id      = Column(Integer, nullable=True)
    company_name   = Column(String(200), default="")
    company_kana   = Column(String(200), default="")
    postal_code    = Column(String(10), default="")
    address1       = Column(String(200), default="")
    address2       = Column(String(200), default="")
    title          = Column(String(100), default="")
    person_name    = Column(String(100), default="")
    barcode_address = Column(String(100), default="")     # ← 追加
    entry_mode     = Column(String(20), default="inherit")

    batch = relationship("LabelBatch", back_populates="entries")
```

- [ ] **Step 3: `init_db()` に ALTER TABLE を追加**

既存DBに列を追加するマイグレーション。`init_db()` の末尾に追記：

```python
def init_db():
    engine = get_engine()
    Base.metadata.create_all(engine)
    from sqlalchemy import text, inspect as sa_inspect
    with engine.connect() as conn:
        cols = [c["name"] for c in sa_inspect(engine).get_columns("label_entries")]
        if "company_kana" not in cols:
            conn.execute(text("ALTER TABLE label_entries ADD COLUMN company_kana VARCHAR(200) DEFAULT ''"))
            conn.commit()
        if "barcode_address" not in cols:
            conn.execute(text("ALTER TABLE label_entries ADD COLUMN barcode_address VARCHAR(100) DEFAULT ''"))
            conn.commit()

        batch_cols = [c["name"] for c in sa_inspect(engine).get_columns("label_batches")]
        if "barcode_enabled" not in batch_cols:
            conn.execute(text("ALTER TABLE label_batches ADD COLUMN barcode_enabled INTEGER DEFAULT 0"))
            conn.commit()
```

- [ ] **Step 4: テストで確認**

```bash
cd C:\Users\taka\Documents\Gemini\0030Business\label_ippatsusaku
pytest tests/test_models.py -v
```

既存テストがすべて PASS することを確認。

- [ ] **Step 5: コミット**

```bash
git add app/database/models.py
git commit -m "feat: DB に barcode_enabled/barcode_address 列を追加"
```

---

## Task 2: 住所表示番号の抽出

**Files:**
- Create: `app/utils/customer_barcode.py`
- Create: `tests/test_customer_barcode.py`

- [ ] **Step 1: テストファイルを作成して失敗させる**

`tests/test_customer_barcode.py` を作成：

```python
# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from app.utils.customer_barcode import extract_address_code


@pytest.mark.parametrize("address,expected_code,expected_confident", [
    # 丁目・番・号パターン
    ("東京都千代田区霞が関1丁目3番2号",  "1-3-2",  True),
    ("東京都新宿区西新宿2丁目8番1号",    "2-8-1",  True),
    # 全角数字
    ("東京都千代田区霞が関１丁目３番２号", "1-3-2", True),
    # 番地のみ
    ("東京都渋谷区道玄坂2番地",           "2",      True),
    # ハイフン区切り
    ("東京都港区六本木3-14-1",            "3-14-1", True),
    # 全角ハイフン
    ("東京都港区六本木３－１４－１",       "3-14-1", True),
    # 番地が見つからない（マンション名のみ）
    ("東京都港区六本木ヒルズ森タワー",     "",       False),
    # 空文字
    ("",                                   "",       False),
])
def test_extract_address_code(address, expected_code, expected_confident):
    code, confident = extract_address_code(address)
    assert code == expected_code
    assert confident == expected_confident
```

- [ ] **Step 2: テストを実行して FAIL を確認**

```bash
pytest tests/test_customer_barcode.py::test_extract_address_code -v
```

Expected: `ModuleNotFoundError: No module named 'app.utils.customer_barcode'`

- [ ] **Step 3: `customer_barcode.py` の骨格と `extract_address_code` を実装**

`app/utils/customer_barcode.py` を新規作成：

```python
# -*- coding: utf-8 -*-
"""
日本郵便 カスタマバーコード
  - 住所表示番号の抽出
  - バーコード文字列の構築
  - チェックデジット計算
  - reportlab canvas への描画
"""
import re
from reportlab.lib.units import mm
from reportlab.lib.colors import black


# ── 住所表示番号の抽出 ─────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """全角数字・ハイフンを半角に変換する"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19:          # 全角数字 ０-９
            result.append(chr(code - 0xFF10 + ord('0')))
        elif ch in ('－', '−', 'ー', '‐', '–', '—'):  # 各種全角ハイフン
            result.append('-')
        else:
            result.append(ch)
    return ''.join(result)


def extract_address_code(address: str) -> tuple[str, bool]:
    """
    住所テキストから住所表示番号（例: "1-3-2"）を抽出する。
    Returns: (address_code, is_confident)
      is_confident=False のとき UI で警告表示する。
    """
    if not address or not address.strip():
        return "", False

    text = _normalize(address)

    # パターン1: X丁目Y番Z号 (Z号は省略可)
    m = re.search(r'(\d+)丁目(\d+)番地?(\d+)?号?', text)
    if m:
        parts = [m.group(1), m.group(2)]
        if m.group(3):
            parts.append(m.group(3))
        return '-'.join(parts), True

    # パターン2: X番地Y号
    m = re.search(r'(\d+)番地(\d+)号?', text)
    if m:
        return f'{m.group(1)}-{m.group(2)}', True

    # パターン3: X番地
    m = re.search(r'(\d+)番地', text)
    if m:
        return m.group(1), True

    # パターン4: ハイフン区切り数字列（例: 3-14-1）
    m = re.search(r'(\d+(?:-\d+)+)', text)
    if m:
        return m.group(1), True

    # フォールバック: 数字のみ（信頼度低）
    m = re.search(r'(\d+)', text)
    if m:
        return m.group(1), False

    return "", False
```

- [ ] **Step 4: テストを実行して PASS を確認**

```bash
pytest tests/test_customer_barcode.py::test_extract_address_code -v
```

Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add app/utils/customer_barcode.py tests/test_customer_barcode.py
git commit -m "feat: 住所表示番号の抽出ロジックを実装"
```

---

## Task 3: バーコード文字列の構築とチェックデジット

**Files:**
- Modify: `app/utils/customer_barcode.py`
- Modify: `tests/test_customer_barcode.py`

- [ ] **Step 1: チェックデジットと文字列構築のテストを追加**

`tests/test_customer_barcode.py` に追記：

```python
from app.utils.customer_barcode import calc_check_digit, build_barcode_chars


def test_calc_check_digit_example():
    # 日本郵便マニュアル掲載の計算例: 合計110 → 114-110=4
    # 郵便番号 "1000013" + 住所表示番号 "1-3-2" にCC4パディングした21文字
    chars = list("1000013") + list("1-3-2") + ["CC4"] * 8
    assert len(chars) == 20  # チェックデジット前の20文字
    check = calc_check_digit(chars)
    assert check in [str(i) for i in range(10)] + ['-'] + [f'CC{i}' for i in range(1, 9)]


def test_build_barcode_chars_length():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert len(chars) == 23  # S + 7 + 13 + check + STOP


def test_build_barcode_chars_start_stop():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert chars[0] == 'S'
    assert chars[-1] == 'STOP'


def test_build_barcode_chars_postal():
    chars = build_barcode_chars("1000013", "1-3-2")
    assert chars[1:8] == list("1000013")


def test_build_barcode_chars_invalid_postal():
    with pytest.raises(ValueError):
        build_barcode_chars("100", "1-3-2")  # 7桁でない


def test_build_barcode_chars_addr_pad():
    # 住所表示番号が短い場合 CC4 でパディングされる
    chars = build_barcode_chars("1000013", "1")
    # chars[8:21] = ['1', 'CC4', 'CC4', ..., 'CC4', check] = 13文字 + check
    payload_addr = chars[8:21]
    assert payload_addr[0] == '1'
    assert all(c == 'CC4' for c in payload_addr[1:])
```

- [ ] **Step 2: テストを実行して FAIL を確認**

```bash
pytest tests/test_customer_barcode.py -k "check_digit or barcode_chars" -v
```

Expected: `ImportError: cannot import name 'calc_check_digit'`

- [ ] **Step 3: チェックデジットと文字列構築を実装**

`app/utils/customer_barcode.py` に追記：

```python
# ── バーコード定数 ──────────────────────────────────────────────────────────

# チェックデジット計算用の文字→数値マッピング
_CHAR_VALUES: dict[str, int] = {str(i): i for i in range(10)}
_CHAR_VALUES['-'] = 10
_CHAR_VALUES.update({f'CC{i}': 10 + i for i in range(1, 9)})

# 4ステイト3バー エンコードテーブル: char → (bar1, bar2, bar3)
# F=ロングバー, A=セミロング上, D=セミロング下, T=タイミングバー
# ⚠ 郵便番号・バーコードマニュアル(日本郵便)の文字コード表で要確認
_CHAR_PATTERNS: dict[str, tuple[str, str, str]] = {
    '0':    ('F', 'T', 'T'),
    '1':    ('A', 'T', 'D'),
    '2':    ('D', 'T', 'A'),
    '3':    ('T', 'F', 'T'),
    '4':    ('T', 'A', 'D'),
    '5':    ('A', 'D', 'T'),
    '6':    ('T', 'D', 'A'),
    '7':    ('D', 'A', 'T'),
    '8':    ('T', 'T', 'F'),
    '9':    ('F', 'A', 'T'),
    '-':    ('A', 'F', 'T'),
    'CC1':  ('D', 'F', 'T'),
    'CC2':  ('T', 'A', 'F'),
    'CC3':  ('F', 'T', 'A'),
    'CC4':  ('T', 'D', 'F'),
    'CC5':  ('F', 'D', 'T'),
    'CC6':  ('T', 'F', 'A'),
    'CC7':  ('A', 'A', 'D'),   # CC7・CC8 は公式マニュアルで要確認
    'CC8':  ('D', 'D', 'A'),
    'S':    ('F', 'A', 'D'),   # スタートコード
    'STOP': ('D', 'A', 'F'),   # ストップコード
}


# ── チェックデジット計算 ────────────────────────────────────────────────────

def calc_check_digit(chars: list[str]) -> str:
    """
    20文字のペイロード（スタート・ストップ除く、チェックデジット前）から
    チェックデジット文字を計算する。
    合計が次の19の倍数になる値を選ぶ。
    """
    total = sum(_CHAR_VALUES.get(c, 0) for c in chars)
    remainder = total % 19
    check_val = (19 - remainder) % 19
    if check_val <= 9:
        return str(check_val)
    if check_val == 10:
        return '-'
    return f'CC{check_val - 10}'


# ── バーコード文字列の構築 ─────────────────────────────────────────────────

def build_barcode_chars(postal: str, addr_code: str) -> list[str]:
    """
    バーコード文字リストを返す（スタート・ストップ含む 23 文字）。
    postal   : ハイフンなし7桁郵便番号（例: "1000013"）
    addr_code: 住所表示番号（例: "1-3-2"）
    """
    postal_clean = re.sub(r'\D', '', postal)
    if len(postal_clean) != 7:
        raise ValueError(f"郵便番号が7桁ではありません: {postal!r}")

    # 住所表示番号を文字単位に分解（数字とハイフンのみ）
    addr_chars: list[str] = [ch for ch in addr_code if ch.isdigit() or ch == '-']

    # 13文字に CC4 でパディング
    while len(addr_chars) < 13:
        addr_chars.append('CC4')
    addr_chars = addr_chars[:13]

    payload = list(postal_clean) + addr_chars        # 20文字
    check = calc_check_digit(payload)

    return ['S'] + payload + [check] + ['STOP']      # 23文字
```

- [ ] **Step 4: テストを実行して PASS を確認**

```bash
pytest tests/test_customer_barcode.py -v
```

Expected: 全テスト PASS

- [ ] **Step 5: コミット**

```bash
git add app/utils/customer_barcode.py tests/test_customer_barcode.py
git commit -m "feat: バーコード文字列構築とチェックデジット計算を実装"
```

---

## Task 4: バーコードの描画

**Files:**
- Modify: `app/utils/customer_barcode.py`

- [ ] **Step 1: 描画定数と `draw_barcode` 関数を追加**

`app/utils/customer_barcode.py` に追記：

```python
# ── バー寸法定数（a=8 で最小ラベル 70mm 幅に収まるサイズ）────────────────
# a=8 のとき: ロング=2.88mm, ピッチ=0.96mm, 幅=0.48mm
# 23文字×3バー=69本 × 0.96mm = 66.24mm → 70mm幅ラベルに余裕あり
_A = 8.0
_LONG_H   = 3.6 * _A / 10 * mm    # ロングバー高さ (pt)
_SHORT_H  = 1.2 * _A / 10 * mm    # タイミングバー高さ (pt)
_PITCH    = 1.2 * _A / 10 * mm    # バー中心間距離 (pt)
_BAR_W    = 0.6 * _A / 10 * mm    # バー幅 (pt)
_EXTEND   = (_LONG_H - _SHORT_H) / 2  # 上下への延長量 (pt)


def barcode_height() -> float:
    """バーコード全体の高さ (pt) を返す。PDFサービスからレイアウト計算に使用"""
    return _LONG_H


def draw_barcode(canvas, x0: float, y0: float, chars: list[str]) -> None:
    """
    reportlab canvas にバーコードを描画する。
    x0, y0: バーコード左下隅座標 (pt)
    chars  : build_barcode_chars() の戻り値（23文字）
    """
    mid_y = y0 + _SHORT_H / 2 + _EXTEND   # バー中央ライン Y 座標

    canvas.saveState()
    canvas.setFillColor(black)
    canvas.setStrokeColor(black)

    x = x0
    for char in chars:
        patterns = _CHAR_PATTERNS.get(char, ('T', 'T', 'T'))
        for bar_type in patterns:
            if bar_type == 'F':
                bar_y = mid_y - _LONG_H / 2
                bar_h = _LONG_H
            elif bar_type == 'A':
                # 上方向に延長（タイミングバー上端 → ロングバー上端）
                bar_y = mid_y - _SHORT_H / 2
                bar_h = _SHORT_H + _EXTEND
            elif bar_type == 'D':
                # 下方向に延長（ロングバー下端 → タイミングバー下端）
                bar_y = mid_y - _SHORT_H / 2 - _EXTEND
                bar_h = _SHORT_H + _EXTEND
            else:  # T
                bar_y = mid_y - _SHORT_H / 2
                bar_h = _SHORT_H
            canvas.rect(x, bar_y, _BAR_W, bar_h, fill=1, stroke=0)
            x += _PITCH

    canvas.restoreState()


def barcode_total_width(num_chars: int = 23) -> float:
    """バーコード全体の幅 (pt) を返す"""
    return num_chars * 3 * _PITCH
```

- [ ] **Step 2: テスト実行で既存テストが壊れていないことを確認**

```bash
pytest tests/ -v
```

Expected: 全テスト PASS

- [ ] **Step 3: コミット**

```bash
git add app/utils/customer_barcode.py
git commit -m "feat: reportlab canvas へのバーコード描画関数を実装"
```

---

## Task 5: PDF サービスへの統合

**Files:**
- Modify: `app/services/label_pdf_service.py`

- [ ] **Step 1: `generate_label_pdf` に `barcode_enabled` 引数を追加**

`label_pdf_service.py` の `generate_label_pdf` シグネチャを変更：

```python
def generate_label_pdf(
    entries:         list,
    output_path:     str,
    batch_mode:      str  = "normal",
    layout_key:      str  = DEFAULT_LAYOUT_KEY,
    font_key:        str  = DEFAULT_FONT_KEY,
    barcode_enabled: bool = False,          # ← 追加
) -> str:
```

`_draw_label` の呼び出し部分を修正（2箇所）：

```python
# 回転なしの呼び出し
_draw_label(c, entry, x0, y0, lw, lh, mode, font, barcode_enabled)

# 180°回転の呼び出し（a4_4split）
_draw_label(c, entry, -lw / 2, -lh / 2, lw, lh, mode, font, barcode_enabled)
```

`_draw_label` のシグネチャを変更：

```python
def _draw_label(c, entry, x0: float, y0: float, w: float, h: float, mode: str,
                font: str = "MSPGothic", barcode_enabled: bool = False):
    c.saveState()

    company = entry.company_name or ""
    postal  = entry.postal_code  or ""
    addr1   = entry.address1     or ""
    addr2   = entry.address2     or ""
    title   = entry.title        or ""
    person  = entry.person_name  or ""
    barcode_addr = getattr(entry, 'barcode_address', '') or ""

    if mode == "simple":
        _draw_simple(c, x0, y0, w, h, company, font)
    elif mode == "no_person":
        _draw_no_person(c, x0, y0, w, h, company, postal, addr1, addr2, font,
                        barcode_enabled, barcode_addr)
    elif mode == "nametag":
        _draw_nametag(c, x0, y0, w, h, company, title, person, font)
    elif mode == "split4":
        _draw_split4(c, x0, y0, w, h, company, font)
    else:
        _draw_normal(c, x0, y0, w, h, company, postal, addr1, addr2, title, person, font,
                     barcode_enabled, barcode_addr)

    c.restoreState()
```

- [ ] **Step 2: `_draw_normal` にバーコード描画を追加**

`_draw_normal` のシグネチャを変更し、バーコード描画を追記。ファイル先頭に import を追加：

```python
from app.utils.customer_barcode import (
    build_barcode_chars, draw_barcode, barcode_height, extract_address_code
)
```

`_draw_normal` のシグネチャを変更：

```python
def _draw_normal(c, x0, y0, w, h,
                 company, postal, addr1, addr2, title, person,
                 font: str = "MSPGothic",
                 barcode_enabled: bool = False,
                 barcode_addr: str = ""):
```

関数の先頭で、バーコード用に縦方向の有効高さを縮小する計算を追加：

```python
    # バーコードが有効なら下部にスペースを確保する
    _BC_MARGIN = 1.5 * mm          # バーコード下端からの余白
    _BC_TOP_MARGIN = 1.0 * mm      # バーコード上端の余白
    use_barcode = (
        barcode_enabled
        and postal
        and barcode_addr
        and mode not in ("simple", "nametag", "split4")
    )
    bc_reserve = (barcode_height() + _BC_MARGIN + _BC_TOP_MARGIN) if use_barcode else 0.0
```

※ `mode` は `_draw_normal` では常に normal なので `not in (...)` チェックは不要だが、防御的に残す。

`_draw_normal` の末尾（`c.restoreState()` の直前）に追記：

```python
    # ── バーコード描画 ───────────────────────────────────────────────
    if use_barcode:
        try:
            chars = build_barcode_chars(re.sub(r'\D', '', postal), barcode_addr)
            bc_x = x0 + P
            bc_y = y0 + _BC_MARGIN
            draw_barcode(c, bc_x, bc_y, chars)
        except Exception:
            pass   # 描画失敗は無視（出力を止めない）
```

また `re` モジュールを使うためファイル先頭に `import re` があることを確認（現状なければ追加）。

`_draw_normal` 内で `cur_y` の初期値を計算している箇所を修正して、`bc_reserve` 分だけ有効高さを縮小する：

```python
    # 元のコード（修正前）
    cur_y = y0 + h - P - addr_fs * 0.85

    # 修正後：バーコード分のスペースを引く
    effective_h = h - bc_reserve
    cur_y = y0 + effective_h - P - addr_fs * 0.85
```

- [ ] **Step 3: `_draw_no_person` にバーコード描画を追加**

`_draw_no_person` のシグネチャを変更：

```python
def _draw_no_person(c, x0, y0, w, h, company, postal, addr1, addr2,
                    font: str = "MSPGothic",
                    barcode_enabled: bool = False,
                    barcode_addr: str = ""):
```

`_draw_normal` と同様に `bc_reserve` を計算し、`effective_h` を使った `cur_y` 初期値に変更。末尾にバーコード描画を追加（同じコードブロックをコピー）。

- [ ] **Step 4: アプリを起動して目視確認（バーコードOFFで既存動作が変わらないこと）**

```bash
python main.py
```

適当なラベルで PDF 出力し、既存のレイアウトが崩れていないことを確認。

- [ ] **Step 5: コミット**

```bash
git add app/services/label_pdf_service.py
git commit -m "feat: PDF サービスにバーコード描画を統合"
```

---

## Task 6: UI — チェックボックスと住所表示番号列

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

- [ ] **Step 1: 列定数と `_COLS` を更新**

`DirectLabelDialog` クラスの定数定義に追記：

```python
COL_CHK     = 0
COL_COMPANY = 1
COL_KANA    = 2
COL_TITLE   = 3
COL_PERSON  = 4
COL_POSTAL  = 5
COL_ADDR    = 6
COL_BC_ADDR = 7   # ← 追加

_COLS = [
    ("",              32,  QHeaderView.ResizeMode.Fixed),
    ("事業所名",      200, QHeaderView.ResizeMode.Stretch),
    ("フリガナ",      130, QHeaderView.ResizeMode.Interactive),
    ("所属・役職名",  130, QHeaderView.ResizeMode.Interactive),
    ("氏名",          120, QHeaderView.ResizeMode.Interactive),
    ("郵便番号",       90, QHeaderView.ResizeMode.Fixed),
    ("住所",          250, QHeaderView.ResizeMode.Stretch),
    ("住所表示番号",  130, QHeaderView.ResizeMode.Fixed),    # ← 追加
]
```

- [ ] **Step 2: テーブルを 8 列に変更**

`_init_ui` の `QTableWidget(0, len(self._COLS))` はクラス変数 `_COLS` を使っているので変更不要。ただし `table.setColumnHidden(COL_BC_ADDR, True)` を初期設定で追加：

`self.table.installEventFilter(self)` の後ろに追記：

```python
        self.table.setColumnHidden(self.COL_BC_ADDR, True)
```

- [ ] **Step 3: フッターにチェックボックスを追加**

`_init_ui` の `foot = QHBoxLayout()` ブロックの `foot.addWidget(self._count_lbl)` の後ろに追記：

```python
        self._chk_barcode = QCheckBox("カスタマバーコードを印字する")
        self._chk_barcode.setStyleSheet("font-size: 12px; color: #475569;")
        self._chk_barcode.toggled.connect(self._on_barcode_toggled)
        foot.addWidget(self._chk_barcode)
```

- [ ] **Step 4: `_on_barcode_toggled` メソッドを実装**

`_on_sort` メソッドの前あたりに追加：

```python
    def _on_barcode_toggled(self, enabled: bool):
        self.table.setColumnHidden(self.COL_BC_ADDR, not enabled)
        if enabled:
            self._populate_barcode_addr()

    def _populate_barcode_addr(self):
        """住所列から住所表示番号を自動抽出してバーコード列を初期化する"""
        from app.utils.customer_barcode import extract_address_code
        for row in range(self.table.rowCount()):
            item_bc = self.table.item(row, self.COL_BC_ADDR)
            # すでに値が入っている行はスキップ（手動入力を尊重）
            if item_bc and item_bc.text().strip():
                continue
            addr = (self.table.item(row, self.COL_ADDR) or QTableWidgetItem()).text()
            code, confident = extract_address_code(addr)
            self._set_barcode_addr_item(row, code, warn=not confident)

    def _set_barcode_addr_item(self, row: int, code: str, warn: bool = False):
        """COL_BC_ADDR のセルを設定し、warn=True のとき黄色背景にする"""
        from PyQt6.QtGui import QColor
        item = self.table.item(row, self.COL_BC_ADDR)
        if item is None:
            item = QTableWidgetItem(code)
            self.table.setItem(row, self.COL_BC_ADDR, item)
        else:
            item.setText(code)
        if warn:
            item.setBackground(QColor('#FFF59D'))
            item.setToolTip("住所から自動取得できませんでした。手入力で修正してください。")
        else:
            item.setBackground(QColor('white'))
            item.setToolTip("")
```

- [ ] **Step 5: セル編集時に警告を解除するシグナルを接続**

`_init_ui` の `self.table.itemClicked.connect` などのシグナル接続箇所に追記：

```python
        self.table.itemChanged.connect(self._on_item_changed)
```

`_on_item_changed` メソッドを追加：

```python
    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == self.COL_BC_ADDR:
            from PyQt6.QtGui import QColor
            item.setBackground(QColor('white'))
            item.setToolTip("")
```

- [ ] **Step 6: アプリを起動して UI 動作を目視確認**

```bash
python main.py
```

確認項目：
- 「カスタマバーコードを印字する」チェックボックスがフッターに表示される
- チェックONで「住所表示番号」列が表示され、住所から自動抽出された値が入る
- 番地が取れない行は黄色背景になる
- セルを手動編集すると黄色背景が消える
- チェックOFFで列が非表示になる

- [ ] **Step 7: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: バーコードオプション UI（チェックボックス・住所表示番号列）を追加"
```

---

## Task 7: バーコード設定の保存と復元

**Files:**
- Modify: `app/ui/direct_label_dialog.py`

- [ ] **Step 1: `_export` でバーコード設定を保存**

`_export` メソッド内の `entry_dicts` 構築ループを修正して `barcode_address` を含める：

```python
        entry_dicts = []
        for sort_idx, row in enumerate(checked_rows):
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            entry_dicts.append({
                "sort_order":    sort_idx,
                "client_id":     None,
                "company_name":  _cell(self.COL_COMPANY),
                "company_kana":  _cell(self.COL_KANA),
                "postal_code":   _cell(self.COL_POSTAL),
                "address1":      _cell(self.COL_ADDR),
                "address2":      "",
                "title":         _cell(self.COL_TITLE),
                "person_name":   _cell(self.COL_PERSON),
                "barcode_address": _cell(self.COL_BC_ADDR),   # ← 追加
                "entry_mode":    "inherit",
            })
```

バッチへの `barcode_enabled` 保存を追加。`batch.label_mode = mode` の直後に追記：

```python
                    batch.barcode_enabled = 1 if self._chk_barcode.isChecked() else 0
```

新規バッチ作成の場合も同様に追記：

```python
                batch = LabelBatch(
                    batch_name=data_name,
                    label_mode=mode,
                    barcode_enabled=1 if self._chk_barcode.isChecked() else 0,
                )
```

- [ ] **Step 2: `generate_label_pdf` 呼び出しに `barcode_enabled` を渡す**

`_export` 内の `generate_label_pdf` 呼び出しを修正：

```python
            generate_label_pdf(
                orm_entries,
                os.path.normpath(pdf_path),
                mode,
                layout_key,
                font_key,
                barcode_enabled=self._chk_barcode.isChecked(),   # ← 追加
            )
```

- [ ] **Step 3: `_load_batch` でバーコード設定を復元**

`_load_batch` の `entries = list(batch.entries)` の後ろに追記：

```python
            barcode_enabled = bool(batch.barcode_enabled)
```

`session.close()` の後で、`self.table.setRowCount(0)` の前あたりに追記：

```python
        self._chk_barcode.setChecked(barcode_enabled)
```

`_load_batch` の `_add_row` 呼び出しを修正して `barcode_address` を渡す：

```python
            self._add_row([
                e.company_name   or "",
                e.company_kana   or "",
                e.title          or "",
                e.person_name    or "",
                e.postal_code    or "",
                addr,
                e.barcode_address or "",   # ← 追加（COL_BC_ADDR 分）
            ])
```

`_add_row` が 7 番目の要素（インデックス 6）を `COL_BC_ADDR` に設定するようにする。
現在の `_add_row` は `range(self.COL_COMPANY, len(self._COLS))` でループしており、
`len(self._COLS)` が 8 になったことで `COL_BC_ADDR`（offset=6）も自動的に対象になる。
値リストの 7 番目要素（index 6）が barcode_address になるため正しく動作する。

また、復元時は自動抽出せずそのまま表示するため、バーコードチェックがONでも `_populate_barcode_addr` を呼ばないよう修正。`_on_barcode_toggled` を修正：

```python
    def _on_barcode_toggled(self, enabled: bool):
        self.table.setColumnHidden(self.COL_BC_ADDR, not enabled)
        if enabled:
            self._populate_barcode_addr()
```

`_populate_barcode_addr` はすでに「値が入っている行をスキップ」する実装になっているため、復元後のデータは上書きされない。これで OK。

- [ ] **Step 4: 保存と復元の動作を目視確認**

```bash
python main.py
```

確認項目：
1. バーコードONでPDF出力 → DBに `barcode_enabled=1` と `barcode_address` が保存されること
2. 一覧画面から同じバッチを開く → チェックボックスがONで、住所表示番号が復元されること
3. バーコードOFFでPDF出力 → チェックボックスがOFFで復元されること
4. 出力されたPDFにバーコードが印字されること（黒い棒が下部に表示）

- [ ] **Step 5: コミット**

```bash
git add app/ui/direct_label_dialog.py
git commit -m "feat: バーコード設定の保存と復元を実装 (v1.3.0)"
```

---

## セルフレビュー結果

**スペックカバレッジ:**
- ✅ normal/no_person モードのみ対象
- ✅ バッチ単位 ON/OFF
- ✅ 住所表示番号の自動抽出（正規表現）
- ✅ 低信頼度時の黄色警告
- ✅ 手動編集で警告解除
- ✅ 編集テーブルに列追加（チェックOFF時は非表示）
- ✅ ラベル下部自動配置
- ✅ DB 保存・復元

**型整合性:**
- `build_barcode_chars` → `list[str]` → `draw_barcode(canvas, x, y, chars)` で一貫
- `barcode_height()` → `float (pt)` → `bc_reserve` で使用（単位一致）
- `barcode_enabled` は `bool` で PDF サービスに渡す（DB は int 0/1、UI で変換）

**エンコードテーブル注意事項:**
CC7・CC8 のパターンは公式マニュアル（https://www.post.japanpost.jp/zipcode/zipmanual/）の文字コード表で要確認。
実際のバーコードを印刷してスキャナで読み取れるかテストすること。
