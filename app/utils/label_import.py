# -*- coding: utf-8 -*-
"""
宛名ラベル用 CSV / クリップボード貼り付けのパースとマッチングロジック。

【設計方針】
  - 「貼り付け行の順序 = テーブル行の順序」という割り当ては行わない。
  - 「企業ID」または「企業名」をキーにしてマッチングする。
  - マッチしなかった行は必ず呼び出し元に返し、ユーザーへ明示する。
"""
import csv
import io
import unicodedata
from dataclasses import dataclass, field
from typing import Optional


# ──────────────────────────────────────────────
#  データクラス
# ──────────────────────────────────────────────

@dataclass
class DirectRow:
    """直接貼り付けモード用：住所を含むすべての情報を自前で持つ"""
    company_name: str = ""
    postal_code:  str = ""
    address1:     str = ""
    address2:     str = ""
    title:        str = ""
    person_name:  str = ""


@dataclass
class ImportRow:
    """1行分のインポートデータ"""
    company_name: str = ""
    client_id: Optional[int] = None
    title: str = ""
    person_name: str = ""
    raw: dict = field(default_factory=dict)


@dataclass
class MatchResult:
    """マッチ成功した組み合わせ"""
    client: object          # Client ORM オブジェクト
    import_row: ImportRow


@dataclass
class UnmatchedRow:
    """マッチ失敗した行（候補付き）"""
    import_row: ImportRow
    candidates: list = field(default_factory=list)   # 候補の Client リスト


# ──────────────────────────────────────────────
#  内部ユーティリティ
# ──────────────────────────────────────────────

def _normalize(text: str) -> str:
    """比較用正規化：NFKC → スペース除去 → 小文字化"""
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("　", "").replace(" ", "").lower()
    return text


# ──────────────────────────────────────────────
#  パーサー
# ──────────────────────────────────────────────

# 認識するヘッダーの別名セット
_COMPANY_KEYS  = {"企業名", "会社名", "company"}
_ID_KEYS       = {"企業id", "会社id", "id", "client_id"}
_TITLE_KEYS    = {"肩書", "役職", "title"}
_PERSON_KEYS   = {"氏名", "名前", "担当者", "person", "name"}


def _extract_row(row_dict: dict) -> ImportRow:
    """ヘッダー名の揺れを吸収して ImportRow を生成する"""
    # キーを正規化して検索
    norm = {_normalize(k): v for k, v in row_dict.items()}

    company = ""
    for k in _COMPANY_KEYS:
        if _normalize(k) in norm:
            company = norm[_normalize(k)].strip()
            break

    client_id = None
    for k in _ID_KEYS:
        val = norm.get(_normalize(k), "").strip()
        if val.isdigit():
            client_id = int(val)
            break

    title = ""
    for k in _TITLE_KEYS:
        if _normalize(k) in norm:
            title = norm[_normalize(k)].strip()
            break

    person = ""
    for k in _PERSON_KEYS:
        if _normalize(k) in norm:
            person = norm[_normalize(k)].strip()
            break

    return ImportRow(
        company_name=company,
        client_id=client_id,
        title=title,
        person_name=person,
        raw=dict(row_dict),
    )


def parse_clipboard_text(text: str) -> list[ImportRow]:
    """
    クリップボードからタブ区切りテキスト（Excel コピー）を解析する。

    ヘッダー行の有無を自動判定：
      - 先頭行に「企業名」「肩書」「氏名」等の語を含む → ヘッダーあり
      - それ以外 → ヘッダーなし（列順: 企業名, 肩書, 氏名 と仮定）
    """
    rows: list[ImportRow] = []
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return rows

    first_cols = [c.strip() for c in lines[0].split("\t")]
    has_header = any(
        _normalize(c) in {_normalize(k) for k in _COMPANY_KEYS | _TITLE_KEYS | _PERSON_KEYS | _ID_KEYS}
        for c in first_cols
    )

    if has_header:
        headers    = first_cols
        data_lines = lines[1:]
    else:
        # ヘッダーなし：列順を固定
        headers    = ["企業名", "肩書", "氏名"]
        data_lines = lines

    for line in data_lines:
        cols = line.split("\t")
        row_dict = {headers[i]: (cols[i].strip() if i < len(cols) else "")
                    for i in range(len(headers))}
        ir = _extract_row(row_dict)
        if ir.company_name:
            rows.append(ir)

    return rows


def parse_csv_bytes(data: bytes) -> list[ImportRow]:
    """
    CSV ファイルのバイト列を解析する。
    UTF-8 (BOM あり/なし)、Shift-JIS、CP932 の順で試みる。
    """
    text = None
    for enc in ("utf-8-sig", "utf-8", "shift-jis", "cp932"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise ValueError("CSV のエンコーディングを認識できません（UTF-8 / Shift-JIS を使用してください）")

    reader = csv.DictReader(io.StringIO(text))
    rows: list[ImportRow] = []
    for r in reader:
        ir = _extract_row(dict(r))
        if ir.company_name:
            rows.append(ir)
    return rows


# ──────────────────────────────────────────────
#  直接入力モード用パーサー
# ──────────────────────────────────────────────

# 直接入力の列名マッピング
_DIR_COMPANY  = {"企業名", "会社名", "company"}
_DIR_POSTAL   = {"郵便番号", "postal", "zip"}
_DIR_ADDR1    = {"住所", "住所1", "address", "address1"}
_DIR_ADDR2    = {"住所2", "address2"}
_DIR_TITLE    = {"肩書", "所属", "役職", "部署", "所属・役職", "title", "department"}
_DIR_PERSON   = {"氏名", "名前", "担当者", "person", "name"}

# 列数ごとのフォールバック順（ヘッダーなし時）
_FALLBACK_COLS = {
    2: ["company_name", "person_name"],
    3: ["company_name", "title", "person_name"],
    4: ["company_name", "postal_code", "address1", "person_name"],
    5: ["company_name", "postal_code", "address1", "title", "person_name"],
    6: ["company_name", "postal_code", "address1", "address2", "title", "person_name"],
}


def _extract_direct_row(row_dict: dict) -> DirectRow:
    """ヘッダー付き辞書から DirectRow を生成する"""
    norm = {_normalize(k): v for k, v in row_dict.items()}

    def _pick(keys):
        for k in keys:
            v = norm.get(_normalize(k), "")
            if v.strip():
                return v.strip()
        return ""

    return DirectRow(
        company_name=_pick(_DIR_COMPANY),
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
        postal_code =mapping.get("postal_code",  ""),
        address1    =mapping.get("address1",      ""),
        address2    =mapping.get("address2",      ""),
        title       =mapping.get("title",         ""),
        person_name =mapping.get("person_name",   ""),
    )


def parse_raw_clipboard(text: str) -> tuple[list[str], list[list[str]]]:
    """
    クリップボードのタブ区切りテキストを生の列データに変換する。

    Returns:
        (headers, data_rows)
        headers   : 列名リスト（ヘッダー行があればその値、なければ「列1」「列2」…）
        data_rows : データ行のリスト（各行は文字列リスト）
    """
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return [], []

    all_rows = [[c.strip() for c in line.split("\t")] for line in lines]
    ncols = max(len(r) for r in all_rows)

    first_cols = all_rows[0]
    all_known = {_normalize(k)
                 for ks in (_DIR_COMPANY, _DIR_POSTAL, _DIR_ADDR1, _DIR_ADDR2,
                             _DIR_TITLE, _DIR_PERSON)
                 for k in ks}
    has_header = any(_normalize(c) in all_known for c in first_cols)

    if has_header:
        headers   = first_cols + [f"列{i+1}" for i in range(len(first_cols), ncols)]
        data_rows = all_rows[1:]
    else:
        headers   = [f"列{i+1}" for i in range(ncols)]
        data_rows = all_rows

    data_rows = [row + [""] * (ncols - len(row)) for row in data_rows]
    return headers, data_rows


def parse_direct_clipboard(text: str) -> list[DirectRow]:
    """
    クリップボードのタブ区切りテキストを DirectRow リストに変換する。

    ヘッダー行の有無を自動判定し、なければ列数でフォールバック。
    """
    rows: list[DirectRow] = []
    lines = [ln for ln in text.strip().splitlines() if ln.strip()]
    if not lines:
        return rows

    first_cols = [c.strip() for c in lines[0].split("\t")]
    all_known  = {_normalize(k)
                  for ks in (_DIR_COMPANY, _DIR_POSTAL, _DIR_ADDR1, _DIR_ADDR2,
                              _DIR_TITLE, _DIR_PERSON)
                  for k in ks}
    has_header = any(_normalize(c) in all_known for c in first_cols)

    if has_header:
        # ヘッダー行あり
        headers    = first_cols
        data_lines = lines[1:]
        for line in data_lines:
            vals     = line.split("\t")
            row_dict = {headers[i]: (vals[i].strip() if i < len(vals) else "")
                        for i in range(len(headers))}
            dr = _extract_direct_row(row_dict)
            if dr.company_name:
                rows.append(dr)
    else:
        # ヘッダー行なし：列数でフォールバック
        ncols      = len(first_cols)
        field_order = _FALLBACK_COLS.get(ncols) or _FALLBACK_COLS.get(
            min(_FALLBACK_COLS.keys(), key=lambda k: abs(k - ncols))
        )
        for line in lines:
            cols = [c.strip() for c in line.split("\t")]
            dr   = _cols_to_direct_row(cols, field_order)
            if dr.company_name:
                rows.append(dr)

    return rows


def parse_direct_csv_bytes(data: bytes) -> list[DirectRow]:
    """CSV ファイルのバイト列を DirectRow リストに変換する"""
    text = None
    for enc in ("utf-8-sig", "utf-8", "shift-jis", "cp932"):
        try:
            text = data.decode(enc)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    if text is None:
        raise ValueError("CSV のエンコーディングを認識できません")

    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames:
        rows: list[DirectRow] = []
        for r in reader:
            dr = _extract_direct_row(dict(r))
            if dr.company_name:
                rows.append(dr)
        return rows

    # DictReader がヘッダーを検出できない場合はタブ区切りとして再試行
    return parse_direct_clipboard(text.replace(",", "\t"))


# ──────────────────────────────────────────────
#  マッチングロジック
# ──────────────────────────────────────────────

def match_entries(
    import_rows: list[ImportRow],
    selected_clients: list,
) -> tuple[list[MatchResult], list[UnmatchedRow]]:
    """
    インポート行と選択済み企業リストをマッチングする。

    優先順位:
      1. 企業 ID 完全一致
      2. 企業名 完全一致
      3. 正規化後の完全一致（全角スペース・大文字小文字を無視）

    マッチしなかった行は UnmatchedRow として返す。
    UnmatchedRow.candidates には正規化部分一致の候補を入れる。
    """
    id_index   = {c.id:   c for c in selected_clients}
    name_index = {c.name: c for c in selected_clients}
    norm_index = {_normalize(c.name): c for c in selected_clients}

    matched: list[MatchResult]   = []
    unmatched: list[UnmatchedRow] = []

    for row in import_rows:
        client = None

        # 1. ID マッチ
        if row.client_id is not None:
            client = id_index.get(row.client_id)

        # 2. 企業名 完全一致
        if client is None:
            client = name_index.get(row.company_name)

        # 3. 正規化後 完全一致
        if client is None:
            client = norm_index.get(_normalize(row.company_name))

        if client is not None:
            matched.append(MatchResult(client=client, import_row=row))
        else:
            # 部分一致で候補を収集（ユーザーへの提案用）
            norm_q     = _normalize(row.company_name)
            candidates = [
                c for c in selected_clients
                if norm_q in _normalize(c.name) or _normalize(c.name) in norm_q
            ]
            unmatched.append(UnmatchedRow(import_row=row, candidates=candidates))

    return matched, unmatched
