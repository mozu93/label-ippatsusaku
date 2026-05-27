# -*- coding: utf-8 -*-
"""
PDF プレビューダイアログ（PyMuPDF 使用）

generate_label_pdf() が返す bytes（BytesIO.getvalue()）を受け取り、
ページ単位で拡大・縮小・ページ送りしながら確認できる。

【修正履歴】
  v2: container QWidget を廃止。img_lbl を QScrollArea の直接 widget にすることで、
      setFixedSize のレイアウト更新遅延によるサイズ消失バグを解消。
      showEvent で _fit_width を実行し、ダイアログ幅に合わせた初期ズームを適用。
"""
import fitz  # PyMuPDF

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QImage, QPixmap

from app.ui.theme import BTN_OUTLINE, C_TEXT_SUB


class PdfPreviewDialog(QDialog):
    """PDF をページごとにプレビュー表示するダイアログ"""

    _ZOOM_MIN  = 0.5
    _ZOOM_MAX  = 4.0
    _ZOOM_STEP = 1.25

    def __init__(self, pdf_data: bytes, title: str = "PDF プレビュー", parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setMinimumSize(720, 560)
        self.resize(900, 720)
        self._pdf_data  = pdf_data
        self._current   = 0
        self._zoom      = 1.0          # showEvent で fit_width により上書きされる
        self._first_show = True
        self._doc       = fitz.open(stream=pdf_data, filetype="pdf")
        self._total     = len(self._doc)
        self._init_ui()
        # __init__ ではまだ viewport サイズが確定していないため
        # 初回レンダリングは showEvent → _fit_width で行う

    # ── UI 構築 ────────────────────────────────────────────────────────

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        # ── ナビゲーションバー ─────────────────────────────────────────
        nav = QHBoxLayout()
        nav.setSpacing(6)

        self._btn_prev = QPushButton("◀ 前ページ")
        self._btn_prev.setFixedHeight(30)
        self._btn_prev.setStyleSheet(BTN_OUTLINE)
        self._btn_prev.clicked.connect(self._prev)

        self._page_lbl = QLabel()
        self._page_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._page_lbl.setStyleSheet(
            f"font-size: 13px; color: {C_TEXT_SUB}; min-width: 120px;"
        )

        self._btn_next = QPushButton("次ページ ▶")
        self._btn_next.setFixedHeight(30)
        self._btn_next.setStyleSheet(BTN_OUTLINE)
        self._btn_next.clicked.connect(self._next)

        btn_zoom_out = QPushButton("－")
        btn_zoom_out.setFixedSize(30, 30)
        btn_zoom_out.setStyleSheet(BTN_OUTLINE)
        btn_zoom_out.setToolTip("縮小（ズームアウト）")
        btn_zoom_out.clicked.connect(self._zoom_out)

        self._zoom_lbl = QLabel("100%")
        self._zoom_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._zoom_lbl.setStyleSheet(
            f"font-size: 12px; color: {C_TEXT_SUB}; min-width: 48px;"
        )

        btn_zoom_in = QPushButton("＋")
        btn_zoom_in.setFixedSize(30, 30)
        btn_zoom_in.setStyleSheet(BTN_OUTLINE)
        btn_zoom_in.setToolTip("拡大（ズームイン）")
        btn_zoom_in.clicked.connect(self._zoom_in)

        btn_fit = QPushButton("幅に合わせる")
        btn_fit.setFixedHeight(30)
        btn_fit.setStyleSheet(BTN_OUTLINE)
        btn_fit.setToolTip("ウィンドウ幅にフィット")
        btn_fit.clicked.connect(self._fit_width)

        nav.addWidget(self._btn_prev)
        nav.addWidget(self._page_lbl)
        nav.addWidget(self._btn_next)
        nav.addSpacing(12)
        nav.addWidget(btn_zoom_out)
        nav.addWidget(self._zoom_lbl)
        nav.addWidget(btn_zoom_in)
        nav.addSpacing(4)
        nav.addWidget(btn_fit)
        nav.addStretch()
        root.addLayout(nav)

        # ── スクロールエリア ───────────────────────────────────────────
        # img_lbl を直接 setWidget することで、resize() がスクロールエリアに
        # 即座に反映される（container 経由の遅延更新バグを回避）
        self._scroll = QScrollArea()
        self._scroll.setWidgetResizable(False)
        self._scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._scroll.setStyleSheet(
            "QScrollArea { background: #475569; border: none; }"
            "QScrollBar:vertical {"
            "  width: 8px; background: #334155; border: none; }"
            "QScrollBar::handle:vertical {"
            "  background: #94A3B8; border-radius: 4px; min-height: 30px; }"
            "QScrollBar:horizontal {"
            "  height: 8px; background: #334155; border: none; }"
            "QScrollBar::handle:horizontal {"
            "  background: #94A3B8; border-radius: 4px; min-width: 30px; }"
            "QScrollBar::add-line, QScrollBar::sub-line { width: 0; height: 0; }"
        )

        # ページ画像ラベル（スクロールエリアの直接 widget）
        self._img_lbl = QLabel()
        self._img_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._img_lbl.setStyleSheet(
            "background: white; border: 1px solid #94A3B8;"
        )
        self._scroll.setWidget(self._img_lbl)
        root.addWidget(self._scroll, 1)

        # ── フッター ──────────────────────────────────────────────────
        foot = QHBoxLayout()
        btn_close = QPushButton("閉じる")
        btn_close.setFixedHeight(36)
        btn_close.setStyleSheet(
            f"QPushButton {{ color: {C_TEXT_SUB}; border: 1px solid #D1D5DB; "
            f"border-radius: 5px; background: white; padding: 0 20px; }}"
            f"QPushButton:hover {{ background: #F9FAFB; }}"
        )
        btn_close.clicked.connect(self.accept)
        foot.addStretch()
        foot.addWidget(btn_close)
        root.addLayout(foot)

    # ── レンダリング ───────────────────────────────────────────────────

    def _render(self):
        """現在ページを self._zoom 倍でレンダリングして img_lbl に表示する"""
        page = self._doc[self._current]
        mat  = fitz.Matrix(self._zoom, self._zoom)
        pix  = page.get_pixmap(matrix=mat, alpha=False)

        # pix.samples を bytes にコピーして QImage の参照切れを防ぐ
        img_bytes = bytes(pix.samples)
        qt_img    = QImage(img_bytes, pix.width, pix.height,
                           pix.stride, QImage.Format.Format_RGB888)
        pixmap    = QPixmap.fromImage(qt_img)   # ここでディープコピー確定

        self._img_lbl.setPixmap(pixmap)
        # resize() でスクロールエリアが即座にスクロール範囲を再計算する
        # setFixedSize は defer されるため使わない
        self._img_lbl.resize(pixmap.size())

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
        """ビューポート幅にページが収まるズーム率を計算して再描画する"""
        page  = self._doc[self._current]
        vp_w  = self._scroll.viewport().width() - 8   # 左右 4px マージン
        pw    = page.rect.width                        # PDF ページ幅 (points)
        if pw > 0 and vp_w > 0:
            self._zoom = max(self._ZOOM_MIN, min(vp_w / pw, self._ZOOM_MAX))
        self._render()

    # ── ライフサイクル ─────────────────────────────────────────────────

    def showEvent(self, event):
        """初回表示時にビューポートサイズが確定してから幅フィットを実行する"""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
            self._fit_width()

    def closeEvent(self, event):
        self._doc.close()
        super().closeEvent(event)
