# -*- coding: utf-8 -*-
"""
PDF プレビューダイアログ（PyMuPDF 使用）

generate_label_pdf() が返す bytes（BytesIO.getvalue()）を受け取り、
ページ単位で拡大・縮小・ページ送りしながら確認できる。
"""
import fitz  # PyMuPDF

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap

from app.ui.theme import BTN_PRIMARY, BTN_OUTLINE


class PdfPreviewDialog(QDialog):
    """PDF をページごとにプレビュー表示するダイアログ"""

    _ZOOM_MIN = 0.5
    _ZOOM_MAX = 4.0
    _ZOOM_STEP = 1.25

    def __init__(self, pdf_data: bytes, title: str = "PDF プレビュー", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(720, 560)
        self.resize(860, 680)
        self._pdf_data    = pdf_data
        self._current     = 0
        self._zoom        = 1.5
        self._doc         = fitz.open(stream=pdf_data, filetype="pdf")
        self._total       = len(self._doc)
        self._init_ui()
        self._render()

    # ── UI 構築 ────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ナビゲーションバー
        nav = QHBoxLayout()
        nav.setSpacing(6)

        self._btn_prev = QPushButton("◀ 前ページ")
        self._btn_prev.setFixedHeight(30)
        self._btn_prev.setStyleSheet(BTN_OUTLINE)
        self._btn_prev.clicked.connect(self._prev)

        self._page_lbl = QLabel()
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setStyleSheet("font-size: 13px; color: #475569; min-width: 120px;")

        self._btn_next = QPushButton("次ページ ▶")
        self._btn_next.setFixedHeight(30)
        self._btn_next.setStyleSheet(BTN_OUTLINE)
        self._btn_next.clicked.connect(self._next)

        sep = QWidget()
        sep.setFixedWidth(16)

        btn_zoom_out = QPushButton("－")
        btn_zoom_out.setFixedSize(30, 30)
        btn_zoom_out.setStyleSheet(BTN_OUTLINE)
        btn_zoom_out.setToolTip("縮小")
        btn_zoom_out.clicked.connect(self._zoom_out)

        self._zoom_lbl = QLabel()
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_lbl.setStyleSheet("font-size: 12px; color: #64748B; min-width: 44px;")

        btn_zoom_in = QPushButton("＋")
        btn_zoom_in.setFixedSize(30, 30)
        btn_zoom_in.setStyleSheet(BTN_OUTLINE)
        btn_zoom_in.setToolTip("拡大")
        btn_zoom_in.clicked.connect(self._zoom_in)

        btn_fit = QPushButton("幅に合わせる")
        btn_fit.setFixedHeight(30)
        btn_fit.setStyleSheet(BTN_OUTLINE)
        btn_fit.clicked.connect(self._fit_width)

        nav.addWidget(self._btn_prev)
        nav.addWidget(self._page_lbl)
        nav.addWidget(self._btn_next)
        nav.addWidget(sep)
        nav.addWidget(btn_zoom_out)
        nav.addWidget(self._zoom_lbl)
        nav.addWidget(btn_zoom_in)
        nav.addWidget(btn_fit)
        nav.addStretch()
        root.addLayout(nav)

        # スクロールエリア
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #94A3B8; border: none; }"
            "QScrollBar:vertical { width: 8px; background: #CBD5E1; border: none; }"
            "QScrollBar::handle:vertical { background: #64748B; border-radius: 4px; min-height: 30px; }"
            "QScrollBar:horizontal { height: 8px; background: #CBD5E1; border: none; }"
            "QScrollBar::handle:horizontal { background: #64748B; border-radius: 4px; min-width: 30px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }"
        )

        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(
            "QLabel { background: white; "
            "border: 1px solid #CBD5E1; "
            "margin: 12px; }"
        )

        # スクロールエリアの中身を包む（中央寄せ用）
        container = QWidget()
        container.setStyleSheet("background: #94A3B8;")
        cont_layout = QHBoxLayout(container)
        cont_layout.setContentsMargins(0, 0, 0, 0)
        cont_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cont_layout.addWidget(self._img_lbl)
        self._scroll.setWidget(container)
        root.addWidget(self._scroll, 1)

        # フッター
        foot = QHBoxLayout()
        btn_close = QPushButton("閉じる")
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(
            "QPushButton { color: #64748B; border: 1px solid #CBD5E1; "
            "border-radius: 4px; background: white; padding: 0 20px; }"
            "QPushButton:hover { background: #F1F5F9; }"
        )
        btn_close.clicked.connect(self.accept)
        foot.addStretch()
        foot.addWidget(btn_close)
        root.addLayout(foot)

    # ── レンダリング ───────────────────────────────────────────────────

    def _render(self):
        page = self._doc[self._current]
        mat  = fitz.Matrix(self._zoom, self._zoom)
        pix  = page.get_pixmap(matrix=mat, alpha=False)

        img    = QImage(pix.samples, pix.width, pix.height,
                        pix.stride, QImage.Format.Format_RGB888)
        pixmap = QPixmap.fromImage(img)
        self._img_lbl.setPixmap(pixmap)
        self._img_lbl.setFixedSize(pixmap.size())

        self._page_lbl.setText(f"{self._current + 1} / {self._total} ページ")
        self._zoom_lbl.setText(f"{int(self._zoom * 100)}%")
        self._btn_prev.setEnabled(self._current > 0)
        self._btn_next.setEnabled(self._current < self._total - 1)

    # ── ナビゲーション ─────────────────────────────────────────────────

    def _prev(self):
        if self._current > 0:
            self._current -= 1
            self._render()

    def _next(self):
        if self._current < self._total - 1:
            self._current += 1
            self._render()

    def _zoom_in(self):
        self._zoom = min(self._zoom * self._ZOOM_STEP, self._ZOOM_MAX)
        self._render()

    def _zoom_out(self):
        self._zoom = max(self._zoom / self._ZOOM_STEP, self._ZOOM_MIN)
        self._render()

    def _fit_width(self):
        """スクロールエリア幅に合わせたズーム率を計算して適用する"""
        page   = self._doc[self._current]
        vp_w   = self._scroll.viewport().width() - 32   # margin 込み
        page_w = page.rect.width  # pt 単位の元の幅
        if page_w > 0:
            self._zoom = max(self._ZOOM_MIN, min(vp_w / page_w, self._ZOOM_MAX))
        self._render()

    # ── クリーンアップ ─────────────────────────────────────────────────

    def closeEvent(self, event):
        self._doc.close()
        super().closeEvent(event)
