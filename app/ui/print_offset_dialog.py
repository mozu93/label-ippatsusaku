# -*- coding: utf-8 -*-
"""印刷位置補正ダイアログ（ファイルメニューから起動）"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
    QLabel, QDoubleSpinBox, QPushButton, QMessageBox,
)
from PyQt6.QtCore import Qt

from app.services.label_pdf_service import LABEL_LAYOUTS
from app.utils.app_config import get_label_offset, save_label_offset
from app.ui.theme import BTN_PRIMARY

_EXCLUDED_LAYOUT_KEYS = {"a4_4split"}

_DESC = (
    "印刷後にシールと印刷位置がずれる場合に補正します。\n"
    "内容が右にずれる → 横補正を負に　　内容が左にずれる → 横補正を正に\n"
    "内容が下にずれる → 縦補正を負に　　内容が上にずれる → 縦補正を正に"
)


def _make_spin(value: float) -> QDoubleSpinBox:
    spin = QDoubleSpinBox()
    spin.setRange(-15.0, 15.0)
    spin.setSingleStep(0.5)
    spin.setDecimals(1)
    spin.setValue(value)
    spin.setSuffix(" mm")
    spin.setFixedWidth(90)
    return spin


class PrintOffsetDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("印刷位置補正")
        self.setFixedSize(480, 400)

        root = QVBoxLayout(self)
        root.setAlignment(Qt.AlignmentFlag.AlignTop)
        root.setSpacing(12)
        root.setContentsMargins(16, 16, 16, 16)

        desc = QLabel(_DESC)
        desc.setStyleSheet("color: #555; font-size: 11px;")
        desc.setWordWrap(True)
        root.addWidget(desc)

        self._spins: dict[str, tuple[QDoubleSpinBox, QDoubleSpinBox]] = {}

        for key, layout in LABEL_LAYOUTS.items():
            if key in _EXCLUDED_LAYOUT_KEYS:
                continue
            h_mm, v_mm = get_label_offset(key)
            grp = QGroupBox(layout.name)
            lay = QVBoxLayout(grp)

            row = QHBoxLayout()
            row.addWidget(QLabel("横補正:"))
            h_spin = _make_spin(h_mm)
            row.addWidget(h_spin)
            row.addSpacing(20)
            row.addWidget(QLabel("縦補正:"))
            v_spin = _make_spin(v_mm)
            row.addWidget(v_spin)
            row.addStretch()
            lay.addLayout(row)

            root.addWidget(grp)
            self._spins[key] = (h_spin, v_spin)

        btn_row = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.setFixedHeight(32)
        save_btn.setStyleSheet(BTN_PRIMARY)
        save_btn.clicked.connect(self._save)
        btn_row.addStretch()
        btn_row.addWidget(save_btn)
        root.addLayout(btn_row)
        root.addStretch()

    def _save(self):
        for key, (h_spin, v_spin) in self._spins.items():
            save_label_offset(key, h_spin.value(), v_spin.value())
        QMessageBox.information(self, "保存完了", "印刷位置補正値を保存しました。")
        self.accept()
