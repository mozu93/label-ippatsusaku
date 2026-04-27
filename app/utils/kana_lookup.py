# -*- coding: utf-8 -*-
"""
事業所名のフリガナ（カタカナ）自動変換ユーティリティ。
pykakasi を使用してオフラインで変換する。
法人種別名（株式会社、有限会社など）は除外してから変換する。
"""
import re

_LEGAL_NAMES = [
    "特定非営利活動法人",
    "独立行政法人",
    "国立大学法人",
    "公立大学法人",
    "公益社団法人",
    "公益財団法人",
    "一般社団法人",
    "一般財団法人",
    "社会福祉法人",
    "農業協同組合",
    "生活協同組合",
    "NPO法人",
    "株式会社",
    "有限会社",
    "合同会社",
    "合資会社",
    "合名会社",
    "医療法人社団",
    "医療法人財団",
    "医療法人",
    "学校法人",
    "宗教法人",
    "協同組合",
    # 略称（全角・半角括弧の両方に対応）
    "（株）", "(株)",
    "（有）", "(有)",
    "（合）", "(合)",
    "（資）", "(資)",
    "（名）", "(名)",
    "（医）", "(医)",
    "（社）", "(社)",
    "（財）", "(財)",
    "（協）", "(協)",
    "（特非）", "(特非)",
    "（NPO）", "(NPO)",
]

# ── アルファベット読み表（大文字のみ・頭字語用） ────────────────────
_ALPHA_KANA = {
    'A': 'エー',   'B': 'ビー',      'C': 'シー',      'D': 'ディー',
    'E': 'イー',   'F': 'エフ',      'G': 'ジー',      'H': 'エイチ',
    'I': 'アイ',   'J': 'ジェー',    'K': 'ケー',      'L': 'エル',
    'M': 'エム',   'N': 'エヌ',      'O': 'オー',      'P': 'ピー',
    'Q': 'キュー', 'R': 'アール',    'S': 'エス',      'T': 'ティー',
    'U': 'ユー',   'V': 'ブイ',      'W': 'ダブリュー', 'X': 'エックス',
    'Y': 'ワイ',   'Z': 'ゼット',
}

# ── ローマ字→カタカナ変換テーブル（ヘボン式） ────────────────────────
# 長いシーケンスほど先にマッチさせるため、3→2→1 の順で検索する
_R2K: dict[str, str] = {}

for _rom, _kat in [
    # 3文字
    ("sha", "シャ"), ("shi", "シ"),  ("shu", "シュ"), ("she", "シェ"), ("sho", "ショ"),
    ("chi", "チ"),   ("cha", "チャ"), ("chu", "チュ"), ("che", "チェ"), ("cho", "チョ"),
    ("tsu", "ツ"),   ("thi", "ティ"), ("dhi", "ディ"),
    ("nya", "ニャ"), ("nyi", "ニィ"), ("nyu", "ニュ"), ("nye", "ニェ"), ("nyo", "ニョ"),
    ("mya", "ミャ"), ("myu", "ミュ"), ("myo", "ミョ"),
    ("rya", "リャ"), ("ryu", "リュ"), ("ryo", "リョ"),
    ("hya", "ヒャ"), ("hyu", "ヒュ"), ("hyo", "ヒョ"),
    ("bya", "ビャ"), ("byu", "ビュ"), ("byo", "ビョ"),
    ("pya", "ピャ"), ("pyu", "ピュ"), ("pyo", "ピョ"),
    ("kya", "キャ"), ("kyu", "キュ"), ("kyo", "キョ"),
    ("gya", "ギャ"), ("gyu", "ギュ"), ("gyo", "ギョ"),
    # 2文字
    ("ka", "カ"), ("ki", "キ"), ("ku", "ク"), ("ke", "ケ"), ("ko", "コ"),
    ("sa", "サ"), ("si", "シ"), ("su", "ス"), ("se", "セ"), ("so", "ソ"),
    ("ta", "タ"), ("ti", "チ"), ("tu", "ツ"), ("te", "テ"), ("to", "ト"),
    ("na", "ナ"), ("ni", "ニ"), ("nu", "ヌ"), ("ne", "ネ"), ("no", "ノ"),
    ("ha", "ハ"), ("hi", "ヒ"), ("fu", "フ"), ("hu", "フ"), ("he", "ヘ"), ("ho", "ホ"),
    ("ma", "マ"), ("mi", "ミ"), ("mu", "ム"), ("me", "メ"), ("mo", "モ"),
    ("ya", "ヤ"), ("yu", "ユ"), ("ye", "イェ"), ("yo", "ヨ"),
    ("ra", "ラ"), ("ri", "リ"), ("ru", "ル"), ("re", "レ"), ("ro", "ロ"),
    ("wa", "ワ"), ("wi", "ヰ"), ("wo", "ヲ"),
    ("ga", "ガ"), ("gi", "ギ"), ("gu", "グ"), ("ge", "ゲ"), ("go", "ゴ"),
    ("za", "ザ"), ("zi", "ジ"), ("zu", "ズ"), ("ze", "ゼ"), ("zo", "ゾ"),
    ("ji", "ジ"), ("ja", "ジャ"), ("ju", "ジュ"), ("jo", "ジョ"),
    ("da", "ダ"), ("di", "ヂ"), ("du", "ヅ"), ("de", "デ"), ("do", "ド"),
    ("ba", "バ"), ("bi", "ビ"), ("bu", "ブ"), ("be", "ベ"), ("bo", "ボ"),
    ("pa", "パ"), ("pi", "ピ"), ("pu", "プ"), ("pe", "ペ"), ("po", "ポ"),
    ("va", "ヴァ"), ("vi", "ヴィ"), ("vu", "ヴ"), ("ve", "ヴェ"), ("vo", "ヴォ"),
    # c の音価（ca=カ行、ci/ce=サ行寄り）
    ("ca", "カ"), ("ci", "シ"), ("cu", "ク"), ("ce", "セ"), ("co", "コ"),
    # 1文字（母音）
    ("a", "ア"), ("i", "イ"), ("u", "ウ"), ("e", "エ"), ("o", "オ"),
    # 語末に現れやすい単独子音
    ("b", "ブ"), ("c", "ク"), ("d", "ド"), ("f", "フ"),
    ("g", "グ"), ("h", "ハ"), ("j", "ジ"), ("k", "ク"),
    ("l", "ル"), ("m", "ム"), ("p", "プ"), ("q", "ク"),
    ("r", "ル"), ("s", "ス"), ("t", "ト"), ("v", "ブ"),
    ("w", "ウ"), ("x", "クス"), ("y", "イ"), ("z", "ズ"),
]:
    _R2K[_rom] = _kat


_VOWELS = set("aiueo")
_CONSONANTS = set("bcdfghjklmpqrstvwxyz")


def _parse_romaji(s: str, strict: bool) -> str | None:
    """
    ローマ字文字列をカタカナに変換する内部実装。

    strict=True  : 語中で単独子音フォールバックが必要な場合は None を返す
                   （全大文字のローマ字判定用）
    strict=False : 変換できない文字はアルファベット読みで補完する
                   （小文字混じりの確定ローマ字変換用）
    """
    result: list[str] = []
    i = 0
    while i < len(s):
        c = s[i]
        nxt = s[i + 1] if i + 1 < len(s) else ""

        # 促音：同じ子音が連続（n を除く）
        if c != "n" and c in _CONSONANTS and nxt == c:
            result.append("ッ")
            i += 1
            continue

        # ん
        if c == "n":
            # ny + 非母音 → ニ（Sony, Panasonic など）
            if nxt == "y":
                after_y = s[i + 2] if i + 2 < len(s) else ""
                if not after_y or after_y not in _VOWELS:
                    result.append("ニ")
                    i += 2
                    continue
            # nn → ン 1つ（次ループで残りの n を処理）
            if nxt == "n":
                result.append("ン")
                i += 1
                continue
            # n + 子音 or 語末 → ン
            if not nxt or nxt not in _VOWELS | {"n", "y"}:
                result.append("ン")
                i += 1
                continue

        # 最長一致（3→2→1 文字）
        for length in (3, 2, 1):
            chunk = s[i: i + length]
            if chunk in _R2K:
                is_single_consonant = (length == 1 and chunk not in _VOWELS)
                is_mid_word = (i + 1 < len(s))
                if strict and is_single_consonant and is_mid_word:
                    return None  # 語中で子音フォールバック → ローマ字として無効
                result.append(_R2K[chunk])
                i += length
                break
        else:
            if strict:
                return None
            result.append(_ALPHA_KANA.get(c.upper(), c))
            i += 1

    kana = "".join(result)
    # ン・ッ で始まる結果はローマ字として不自然（NTT → ンット など）
    if strict and kana and kana[0] in "ンッ":
        return None
    return kana


def _romaji_to_katakana(text: str) -> str:
    """小文字混じりのローマ字をカタカナに変換する（フォールバックあり）"""
    return _parse_romaji(text.lower(), strict=False)


def _try_as_romaji(word: str) -> str | None:
    """
    全大文字の単語をローマ字として変換を試みる。
    自然に変換できない場合は None を返す。
    条件: 4文字以上 かつ 母音(AIUEO)を含む
    """
    upper_vowels = set("AIUEO")
    if len(word) < 4 or not any(c in upper_vowels for c in word):
        return None
    return _parse_romaji(word.lower(), strict=True)


_kakasi = None


def _get_kakasi():
    global _kakasi
    if _kakasi is None:
        import pykakasi
        _kakasi = pykakasi.kakasi()
    return _kakasi


def strip_legal_name(text: str) -> str:
    """法人種別名を先頭または末尾から除去する（長い名前を優先）"""
    t = text.strip()
    for name in _LEGAL_NAMES:
        if t.startswith(name):
            return t[len(name):].strip()
        if t.endswith(name):
            return t[: -len(name)].strip()
    return t


def _alpha_seq_to_kana(text: str) -> str:
    """
    文字列中のASCIIアルファベット連続部分をカタカナに変換する。

    判別ルール:
    - 小文字を含む → ローマ字読み（Toyota → トヨタ）
    - 全大文字 かつ 4文字以上 かつ 母音あり → ローマ字変換を試みる
      - 変換成功（自然なローマ字）→ ローマ字読み（TOYOTA → トヨタ）
      - 変換失敗（語中に解釈不能な子音など）→ 頭字語読み（IBM → アイビーエム）
    - 全大文字 かつ 3文字以下 or 母音なし → 頭字語読み（NTT → エヌティーティー）
    """
    def _repl(m: re.Match) -> str:
        word = m.group(0)
        if not word.isupper():
            return _romaji_to_katakana(word)
        # 全大文字：ローマ字変換を試みる
        kana = _try_as_romaji(word)
        if kana:
            return kana
        # フォールバック：頭字語読み
        return "".join(_ALPHA_KANA.get(c, c) for c in word)
    return re.sub(r"[A-Za-z]+", _repl, text)


def to_katakana(text: str) -> str:
    """漢字・ひらがな・英字混じりテキストをカタカナに変換する。改行は保持する。"""
    kks = _get_kakasi()
    lines = text.split("\n")
    result_lines = []
    for line in lines:
        items = kks.convert(line)
        converted = "".join(item["kana"] for item in items)
        result_lines.append(_alpha_seq_to_kana(converted))
    return "\n".join(result_lines)


def get_company_kana(company_name: str) -> str:
    """
    事業所名から法人種別名を除いてカタカナのフリガナを返す。
    変換できない場合は空文字を返す。
    """
    if not company_name.strip():
        return ""
    try:
        core = strip_legal_name(company_name)
        if not core:
            core = company_name.strip()
        return to_katakana(core)
    except Exception:
        return ""
