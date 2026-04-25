# -*- coding: utf-8 -*-
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QFont
from app.database.models import init_db
from app.ui.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setFont(QFont("Meiryo UI", 10))
    init_db()
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
