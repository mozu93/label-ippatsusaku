# -*- coding: utf-8 -*-
import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont, QIcon
from app.database.models import init_db
from app.ui.main_window import MainWindow


def _app_icon() -> QIcon:
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(base, "assets", "app_icon.ico")
    return QIcon(path) if os.path.exists(path) else QIcon()


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Meiryo UI", 10))
    app.setWindowIcon(_app_icon())
    init_db()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
