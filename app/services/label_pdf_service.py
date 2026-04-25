# -*- coding: utf-8 -*-
"""
宛名ラベル PDF 生成サービス

複数のラベルレイアウトに対応。
LABEL_LAYOUTS に仕様を追加するだけで新しいサイズを登録できる。

登録済みレイアウト:
  "a_one_28185" : A-ONE 28185  A4 3列×6行  70×42.3mm  上余白21.5mm
  "a_one_28187" : A-ONE 28187  A4 2列×6行  84×42mm    上余白22.5mm
  "a_one_51002" : A-ONE 51002  A4 2列×5行  91×55mm    上余白11mm（名札用）
  "a4_4split"   : A4 横長4分割 A4 1列×4行  210×74.25mm（プレートモード用）
"""
from dataclasses import dataclass

from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.colors import HexColor, black
from reportlab.pdfgen.canvas import Canvas
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfbase.pdfmetrics import stringWidth
import os

# ── フォント登録 ────────────────────────────────────────────────────────
_FONT_FILES = {
    "Meiryo":     ("C:/Windows/Fonts/meiryo.ttc",    0),
    "MSPGothic":  ("C:/Windows/Fonts/msgothic.ttc",  2),
    "MSPMincho":  ("C:/Windows/Fonts/msmincho.ttc",  1),
}
for _name, (_path, _idx) in _FONT_FILES.items():
    try:
        pdfmetrics.registerFont(TTFont(_name, _path, subfontIndex=_idx))
    except Exception:
        pass

# 選択可能フォント: 表示名 → 内部フォント名
FONT_OPTIONS: dict[str, str] = {
    "MSPゴシック": "MSPGothic",
    "MSP明朝":    "MSPMincho",
    "メイリオ":   "Meiryo",
}
DEFAULT_FONT_KEY = "MSPゴシック"

FONT_G = "Meiryo"   # 後方互換（簡易モード等で参照される場合に備え残す）
C_BORDER = HexColor("#CCCCCC")
C_SUB    = HexColor("#555555")


# ══════════════════════════════════════════════════════════════════════
#  レイアウト定義
# ══════════════════════════════════════════════════════════════════════

@dataclass
class LabelLayout:
    """ラベル用紙レイアウト仕様"""
    name:            str    # 表示名（UI に出す）
    cols:            int    # 列数
    rows:            int    # 行数
    label_w_mm:      float  # ラベル幅 (mm)
    label_h_mm:      float  # ラベル高 (mm)
    margin_top_mm:   float  # 上余白 (mm)
    margin_left_mm:  float  # 左余白 (mm)
    gap_h_mm:        float  # 列間ギャップ (mm) ※ 水平方向の間隔 − ラベル幅
    gap_v_mm:        float  # 行間ギャップ (mm) ※ 垂直方向の間隔 − ラベル高
    page_h_mm:       float = 297.0  # ページ高さ (mm)。ラベル用紙の実寸を指定


# ── 登録済みレイアウト ─────────────────────────────────────────────────
#
#  【追加方法】
#  LABEL_LAYOUTS に新しいキーとLabelLayoutを追加するだけ。
#  UI のコンボボックスは自動的に新しいエントリを表示する。
#
LABEL_LAYOUTS: dict[str, LabelLayout] = {
    "a_one_28185": LabelLayout(
        name           = "A-ONE 28185  (A4 / 3列×6行 / 70×42.3mm)",
        cols           = 3,
        rows           = 6,
        label_w_mm     = 70.0,
        label_h_mm     = 42.3,
        margin_top_mm  = 21.5,
        margin_left_mm = 0.0,
        gap_h_mm       = 0.0,   # 水平間隔70mm − ラベル幅70mm = 0
        gap_v_mm       = 0.0,   # 垂直間隔42.3mm − ラベル高42.3mm = 0
        page_h_mm      = 296.9, # ラベル用紙実寸（A4標準297mmより0.1mm短い）
    ),
    "a_one_28187": LabelLayout(
        name           = "A-ONE 28187  (A4 / 2列×6行 / 84×42mm)",
        cols           = 2,
        rows           = 6,
        label_w_mm     = 84.0,
        label_h_mm     = 42.0,
        margin_top_mm  = 22.5,
        margin_left_mm = 20.0,
        gap_h_mm       = 2.0,   # 水平ピッチ86mm − ラベル幅84mm = 2
        gap_v_mm       = 0.0,   # 垂直ピッチ42mm − ラベル高42mm = 0
        page_h_mm      = 296.9, # ラベル用紙実寸
    ),
    "a_one_51002": LabelLayout(
        name           = "A-ONE 51002  (A4 / 2列×5行 / 91×55mm・名札)",
        cols           = 2,
        rows           = 5,
        label_w_mm     = 91.0,
        label_h_mm     = 55.0,
        margin_top_mm  = 11.0,
        margin_left_mm = 14.0,
        gap_h_mm       = 0.0,
        gap_v_mm       = 0.0,
    ),
    "a4_4split": LabelLayout(
        name           = "A4 横長4分割  (A4 / 1列×4行 / 210×74.25mm)",
        cols           = 1,
        rows           = 4,
        label_w_mm     = 210.0,
        label_h_mm     = 74.25,
        margin_top_mm  = 0.0,
        margin_left_mm = 0.0,
        gap_h_mm       = 0.0,
        gap_v_mm       = 0.0,
    ),
}

DEFAULT_LAYOUT_KEY = "a_one_28185"


# ══════════════════════════════════════════════════════════════════════
#  座標計算ヘルパー
# ══════════════════════════════════════════════════════════════════════

def _label_wh(layout: LabelLayout) -> tuple[float, float]:
    """ラベル 1 枚のサイズ (pt) を返す"""
    return layout.label_w_mm * mm, layout.label_h_mm * mm


def _label_origin(col: int, row: int, layout: LabelLayout) -> tuple[float, float]:
    """ラベル左下隅の座標 (pt) を返す（row は上から 0 始まり）"""
    page_h = layout.page_h_mm * mm
    lw = layout.label_w_mm  * mm
    lh = layout.label_h_mm  * mm
    mt = layout.margin_top_mm  * mm
    ml = layout.margin_left_mm * mm
    gh = layout.gap_h_mm * mm
    gv = layout.gap_v_mm * mm
    x = ml + col * (lw + gh)
    y = page_h - mt - (row + 1) * lh - row * gv
    return x, y


# ══════════════════════════════════════════════════════════════════════
#  メイン関数
# ══════════════════════════════════════════════════════════════════════

def generate_label_pdf(
    entries:     list,
    output_path: str,
    batch_mode:  str = "normal",
    layout_key:  str = DEFAULT_LAYOUT_KEY,
    font_key:    str = DEFAULT_FONT_KEY,
) -> str:
    """
    entries     : LabelEntry ORM オブジェクトのリスト
    output_path : 出力先ファイルパス
    batch_mode  : バッチのデフォルトモード ("normal" | "simple")
    layout_key  : LABEL_LAYOUTS のキー
    font_key    : FONT_OPTIONS のキー
    """
    layout = LABEL_LAYOUTS.get(layout_key) or LABEL_LAYOUTS[DEFAULT_LAYOUT_KEY]
    font   = FONT_OPTIONS.get(font_key, FONT_OPTIONS[DEFAULT_FONT_KEY])
    lw, lh = _label_wh(layout)
    per_page = layout.cols * layout.rows

    parent = os.path.dirname(output_path)
    if parent:
        os.makedirs(parent, exist_ok=True)

    page_w = A4[0]   # 幅は常に A4 幅（210mm）
    page_h = layout.page_h_mm * mm
    c = Canvas(output_path, pagesize=(page_w, page_h))
    c.setTitle("宛名ラベル")

    # a4_4split: 各エントリを2スロット分（回転＋通常）に展開
    #   slot 0（row 0, 180°回転）＋ slot 1（row 1, 通常）→ 同一エントリ
    #   slot 2（row 2, 180°回転）＋ slot 3（row 3, 通常）→ 同一エントリ
    draw_entries = (
        [e for e in entries for _ in range(2)]
        if layout_key == "a4_4split" else list(entries)
    )

    slot = 0
    for entry in draw_entries:
        # ページ送り
        if slot > 0 and slot % per_page == 0:
            c.showPage()

        page_slot = slot % per_page
        col = page_slot % layout.cols
        row = page_slot // layout.cols
        x0, y0 = _label_origin(col, row, layout)

        mode = batch_mode if entry.entry_mode == "inherit" else entry.entry_mode

        # a4_4split: row 0・2（上から1・3番）を 180° 回転して印刷
        if layout_key == "a4_4split" and row % 2 == 0:
            c.saveState()
            c.translate(x0 + lw / 2, y0 + lh / 2)
            c.rotate(180)
            _draw_label(c, entry, -lw / 2, -lh / 2, lw, lh, mode, font)
            c.restoreState()
        else:
            _draw_label(c, entry, x0, y0, lw, lh, mode, font)
        slot += 1

    c.save()
    return output_path


# ══════════════════════════════════════════════════════════════════════
#  1 枚のラベルを描画
# ══════════════════════════════════════════════════════════════════════

def _fit_text(text: str, font: str, max_size: float,
              max_width: float, min_size: float = 5.5) -> float:
    size = max_size
    while size > min_size and stringWidth(text, font, size) > max_width:
        size -= 0.5
    return size


def _split_line(text: str, font: str, fs: float, max_w: float) -> tuple[str, str]:
    """max_w に収まる最長の先頭部分とその残りを返す（stringWidth で正確測定）"""
    if not text:
        return "", ""
    if stringWidth(text, font, fs) <= max_w:
        return text, ""
    lo, hi = 1, len(text)
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if stringWidth(text[:mid], font, fs) <= max_w:
            lo = mid
        else:
            hi = mid - 1
    return text[:lo], text[lo:]


def _draw_label(c, entry, x0: float, y0: float, w: float, h: float, mode: str,
                font: str = "MSPGothic"):
    c.saveState()

    company = entry.company_name or ""
    postal  = entry.postal_code  or ""
    addr1   = entry.address1     or ""
    addr2   = entry.address2     or ""
    title   = entry.title        or ""
    person  = entry.person_name  or ""

    if mode == "simple":
        _draw_simple(c, x0, y0, w, h, company, font)
    elif mode == "nametag":
        _draw_nametag(c, x0, y0, w, h, company, title, person, font)
    elif mode == "split4":
        _draw_split4(c, x0, y0, w, h, company, font)
    else:
        _draw_normal(c, x0, y0, w, h, company, postal, addr1, addr2, title, person, font)

    c.restoreState()


# ── 通常モード ──────────────────────────────────────────────────────────

def _draw_normal(c, x0, y0, w, h,
                 company, postal, addr1, addr2, title, person,
                 font: str = "MSPGothic"):
    """
    上から順に描画: 郵便番号 → 住所 → 事業所名（インデント）
                   → 所属・役職（インデント、複数行）→ 氏名 様（さらにインデント・大きめ）
    ラベルサイズに応じてフォントサイズを自動スケール。
    基準: ラベル高 53mm (generic_2x5) のサイズを 1.0 とする。
    """
    scale  = min(w / (92.5 * mm), h / (53.0 * mm))
    P      = max(2.0 * mm, 3.0 * mm * scale)    # 左右余白

    inner_w = w - 2 * P
    indent1 = P + 2.5 * mm * scale               # 事業所名・所属のインデント
    indent2 = P + 8.0 * mm * scale               # 氏名のインデント

    addr_fs     = 11.0
    co_max_fs   = 11.0
    title_fs    = 11.0
    name_max_fs = 11.0

    LH = addr_fs * 1.6                           # 行高 = フォントサイズ × 1.6

    cur_y = y0 + h - P - addr_fs * 0.85

    # ── 郵便番号 ─────────────────────────────────────────────────────
    c.setFont(font, addr_fs)
    c.setFillColor(C_SUB)
    if postal:
        c.drawString(x0 + P, cur_y, f"〒{postal}")
        cur_y -= LH * 0.95

    # ── 住所 ─────────────────────────────────────────────────────────
    if addr1:
        a = addr1
        while a:
            line, a = _split_line(a, font, addr_fs, inner_w)
            c.drawString(x0 + P, cur_y, line)
            cur_y -= LH * 0.95
    if addr2:
        c.drawString(x0 + P, cur_y, addr2)
        cur_y -= LH * 0.95

    # 住所と事業所名の間に半行分の空白
    if postal or addr1 or addr2:
        cur_y -= LH * 0.4

    # ── 事業所名（企業名）────────────────────────────────────────────
    # 8pt未満になる場合は折り返し、それ以外は自動縮小
    if company:
        co_avail = inner_w - (indent1 - P)
        co_fs    = _fit_text(company, font, co_max_fs, co_avail, min_size=8.0)
        c.setFont(font, co_fs)
        c.setFillColor(black)
        if co_fs < 8.0 or stringWidth(company, font, co_fs) > co_avail:
            co_fs = 8.0
            c.setFont(font, co_fs)
            co_text = company
            while co_text:
                line, co_text = _split_line(co_text, font, co_fs, co_avail)
                c.drawString(x0 + indent1, cur_y, line)
                cur_y -= LH * 0.9
        else:
            c.drawString(x0 + indent1, cur_y, company)
            cur_y -= LH * 1.05

    # ── 所属・役職（1行・自動縮小）──────────────────────────────────
    if title:
        title_line = title.replace("\n", "　").strip()
        t_fs = _fit_text(title_line, font, title_fs, inner_w - (indent1 - P), min_size=6.0)
        c.setFont(font, t_fs)
        c.setFillColor(black)
        c.drawString(x0 + indent1, cur_y, title_line)
        cur_y -= LH * 0.95

    # ── 氏名 + 様（役職あり: 少し余白、役職なし: 詰めて配置）──────────
    if person:
        name_line = f"{person}　様"
        name_fs   = _fit_text(name_line, font, name_max_fs, inner_w - (indent2 - P))
        name_y    = max(y0 + P * 0.8, cur_y)
        c.setFont(font, name_fs)
        c.setFillColor(black)
        c.drawString(x0 + indent2, name_y, name_line)
    else:
        gochu_fs = max(7.0, 10.0 * scale)
        name_y   = max(y0 + P * 0.8, cur_y)
        c.setFont(font, gochu_fs)
        c.setFillColor(black)
        gw = stringWidth("御中", font, gochu_fs)
        c.drawString(x0 + w - P - gw, name_y, "御中")


# ── 名札モード ──────────────────────────────────────────────────────────

def _draw_nametag(c, x0, y0, w, h, company, title, person, font: str = "MSPGothic"):
    """
    名札レイアウト（A-ONE 51002 等 91×55mm 向け）
    上から順に: 事業所名(18pt) → 所属・役職(14pt) → 氏名(18pt)
    """
    P = 4.0 * mm
    inner_w = w - 2 * P

    co_fs = 18.0
    ti_fs = 16.0
    na_fs = 20.0

    cur_y = y0 + h - P - co_fs * 0.85

    if company:
        c.setFillColor(black)
        if "\n" in company:
            # 手動改行：各行を個別にフィット
            for line in company.split("\n"):
                if not line:
                    cur_y -= co_fs * 0.6
                    continue
                fs = _fit_text(line, font, co_fs, inner_w, min_size=ti_fs)
                c.setFont(font, fs)
                c.drawString(x0 + P, cur_y, line)
                cur_y -= fs * 1.4
        else:
            # 自動折り返し（14pt 未満になるなら 14pt で折り返し）
            fs = _fit_text(company, font, co_fs, inner_w, min_size=ti_fs)
            if stringWidth(company, font, fs) <= inner_w:
                c.setFont(font, fs)
                c.drawString(x0 + P, cur_y, company)
                cur_y -= fs * 1.4
            else:
                c.setFont(font, ti_fs)
                text = company
                while text:
                    line, text = _split_line(text, font, ti_fs, inner_w)
                    c.drawString(x0 + P, cur_y, line)
                    cur_y -= ti_fs * 1.4
    else:
        cur_y -= co_fs * 1.4

    if title:
        fs = _fit_text(title, font, ti_fs, inner_w)
        c.setFont(font, fs)
        c.setFillColor(black)
        indent = stringWidth("　", font, fs)
        c.drawString(x0 + P + indent, cur_y, title)
    cur_y -= ti_fs * 1.4 + 4.0   # 役職と氏名の間に 4pt の余白

    if person:
        fs = _fit_text(person, font, na_fs, inner_w)
        c.setFont(font, fs)
        c.setFillColor(black)
        nw = stringWidth(person, font, fs)
        c.drawString(x0 + (w - nw) / 2, cur_y, person)


# ── 簡易モード ──────────────────────────────────────────────────────────

def _draw_simple(c, x0, y0, w, h, company, font: str = "MSPGothic"):
    P       = 5.0 * mm          # 左右余白 5mm 固定
    inner_w = w - 2 * P
    fs      = 16.0              # 基準フォントサイズ 16pt

    co_fs = _fit_text(company, font, fs, inner_w)
    co_y  = y0 + h / 2 + fs * 0.75

    c.setFont(font, co_fs)
    c.setFillColor(black)
    c.drawString(x0 + P, co_y, company)

    go_fs = 14.0
    gw    = stringWidth("御中", font, go_fs)
    go_y  = y0 + h / 2 - fs * 0.75

    c.setFont(font, go_fs)
    c.setFillColor(black)
    c.drawString(x0 + w - P - gw, go_y, "御中")


# ── プレートモード ──────────────────────────────────────────────────────

def _draw_split4(c, x0, y0, w, h, company, font: str = "MSPGothic"):
    """
    プレートモード：ユーザーが入力した改行（\\n）で区切られた各行を
    均等割付・上下中央で描画。自動折り返しなし。
    row 0・2 の 180° 回転は generate_label_pdf 側で処理する。
    """
    if not company:
        return

    P      = 8.0 * mm
    inner_w = w - 2 * P
    inner_h = h - 2 * P

    # ユーザーの手動改行で分割（空行は除外）
    lines = [ln for ln in company.split("\n") if ln]
    if not lines:
        return

    n = len(lines)
    # 複数行のときは行間を詰める（行間 = フォントサイズの8%）、1行は標準
    LINE_H = 1.08 if n > 1 else 1.4

    # フォントサイズ：横幅制約と縦高さ制約の両方を満たす最大値
    widest  = max(lines, key=lambda ln: stringWidth(ln, font, 150.0))
    fs_w    = _fit_text(widest, font, 150.0, inner_w, min_size=8.0)
    fs_h    = inner_h / (n * LINE_H)          # n行が縦に収まる上限
    fs      = min(fs_w, fs_h)
    line_h  = fs * LINE_H

    # 上下中央：テキストブロック全体の視覚中心をラベル中央に合わせる
    start_y = y0 + h / 2 + (n - 1) * line_h / 2 - fs * 0.3

    bold = n > 1
    c.setFont(font, fs)
    c.setFillColor(black)
    if bold:
        c.setStrokeColor(black)
        c.setLineWidth(fs * 0.02)   # 縁取り幅でボールド感を出す

    for i, line in enumerate(lines):
        cur_y = start_y - i * line_h
        mode  = 2 if bold else 0    # 2 = fill + stroke

        if len(line) == 2:
            # 2文字：前後に半角スペースの1/4幅を余白として均等割付
            pad = stringWidth(" ", font, fs) / 4
            cw  = [stringWidth(ch, font, fs) for ch in line]
            gap = inner_w - 2 * pad - sum(cw)
            x   = x0 + P + pad
            for j, ch in enumerate(line):
                c.drawString(x, cur_y, ch, mode=mode)
                x += cw[j] + (gap if j == 0 else 0)
        else:
            nchars = len(line)
            line_w = stringWidth(line, font, fs)
            gap    = (inner_w - line_w) / (nchars - 1) if nchars > 1 else 0
            x      = x0 + P
            for ch in line:
                c.drawString(x, cur_y, ch, mode=mode)
                x += stringWidth(ch, font, fs) + gap
