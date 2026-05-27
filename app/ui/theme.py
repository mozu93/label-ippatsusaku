# -*- coding: utf-8 -*-
"""
アプリ共通デザイントークン — v2 (2026 single-accent palette)

方針:
  ・アクセントカラーは primary blue 1色のみ
  ・破壊操作は red (danger) のみ
  ・それ以外は warm neutral (gray-50/200/500 系) で統一
  ・背景はハーシュな純白を避け F9FAFB (gray-50) を基調とする
"""
from PyQt6.QtGui import QFont

# ── Primary accent ──────────────────────────────────────────────────
C_PRIMARY        = "#2563EB"   # blue-600
C_PRIMARY_HOVER  = "#1D4ED8"   # blue-700
C_PRIMARY_LIGHT  = "#EFF6FF"   # blue-50  (背景・ハイライト用)
C_PRIMARY_BORDER = "#BFDBFE"   # blue-200 (フォーカスリング・バナー枠)

# ── Danger ──────────────────────────────────────────────────────────
C_DANGER         = "#DC2626"   # red-600
C_DANGER_HOVER   = "#B91C1C"   # red-700

# ── Status (バッジ・状態表示専用。UIアクションには使わない) ──────────
C_SUCCESS        = "#16A34A"   # green-600
C_SUCCESS_HOVER  = "#15803D"   # green-700
C_SUCCESS_BG     = "#F0FDF4"   # green-50
C_SUCCESS_BORDER = "#86EFAC"   # green-300

C_WARNING        = "#D97706"   # amber-600 (通知バナー等)
C_WARNING_HOVER  = "#B45309"   # amber-700

# ── Neutral (アイコンの legacy マッピング含む) ────────────────────────
C_SECONDARY       = "#6B7280"   # gray-500
C_SECONDARY_HOVER = "#4B5563"   # gray-600

# 旧 Teal / Purple は Primary に統合 (import互換のためエイリアスを残す)
C_TEAL            = C_PRIMARY
C_TEAL_HOVER      = C_PRIMARY_HOVER
C_PURPLE          = C_PRIMARY
C_PURPLE_HOVER    = C_PRIMARY_HOVER

# ── Neutrals ────────────────────────────────────────────────────────
C_BG              = "#F9FAFB"   # gray-50  (app background)
C_BG_ALT          = "#F3F4F6"   # gray-100 (alternate rows)
C_SURFACE         = "#FFFFFF"
C_BORDER          = "#E5E7EB"   # gray-200
C_BORDER_DARK     = "#D1D5DB"   # gray-300

# ── Typography ──────────────────────────────────────────────────────
C_TEXT            = "#111827"   # gray-900
C_TEXT_SUB        = "#6B7280"   # gray-500
C_TEXT_MUTED      = "#9CA3AF"   # gray-400
C_TEXT_LINK       = C_PRIMARY

# ── Font ─────────────────────────────────────────────────────────────
FONT_FAMILY = "Meiryo UI"

def font_page_title() -> QFont:
    return QFont(FONT_FAMILY, 15, QFont.Weight.Bold)

def font_section_title() -> QFont:
    return QFont(FONT_FAMILY, 13, QFont.Weight.Bold)

def font_body() -> QFont:
    return QFont(FONT_FAMILY, 13)

# ── Spacing ──────────────────────────────────────────────────────────
PAGE_MARGIN     = (24, 20, 24, 20)
SECTION_SPACING = 16
FORM_SPACING    = 10

# ── Component sizes ──────────────────────────────────────────────────
BTN_H    = 36
BTN_H_SM = 28
INPUT_H  = 34
ROW_H    = 36

# ── Button styles ────────────────────────────────────────────────────
def _btn(bg: str, hover: str, text: str = "white") -> str:
    return (
        f"QPushButton {{ background: {bg}; color: {text}; border-radius: 5px; "
        f"border: none; font-size: 13px; font-family: '{FONT_FAMILY}'; "
        f"padding: 0 16px; }}"
        f"QPushButton:hover {{ background: {hover}; }}"
        f"QPushButton:disabled {{ background: {C_BG_ALT}; color: {C_TEXT_MUTED}; }}"
    )

BTN_PRIMARY   = _btn(C_PRIMARY,   C_PRIMARY_HOVER)
BTN_SUCCESS   = _btn(C_SUCCESS,   C_SUCCESS_HOVER)
BTN_DANGER    = _btn(C_DANGER,    C_DANGER_HOVER)
BTN_WARNING   = _btn(C_WARNING,   C_WARNING_HOVER)
BTN_SECONDARY = _btn(C_SECONDARY, C_SECONDARY_HOVER)
BTN_TEAL      = BTN_PRIMARY   # alias
BTN_PURPLE    = BTN_PRIMARY   # alias

# Ghost button（枠線あり・背景透明）
BTN_GHOST = (
    f"QPushButton {{ background: transparent; color: {C_SECONDARY}; "
    f"border: 1px solid {C_BORDER_DARK}; border-radius: 5px; "
    f"font-size: 13px; font-family: '{FONT_FAMILY}'; padding: 0 14px; }}"
    f"QPushButton:hover {{ background: {C_BG}; color: {C_TEXT}; "
    f"border-color: {C_BORDER_DARK}; }}"
    f"QPushButton:disabled {{ color: {C_TEXT_MUTED}; border-color: {C_BORDER}; }}"
)

# Outline button（白地・blue枠・blue文字）
BTN_OUTLINE = (
    f"QPushButton {{ background: white; color: {C_PRIMARY}; "
    f"border: 1px solid {C_PRIMARY}; border-radius: 5px; "
    f"font-size: 13px; font-family: '{FONT_FAMILY}'; padding: 0 16px; }}"
    f"QPushButton:hover {{ background: {C_PRIMARY_LIGHT}; }}"
    f"QPushButton:disabled {{ color: {C_TEXT_MUTED}; border-color: {C_BORDER_DARK}; }}"
)

# ── Input style ──────────────────────────────────────────────────────
INPUT_STYLE = (
    f"QLineEdit, QComboBox, QDateEdit, QSpinBox {{"
    f"  border: 1px solid {C_BORDER_DARK}; border-radius: 5px; "
    f"  padding: 2px 8px; font-size: 13px; font-family: '{FONT_FAMILY}'; "
    f"  background: white; color: {C_TEXT}; }}"
    f"QLineEdit:focus, QComboBox:focus, QDateEdit:focus {{"
    f"  border-color: {C_PRIMARY}; }}"
    f"QLineEdit:read-only {{ background: {C_BG}; color: {C_TEXT_SUB}; }}"
)

# ── Table style ──────────────────────────────────────────────────────
TABLE_STYLE = (
    f"QTableWidget {{"
    f"  border: 1px solid {C_BORDER}; border-radius: 6px; "
    f"  background: white; gridline-color: {C_BG_ALT}; "
    f"  font-size: 13px; font-family: '{FONT_FAMILY}'; }}"
    f"QTableWidget::item {{ padding: 4px 8px; color: {C_TEXT}; }}"
    f"QTableWidget::item:selected {{ background: {C_PRIMARY_LIGHT}; color: {C_TEXT}; }}"
    f"QTableWidget::item:hover {{ background: #DBEAFE; color: {C_TEXT}; }}"  # blue-100
    f"QTableWidget::item:alternate {{ background: {C_BG_ALT}; }}"
    f"QHeaderView::section {{"
    f"  background: {C_BG}; border: none; "
    f"  border-bottom: 2px solid {C_BORDER}; "
    f"  font-weight: bold; color: {C_TEXT_SUB}; "
    f"  font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 6px 8px; }}"
    f"QTableWidget::indicator {{ width: 15px; height: 15px; }}"
    f"QTableWidget::indicator:unchecked {{"
    f"  border: 2px solid {C_BORDER_DARK}; border-radius: 3px; background: white; }}"
    f"QTableWidget::indicator:checked {{"
    f"  border: 2px solid {C_PRIMARY}; border-radius: 3px; background: {C_PRIMARY}; }}"
    f"QTableWidget::indicator:unchecked:hover {{ border-color: {C_PRIMARY}; }}"
)

# ── Labels ───────────────────────────────────────────────────────────
PAGE_TITLE_STYLE = f"color: {C_TEXT}; font-family: '{FONT_FAMILY}';"

FILTER_BAR_STYLE = (
    f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; "
    f"border-radius: 6px; padding: 4px 0;"
)

CARD_STYLE = (
    f"background: {C_SURFACE}; border: 1px solid {C_BORDER}; border-radius: 8px;"
)

# ── Banner styles (info / warn) ───────────────────────────────────────
# 全モードバナーを統一：単一の neutral-blue info スタイル
INFO_BANNER = (
    f"background: {C_PRIMARY_LIGHT}; border: 1px solid {C_PRIMARY_BORDER}; "
    f"border-radius: 6px; padding: 6px 12px; "
    f"font-size: 11px; color: #1E40AF; font-family: '{FONT_FAMILY}';"   # blue-800
)

WARN_BANNER = (
    f"background: #FFFBEB; border: 1px solid #FCD34D; "
    f"border-radius: 6px; padding: 6px 12px; "
    f"font-size: 11px; color: #92400E; font-family: '{FONT_FAMILY}';"
)

# ── Badge ────────────────────────────────────────────────────────────
def status_badge(color: str, bg: str) -> str:
    return (
        f"color: {color}; background: {bg}; border-radius: 3px; "
        f"padding: 2px 8px; font-size: 11px; font-weight: bold; "
        f"font-family: '{FONT_FAMILY}';"
    )

# ── Toolbar button styles (small padding) ────────────────────────────
BTN_TB_OUTLINE = (
    f"QPushButton {{ background: white; color: {C_PRIMARY}; "
    f"border: 1px solid {C_PRIMARY}; border-radius: 5px; "
    f"font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 0 10px; }}"
    f"QPushButton:hover {{ background: {C_PRIMARY_LIGHT}; }}"
    f"QPushButton:disabled {{ color: {C_TEXT_MUTED}; border-color: {C_BORDER_DARK}; }}"
)

BTN_TB_DANGER = (
    f"QPushButton {{ background: {C_DANGER}; color: white; border-radius: 5px; "
    f"border: none; font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 0 10px; }}"
    f"QPushButton:hover {{ background: {C_DANGER_HOVER}; }}"
)

# ── Segment button style ──────────────────────────────────────────────
def seg_btn_style(pos: str) -> str:
    """pos: 'left' | 'mid' | 'right'"""
    r_tl = "4px" if pos == "left"  else "0px"
    r_tr = "4px" if pos == "right" else "0px"
    r_bl = "4px" if pos == "left"  else "0px"
    r_br = "4px" if pos == "right" else "0px"
    border_right = "none" if pos != "right" else "1px solid #CBD5E1"
    return (
        f"QPushButton {{"
        f"  background: white; color: {C_PRIMARY};"
        f"  border-top: 1px solid #CBD5E1;"
        f"  border-bottom: 1px solid #CBD5E1;"
        f"  border-left: 1px solid #CBD5E1;"
        f"  border-right: {border_right};"
        f"  border-top-left-radius: {r_tl}; border-bottom-left-radius: {r_bl};"
        f"  border-top-right-radius: {r_tr}; border-bottom-right-radius: {r_br};"
        f"  font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 0 12px; }}"
        f"QPushButton:checked {{"
        f"  background: {C_PRIMARY}; color: white;"
        f"  border-color: {C_PRIMARY}; }}"
        f"QPushButton:hover:!checked {{ background: {C_PRIMARY_LIGHT}; }}"
    )

# ── Step indicator styles ─────────────────────────────────────────────
STEP_STYLES: dict[str, str] = {
    "done": (
        f"background: {C_SUCCESS_BG}; color: #166534; border-radius: 5px;"
        f"font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 0 10px;"
    ),
    "active": (
        f"background: {C_PRIMARY}; color: white; border-radius: 5px;"
        f"font-size: 12px; font-weight: bold; font-family: '{FONT_FAMILY}'; padding: 0 10px;"
    ),
    "pending": (
        f"background: {C_BG_ALT}; color: {C_TEXT_MUTED}; border-radius: 5px;"
        f"font-size: 12px; font-family: '{FONT_FAMILY}'; padding: 0 10px;"
    ),
}

# ── Radio button (legacy) ─────────────────────────────────────────────
MODE_RADIO_STYLE = (
    f"QRadioButton {{"
    f"  font-size: 12px; font-family: '{FONT_FAMILY}'; spacing: 6px; }}"
    f"QRadioButton::indicator {{"
    f"  width: 14px; height: 14px; border-radius: 7px; "
    f"  border: 2px solid {C_BORDER_DARK}; background: white; }}"
    f"QRadioButton::indicator:checked {{"
    f"  background: {C_PRIMARY}; border-color: {C_PRIMARY}; }}"
    f"QRadioButton::indicator:hover {{ border-color: {C_PRIMARY}; }}"
)
