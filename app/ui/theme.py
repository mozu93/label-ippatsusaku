# -*- coding: utf-8 -*-
"""
アプリ共通デザイントークン
全UIファイルでこのモジュールをインポートして使用する。
"""
from PyQt6.QtGui import QFont

# ── カラー ─────────────────────────────────────────────────────────
C_PRIMARY        = "#1565C0"
C_PRIMARY_HOVER  = "#1976D2"
C_PRIMARY_LIGHT  = "#EFF6FF"

C_SUCCESS        = "#2E7D32"
C_SUCCESS_HOVER  = "#388E3C"

C_DANGER         = "#D32F2F"
C_DANGER_HOVER   = "#C62828"

C_WARNING        = "#E65100"
C_WARNING_HOVER  = "#BF360C"

C_SECONDARY      = "#475569"
C_SECONDARY_HOVER = "#334155"

C_TEAL           = "#00838F"
C_TEAL_HOVER     = "#00ACC1"

C_PURPLE         = "#6A1B9A"
C_PURPLE_HOVER   = "#7B1FA2"

C_BG             = "#F8FAFC"
C_SURFACE        = "#FFFFFF"
C_BORDER         = "#E2E8F0"
C_BORDER_DARK    = "#CBD5E1"

C_TEXT           = "#1E293B"
C_TEXT_SUB       = "#64748B"
C_TEXT_MUTED     = "#94A3B8"
C_TEXT_LINK      = C_PRIMARY

# ── タイポグラフィ ──────────────────────────────────────────────────
FONT_FAMILY = "Meiryo UI"

def font_page_title() -> QFont:
    return QFont(FONT_FAMILY, 15, QFont.Weight.Bold)

def font_section_title() -> QFont:
    return QFont(FONT_FAMILY, 13, QFont.Weight.Bold)

def font_body() -> QFont:
    return QFont(FONT_FAMILY, 13)

# ── スペーシング ───────────────────────────────────────────────────
PAGE_MARGIN      = (24, 20, 24, 20)   # left, top, right, bottom
SECTION_SPACING  = 16
FORM_SPACING     = 10

# ── コンポーネントサイズ ───────────────────────────────────────────
BTN_H            = 36   # 通常ボタン高さ
BTN_H_SM         = 28   # テーブル内ボタン高さ
INPUT_H          = 34   # 入力欄高さ
ROW_H            = 36   # テーブル行高さ

# ── ボタンスタイル ──────────────────────────────────────────────────
def _btn(bg: str, hover: str, text: str = "white") -> str:
    return (
        f"QPushButton {{ background: {bg}; color: {text}; border-radius: 4px; "
        f"border: none; font-size: 13px; font-family: '{FONT_FAMILY}'; "
        f"padding: 0 16px; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
        f"QPushButton:disabled {{ background: #B0BEC5; color: #ECEFF1; }}"
    )

BTN_PRIMARY   = _btn(C_PRIMARY,   C_PRIMARY_HOVER)
BTN_SUCCESS   = _btn(C_SUCCESS,   C_SUCCESS_HOVER)
BTN_DANGER    = _btn(C_DANGER,    C_DANGER_HOVER)
BTN_WARNING   = _btn(C_WARNING,   C_WARNING_HOVER)
BTN_SECONDARY = _btn(C_SECONDARY, C_SECONDARY_HOVER)
BTN_TEAL      = _btn(C_TEAL,      C_TEAL_HOVER)
BTN_PURPLE    = _btn(C_PURPLE,    C_PURPLE_HOVER)

# ゴーストボタン（枠線あり・背景透明）
BTN_GHOST = (
    f"QPushButton {{ background: transparent; color: {C_SECONDARY}; "
    f"border: 1px solid {C_BORDER_DARK}; border-radius: 4px; "
    f"font-size: 13px; font-family: '{FONT_FAMILY}'; padding: 0 14px; }}"
    f"QPushButton:hover {{ background: {C_BG}; color: {C_TEXT}; }}"
)

# アウトラインボタン（白地・青枠・青文字）
BTN_OUTLINE = (
    f"QPushButton {{ background: white; color: {C_PRIMARY}; "
    f"border: 1px solid {C_PRIMARY}; border-radius: 4px; "
    f"font-size: 13px; font-family: '{FONT_FAMILY}'; padding: 0 20px; }}"
    f"QPushButton:hover {{ background: {C_PRIMARY_LIGHT}; }}"
    f"QPushButton:disabled {{ color: #BDBDBD; border-color: #BDBDBD; }}"
)

# ── 入力欄スタイル ──────────────────────────────────────────────────
INPUT_STYLE = (
    f"QLineEdit, QComboBox, QDateEdit, QSpinBox {{"
    f"  border: 1px solid {C_BORDER_DARK}; border-radius: 4px; "
    f"  padding: 2px 8px; font-size: 13px; font-family: '{FONT_FAMILY}'; "
    f"  background: white; color: {C_TEXT}; }}"
    f"QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{"
    f"  border-color: {C_PRIMARY}; }}"
    f"QLineEdit:read-only {{ background: {C_BG}; color: {C_TEXT_SUB}; }}"
)

# ── テーブルスタイル ───────────────────────────────────────────────
TABLE_STYLE = (
    f"QTableWidget {{"
    f"  border: 1px solid {C_BORDER}; border-radius: 6px; "
    f"  background: white; gridline-color: #F1F5F9; "
    f"  font-size: 13px; font-family: '{FONT_FAMILY}'; }}"
    f"QTableWidget::item {{ padding: 4px 8px; color: {C_TEXT}; }}"
    f"QTableWidget::item:selected {{ background: {C_PRIMARY_LIGHT}; color: {C_TEXT}; }}"
    f"QTableWidget::item:hover {{ background: #BBDEFB; color: {C_TEXT}; }}"
    f"QTableWidget::item:alternate {{ background: #FAFBFC; }}"
    f"QHeaderView::section {{"
    f"  background: {C_BG}; border: none; "
    f"  border-bottom: 2px solid {C_BORDER}; "
    f"  font-weight: bold; color: {C_TEXT_SUB}; "
    f"  font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 6px 8px; }}"
    f"QTableWidget::indicator {{ width: 15px; height: 15px; }}"
    f"QTableWidget::indicator:unchecked {{"
    f"  border: 2px solid #94A3B8; border-radius: 3px; background: white; }}"
    f"QTableWidget::indicator:checked {{"
    f"  border: 2px solid {C_PRIMARY}; border-radius: 3px; background: {C_PRIMARY}; }}"
    f"QTableWidget::indicator:unchecked:hover {{"
    f"  border-color: {C_PRIMARY}; }}"
)

# ── ページタイトルラベルスタイル ───────────────────────────────────
PAGE_TITLE_STYLE = f"color: {C_TEXT}; font-family: '{FONT_FAMILY}';"

# ── フィルターバースタイル ─────────────────────────────────────────
FILTER_BAR_STYLE = (
    f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; "
    f"border-radius: 6px; padding: 4px 0;"
)

# ── カードパネルスタイル ───────────────────────────────────────────
CARD_STYLE = (
    f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 6px;"
)

# ── バッジ/ステータスラベル ────────────────────────────────────────
def status_badge(color: str, bg: str) -> str:
    return (
        f"color: {color}; background: {bg}; border-radius: 3px; "
        f"padding: 2px 8px; font-size: 11px; font-weight: bold; "
        f"font-family: '{FONT_FAMILY}';"
    )

# ── 情報バナー ─────────────────────────────────────────────────────
INFO_BANNER = (
    f"background: {C_PRIMARY_LIGHT}; border: 1px solid #BFDBFE; "
    f"border-radius: 4px; padding: 8px 12px; "
    f"font-size: 12px; color: #1E40AF; font-family: '{FONT_FAMILY}';"
)

WARN_BANNER = (
    f"background: #FFF7ED; border: 1px solid #FED7AA; "
    f"border-radius: 4px; padding: 8px 12px; "
    f"font-size: 12px; color: #9A3412; font-family: '{FONT_FAMILY}';"
)
