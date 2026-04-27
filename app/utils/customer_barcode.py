# -*- coding: utf-8 -*-
"""
日本郵便 カスタマバーコード（4ステイト3バー）

  - 住所表示番号の抽出
  - バーコード文字列の構築（スタート＋郵便番号7桁＋住所表示番号13桁＋チェックデジット＋ストップ）
  - チェックデジット計算（合計が19の倍数）
  - reportlab canvas への描画

仕様参照: https://www.post.japanpost.jp/zipcode/zipmanual/
"""
import re
from reportlab.lib.units import mm
from reportlab.lib.colors import black


# ══════════════════════════════════════════════════════════════════════
#  住所表示番号の抽出
# ══════════════════════════════════════════════════════════════════════

def _normalize(text: str) -> str:
    """全角数字・各種ハイフンを半角に変換する"""
    result = []
    for ch in text:
        code = ord(ch)
        if 0xFF10 <= code <= 0xFF19:
            result.append(chr(code - 0xFF10 + ord('0')))
        elif ch in ('－', '−', 'ー', '‐', '–', '—'):
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


# ══════════════════════════════════════════════════════════════════════
#  バーコード定数
# ══════════════════════════════════════════════════════════════════════

# チェックデジット計算用の文字→数値マッピング
_CHAR_VALUES: dict[str, int] = {str(i): i for i in range(10)}
_CHAR_VALUES['-'] = 10
_CHAR_VALUES.update({f'CC{i}': 10 + i for i in range(1, 9)})

# 4ステイト3バー エンコードテーブル: char → (bar1, bar2, bar3)
# F=ロングバー（上下両方）, A=セミロング上, D=セミロング下, T=タイミングバー
# ⚠ 郵便番号・バーコードマニュアル（日本郵便）の文字コード表で CC7・CC8 を要確認
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
    'CC7':  ('A', 'A', 'D'),
    'CC8':  ('D', 'D', 'A'),
    'S':    ('F', 'A', 'D'),   # スタートコード
    'STOP': ('D', 'A', 'F'),   # ストップコード
}


# ══════════════════════════════════════════════════════════════════════
#  チェックデジット計算
# ══════════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════════
#  バーコード文字列の構築
# ══════════════════════════════════════════════════════════════════════

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

    payload = list(postal_clean) + addr_chars   # 20文字
    check = calc_check_digit(payload)

    return ['S'] + payload + [check] + ['STOP']  # 23文字


# ══════════════════════════════════════════════════════════════════════
#  バー寸法定数（a=8 で最小ラベル 70mm 幅に収まるサイズ）
# ══════════════════════════════════════════════════════════════════════
# a=8 のとき: ロング=2.88mm, ピッチ=0.96mm, 幅=0.48mm
# 23文字×3バー=69本 × 0.96mm = 66.24mm → 70mm幅ラベルに余裕あり

_A = 8.0
_LONG_H  = 3.6 * _A / 10 * mm    # ロングバー高さ (pt)
_SHORT_H = 1.2 * _A / 10 * mm    # タイミングバー高さ (pt)
_PITCH   = 1.2 * _A / 10 * mm    # バー中心間距離 (pt)
_BAR_W   = 0.6 * _A / 10 * mm    # バー幅 (pt)
_EXTEND  = (_LONG_H - _SHORT_H) / 2  # 上下への延長量 (pt)


def barcode_height() -> float:
    """バーコード全体の高さ (pt) を返す。PDF サービスのレイアウト計算に使用"""
    return _LONG_H


def barcode_total_width(num_chars: int = 23) -> float:
    """バーコード全体の幅 (pt) を返す"""
    return num_chars * 3 * _PITCH


# ══════════════════════════════════════════════════════════════════════
#  バーコード描画
# ══════════════════════════════════════════════════════════════════════

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
                bar_y = mid_y - _SHORT_H / 2
                bar_h = _SHORT_H + _EXTEND
            elif bar_type == 'D':
                bar_y = mid_y - _SHORT_H / 2 - _EXTEND
                bar_h = _SHORT_H + _EXTEND
            else:  # T
                bar_y = mid_y - _SHORT_H / 2
                bar_h = _SHORT_H
            canvas.rect(x, bar_y, _BAR_W, bar_h, fill=1, stroke=0)
            x += _PITCH

    canvas.restoreState()
