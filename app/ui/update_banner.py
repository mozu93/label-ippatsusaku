# -*- coding: utf-8 -*-
"""
アップデート通知バー。MainWindow の上部に差し込む。
状態: hidden → 「ダウンロード」ボタン → プログレスバー → 「今すぐ更新」ボタン
"""
from PyQt6.QtWidgets import (
    QWidget, QHBoxLayout, QLabel, QPushButton, QProgressBar,
)
from PyQt6.QtCore import QThread, pyqtSignal


class _VersionCheckThread(QThread):
    found = pyqtSignal(str, str)   # (tag_name, download_url)

    def run(self):
        from app.utils.updater import check_latest_version, is_newer_version
        from app.version import __version__
        result = check_latest_version()
        if result and is_newer_version(__version__, result["tag_name"]):
            self.found.emit(result["tag_name"], result["download_url"])


class _DownloadThread(QThread):
    progress = pyqtSignal(int, int)   # (received, total)
    finished = pyqtSignal(str)        # tmp_path
    failed   = pyqtSignal()

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self._url = url

    def run(self):
        from app.utils.updater import download_new_exe
        path = download_new_exe(self._url, progress_callback=self.progress.emit)
        if path:
            self.finished.emit(path)
        else:
            self.failed.emit()


class UpdateBanner(QWidget):
    """アップデート通知バー。新バージョンがなければ非表示のまま。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._download_url = ""
        self._tmp_exe_path = ""
        self._init_ui()
        self.setVisible(False)
        self._start_check()

    def _init_ui(self):
        self.setStyleSheet(
            "background: #FEF9C3; border-bottom: 1px solid #FDE047;"
        )
        self.setFixedHeight(40)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 0, 12, 0)

        self._lbl = QLabel()
        self._lbl.setStyleSheet("color: #713F12; font-size: 12px;")

        self._btn_dl = QPushButton("ダウンロード")
        self._btn_dl.setFixedHeight(28)
        self._btn_dl.setStyleSheet(
            "QPushButton { background: #1565C0; color: white; border-radius: 4px; "
            "padding: 0 12px; font-size: 12px; }"
            "QPushButton:hover { background: #1976D2; }"
        )
        self._btn_dl.clicked.connect(self._start_download)

        self._progress = QProgressBar()
        self._progress.setFixedHeight(20)
        self._progress.setVisible(False)

        self._btn_install = QPushButton("今すぐ更新して再起動")
        self._btn_install.setFixedHeight(28)
        self._btn_install.setStyleSheet(
            "QPushButton { background: #2E7D32; color: white; border-radius: 4px; "
            "padding: 0 12px; font-size: 12px; }"
            "QPushButton:hover { background: #388E3C; }"
        )
        self._btn_install.setVisible(False)
        self._btn_install.clicked.connect(self._install)

        layout.addWidget(self._lbl)
        layout.addStretch()
        layout.addWidget(self._btn_dl)
        layout.addWidget(self._progress)
        layout.addWidget(self._btn_install)

    def _start_check(self):
        self._check_thread = _VersionCheckThread(self)
        self._check_thread.found.connect(self._on_update_found)
        self._check_thread.start()

    def _on_update_found(self, tag: str, url: str):
        self._download_url = url
        self._lbl.setText(f"新しいバージョン {tag} が利用可能です")
        self.setVisible(True)

    def _start_download(self):
        self._btn_dl.setVisible(False)
        self._progress.setVisible(True)
        self._progress.setRange(0, 0)
        self._dl_thread = _DownloadThread(self._download_url, self)
        self._dl_thread.progress.connect(self._on_progress)
        self._dl_thread.finished.connect(self._on_download_done)
        self._dl_thread.failed.connect(self._on_download_failed)
        self._dl_thread.start()

    def _on_progress(self, received: int, total: int):
        if total > 0:
            self._progress.setRange(0, total)
            self._progress.setValue(received)

    def _on_download_done(self, tmp_path: str):
        self._tmp_exe_path = tmp_path
        self._progress.setVisible(False)
        self._lbl.setText("ダウンロード完了。アプリを再起動して更新します。")
        self._btn_install.setVisible(True)

    def _on_download_failed(self):
        self._progress.setVisible(False)
        self._btn_dl.setVisible(True)
        self._lbl.setText("ダウンロードに失敗しました。後で再試行してください。")

    def _install(self):
        import sys
        from app.utils.updater import launch_updater
        current_exe = sys.executable if getattr(sys, "frozen", False) else ""
        if not current_exe:
            from PyQt6.QtWidgets import QMessageBox
            QMessageBox.information(
                self, "開発環境",
                "開発環境では更新インストールを実行できません。\n"
                f"ダウンロード先: {self._tmp_exe_path}"
            )
            return
        launch_updater(self._tmp_exe_path, current_exe)
