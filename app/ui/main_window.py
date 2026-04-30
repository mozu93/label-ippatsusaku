# -*- coding: utf-8 -*-
import os
import sys
import webbrowser

from PyQt6.QtWidgets import QMainWindow, QWidget, QVBoxLayout, QMessageBox
from PyQt6.QtGui import QAction

from app.ui.update_banner import UpdateBanner
from app.ui.label_list import LabelListWidget
from app.version import __version__


def _manual_path() -> str:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    return os.path.join(base, "docs", "manual", "manual.html")


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ラベル一発作成")
        self.resize(1000, 680)
        self.setMinimumSize(800, 500)

        self._setup_menu()

        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._banner = UpdateBanner(self)
        layout.addWidget(self._banner)

        self._label_list = LabelListWidget(self)
        layout.addWidget(self._label_list)

    def _setup_menu(self):
        menubar = self.menuBar()
        help_menu = menubar.addMenu("ヘルプ")

        act_manual = QAction("マニュアルを開く", self)
        act_manual.triggered.connect(self._open_manual)
        help_menu.addAction(act_manual)

        help_menu.addSeparator()

        act_about = QAction("バージョン情報", self)
        act_about.triggered.connect(self._show_about)
        help_menu.addAction(act_about)

    def _open_manual(self):
        path = _manual_path()
        if os.path.exists(path):
            webbrowser.open(f"file:///{path.replace(os.sep, '/')}")
        else:
            QMessageBox.warning(self, "マニュアル", "マニュアルファイルが見つかりませんでした。")

    def _show_about(self):
        QMessageBox.about(
            self,
            "バージョン情報",
            f"<b>ラベル一発作成</b><br>"
            f"バージョン {__version__}<br><br>"
            f"宛名ラベル・名札・卓上プレートを<br>"
            f"素早くPDF出力するアプリです。",
        )
