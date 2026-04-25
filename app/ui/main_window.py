# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from app.ui.update_banner import UpdateBanner
from app.ui.label_list import LabelListWidget


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ラベル一発作成")
        self.resize(1000, 680)
        self.setMinimumSize(800, 500)

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._banner = UpdateBanner(self)
        layout.addWidget(self._banner)

        self._label_list = LabelListWidget(self)
        layout.addWidget(self._label_list)
