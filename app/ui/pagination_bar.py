# app/ui/pagination_bar.py
import math
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSignal


class PaginationBar(QWidget):
    """ページネーション制御バー。changed シグナルでページ/件数変更を通知する。"""
    changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._page = 1
        self._total = 0
        self._page_size = 50
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(6)

        _nav_btn_style = (
            "QPushButton { border: 1px solid #BDBDBD; border-radius: 3px; padding: 0 10px; }"
            "QPushButton:hover { background: #E3F2FD; }"
            "QPushButton:disabled { color: #BDBDBD; }"
        )

        self._btn_prev = QPushButton("< 前へ")
        self._btn_prev.setFixedHeight(28)
        self._btn_prev.setStyleSheet(_nav_btn_style)
        self._btn_prev.clicked.connect(self._prev)

        self._lbl = QLabel("1 / 1 ページ")
        self._lbl.setFixedHeight(28)
        self._lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignHCenter)
        self._lbl.setStyleSheet("color: #555; font-size: 12px;")

        self._btn_next = QPushButton("次へ >")
        self._btn_next.setFixedHeight(28)
        self._btn_next.setStyleSheet(_nav_btn_style)
        self._btn_next.clicked.connect(self._next)

        self._size_combo = QComboBox()
        self._size_combo.setFixedHeight(28)
        self._size_combo.setStyleSheet(
            "QComboBox { border: 1px solid #BDBDBD; border-radius: 3px; "
            "padding: 0 4px; font-size: 12px; color: #555; background: white; }"
            "QComboBox::drop-down { subcontrol-origin: padding; subcontrol-position: top right; "
            "width: 16px; border-left: 1px solid #BDBDBD; }"
        )
        self._size_combo.blockSignals(True)
        for s in [50, 100, 200]:
            self._size_combo.addItem(f"{s}件", s)
        self._size_combo.blockSignals(False)
        self._size_combo.currentIndexChanged.connect(self._on_size_changed)

        self._total_lbl = QLabel("全 0 件")
        self._total_lbl.setFixedHeight(28)
        self._total_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        self._total_lbl.setStyleSheet("color: #555; font-size: 12px;")

        layout.addWidget(self._btn_prev)
        layout.addWidget(self._lbl)
        layout.addWidget(self._btn_next)
        layout.addStretch()
        size_lbl = QLabel("表示件数:")
        size_lbl.setFixedHeight(28)
        size_lbl.setStyleSheet("color: #555; font-size: 12px;")
        layout.addWidget(size_lbl)
        layout.addWidget(self._size_combo)
        layout.addWidget(self._total_lbl)

        self._update_ui()

    def set_total(self, total: int):
        self._total = total
        if self._page > self._total_pages():
            self._page = max(1, self._total_pages())
        self._update_ui()

    def reset(self):
        """フィルター変更時にページ1に戻す。"""
        self._page = 1
        self._update_ui()

    def current_page(self) -> int:
        return self._page

    def page_size(self) -> int:
        return self._page_size

    def slice_range(self) -> tuple[int, int]:
        """現在ページのスライス範囲 (start, end) を返す。"""
        start = (self._page - 1) * self._page_size
        return start, start + self._page_size

    def _total_pages(self) -> int:
        if self._total == 0:
            return 1
        return math.ceil(self._total / self._page_size)

    def _prev(self):
        if self._page > 1:
            self._page -= 1
            self._update_ui()
            self.changed.emit()

    def _next(self):
        if self._page < self._total_pages():
            self._page += 1
            self._update_ui()
            self.changed.emit()

    def _on_size_changed(self):
        self._page_size = self._size_combo.currentData()
        self._page = 1
        self._update_ui()
        self.changed.emit()

    def _update_ui(self):
        tp = self._total_pages()
        self._lbl.setText(f"{self._page} / {tp} ページ")
        self._btn_prev.setEnabled(self._page > 1)
        self._btn_next.setEnabled(self._page < tp)
        self._total_lbl.setText(f"全 {self._total} 件")
