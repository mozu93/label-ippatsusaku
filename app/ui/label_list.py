# -*- coding: utf-8 -*-
"""
宛名ラベル一覧画面
"""
from datetime import datetime

import os

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QStyle, QStyleOptionButton, QApplication,
    QLineEdit, QComboBox, QStackedWidget,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.database.models import get_session, LabelBatch
from app.ui.pagination_bar import PaginationBar
from app.ui.theme import (
    BTN_PRIMARY, BTN_DANGER, BTN_OUTLINE,
    TABLE_STYLE, PAGE_TITLE_STYLE, PAGE_MARGIN,
    C_TEXT_SUB, BTN_H, BTN_H_SM, ROW_H,
    font_page_title, C_SUCCESS,
)
from app.ui.widgets import CheckableHeader, MODE_LABEL

COL_CHK  = 0
COL_ID   = 1
COL_NAME = 2
COL_CNT  = 3
COL_MODE = 4
COL_DATE = 5
COL_OPS  = 6


class LabelListWidget(QWidget):
    """宛名ラベル一覧"""

    _BASE_HEADERS = ["", "ID", "ラベル名", "件数", "モード", "作成日時", "操作"]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._batches: list[LabelBatch] = []
        self._filtered: list[LabelBatch] = []
        self._filtered_counts: dict = {}
        self._last_chk_row: int | None = None
        self._sort_col: int | None = None
        self._sort_asc: bool = True
        self._init_ui()
        self._load()

    # ── UI 構築 ────────────────────────────────────────────────────────

    def _init_ui(self):
        layout = QVBoxLayout(self)
        l, t, r, b = PAGE_MARGIN
        layout.setContentsMargins(l, t, r, b)
        layout.setSpacing(12)

        # ── ヘッダー行 ────────────────────────────────────────────────
        toolbar = QHBoxLayout()
        title_lbl = QLabel("ラベル一発作成")
        title_lbl.setFont(font_page_title())
        title_lbl.setStyleSheet(PAGE_TITLE_STYLE)
        toolbar.addWidget(title_lbl)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        # ── 何を作りますか？カード ────────────────────────────────────
        start_lbl = QLabel("何を作りますか？")
        start_lbl.setStyleSheet("font-size: 13px; font-weight: bold; color: #334155;")
        layout.addWidget(start_lbl)

        cards_row = QHBoxLayout()
        cards_row.setSpacing(8)

        _CARDS = [
            ("📬", "宛名ラベル\n（氏名あり）",   "normal",    "#EFF6FF", "#1565C0"),
            ("📮", "宛名ラベル\n（氏名なし）",   "no_person", "#EFF6FF", "#1565C0"),
            ("🏢", "事業所名のみ",               "simple",    "#F0FDF4", "#2E7D32"),
            ("🪪", "名札",                       "nametag",   "#FFF7ED", "#C2410C"),
            ("🪧", "卓上プレート",               "split4",    "#FAF5FF", "#6D28D9"),
        ]

        for icon, label, mode, bg, fg in _CARDS:
            card = QPushButton(f"{icon}\n{label}")
            card.setFixedHeight(72)
            card.setFixedWidth(130)
            card.setStyleSheet(
                f"QPushButton {{ background: {bg}; color: {fg}; "
                f"border: 1px solid {fg}44; border-radius: 8px; "
                f"font-size: 12px; font-family: 'Meiryo UI'; "
                f"text-align: center; padding: 4px; }}"
                f"QPushButton:hover {{ background: {fg}22; border-color: {fg}; }}"
                f"QPushButton:pressed {{ background: {fg}33; }}"
            )
            card.clicked.connect(lambda _, m=mode: self._open_new(mode=m))
            cards_row.addWidget(card)

        cards_row.addStretch()
        layout.addLayout(cards_row)

        # ── 検索・フィルターバー ─────────────────────────────────────
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(8)

        self._search_edit = QLineEdit()
        self._search_edit.setPlaceholderText("🔍  ラベル名で検索...")
        self._search_edit.setFixedHeight(32)
        self._search_edit.setStyleSheet(
            "QLineEdit { border: 1px solid #CBD5E1; border-radius: 4px; "
            "padding: 0 10px; font-size: 13px; background: white; }"
            "QLineEdit:focus { border-color: #1565C0; }"
        )
        self._search_edit.setClearButtonEnabled(True)
        self._search_edit.textChanged.connect(self._apply_filter)

        self._mode_filter = QComboBox()
        self._mode_filter.setFixedHeight(32)
        self._mode_filter.setFixedWidth(160)
        self._mode_filter.setStyleSheet(
            "QComboBox { border: 1px solid #CBD5E1; border-radius: 4px; "
            "padding: 0 8px; font-size: 13px; background: white; }"
            "QComboBox:focus { border-color: #1565C0; }"
            "QComboBox::drop-down { border: none; width: 24px; }"
        )
        self._mode_filter.addItem("モード: すべて", "")
        for key, label in MODE_LABEL.items():
            self._mode_filter.addItem(label, key)
        self._mode_filter.currentIndexChanged.connect(self._apply_filter)

        filter_bar.addWidget(self._search_edit)
        filter_bar.addWidget(self._mode_filter)
        layout.addLayout(filter_bar)

        # ── 一括削除バー ──────────────────────────────────────────────
        bulk_bar = QHBoxLayout()
        self._btn_bulk_del = QPushButton("チェックした項目を削除")
        self._btn_bulk_del.setFixedHeight(BTN_H_SM)
        self._btn_bulk_del.setStyleSheet(BTN_DANGER)
        self._btn_bulk_del.setEnabled(False)
        self._btn_bulk_del.clicked.connect(self._bulk_delete)
        bulk_bar.addStretch()
        bulk_bar.addWidget(self._btn_bulk_del)
        layout.addLayout(bulk_bar)

        # ── テーブル ─────────────────────────────────────────────────
        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(
            ["", "ID", "ラベル名", "件数", "モード", "作成日時", "操作"]
        )
        self._chk_header = CheckableHeader(self.table)
        self._chk_header.toggled.connect(self._on_header_toggled)
        self._chk_header.sort_requested.connect(self._on_sort)
        self.table.setHorizontalHeader(self._chk_header)
        self._chk_header.setStretchLastSection(False)

        hdr = self.table.horizontalHeader()
        hdr.setSectionResizeMode(COL_CHK,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_ID,   QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_NAME, QHeaderView.ResizeMode.Stretch)
        hdr.setSectionResizeMode(COL_CNT,  QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_MODE, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_DATE, QHeaderView.ResizeMode.Fixed)
        hdr.setSectionResizeMode(COL_OPS,  QHeaderView.ResizeMode.Fixed)
        self.table.setColumnWidth(COL_CHK,  32)
        self.table.setColumnWidth(COL_ID,   50)
        self.table.setColumnWidth(COL_CNT,  60)
        self.table.setColumnWidth(COL_MODE, 110)
        self.table.setColumnWidth(COL_DATE, 145)
        self.table.setColumnWidth(COL_OPS,  210)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(42)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.setStyleSheet(TABLE_STYLE + """
            QScrollBar:vertical { width: 8px; background: #F0F0F0; border: none; }
            QScrollBar::handle:vertical { background: #CBD5E1; border-radius: 4px; min-height: 40px; }
            QScrollBar::handle:vertical:hover { background: #94A3B8; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0px; }
        """)
        self.table.itemClicked.connect(self._on_item_clicked)
        self.table.doubleClicked.connect(self._on_double_click)

        # ── Empty State ───────────────────────────────────────────────
        self._empty_widget = self._build_empty_state()

        # ── スタック（テーブル ↔ Empty State） ──────────────────────
        self._stack = QStackedWidget()
        self._stack.addWidget(self.table)          # index 0
        self._stack.addWidget(self._empty_widget)  # index 1
        layout.addWidget(self._stack)

        # ── ページネーション ──────────────────────────────
        self._pagination = PaginationBar()
        self._pagination.changed.connect(self._render_page)
        layout.addWidget(self._pagination)

    def _build_empty_state(self) -> QWidget:
        """データゼロ時に表示する Empty State ウィジェット"""
        w = QWidget()
        v = QVBoxLayout(w)
        v.setAlignment(Qt.AlignmentFlag.AlignCenter)
        v.setSpacing(12)

        icon_lbl = QLabel("📋")
        icon_lbl.setStyleSheet("font-size: 48px;")
        icon_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_title = QLabel("まだラベルがありません")
        self._empty_title.setStyleSheet(
            "font-size: 16px; font-weight: bold; color: #334155;"
        )
        self._empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_sub = QLabel("「＋ 新規作成」からラベルを作成できます")
        self._empty_sub.setStyleSheet("font-size: 13px; color: #64748B;")
        self._empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self._empty_btn = QPushButton("＋ 新規作成")
        self._empty_btn.setFixedHeight(36)
        self._empty_btn.setFixedWidth(160)
        self._empty_btn.setStyleSheet(
            "QPushButton { background: #1565C0; color: white; border-radius: 4px; "
            "border: none; font-size: 13px; padding: 0 16px; }"
            "QPushButton:hover { background: #1976D2; }"
        )

        v.addWidget(icon_lbl)
        v.addWidget(self._empty_title)
        v.addWidget(self._empty_sub)
        v.addSpacing(4)
        v.addWidget(self._empty_btn, alignment=Qt.AlignmentFlag.AlignCenter)
        return w

    # ── データ読み込み ─────────────────────────────────────────────────

    def _load(self):
        self._last_chk_row = None
        session = get_session()
        try:
            self._batches = (
                session.query(LabelBatch)
                .order_by(LabelBatch.created_at.desc())
                .all()
            )
            counts = {b.id: len(b.entries) for b in self._batches}
            session.expunge_all()
        finally:
            session.close()

        self._chk_header.set_checked(False)
        self._filtered_counts = counts
        self._sort_col = None
        self._sort_asc = True
        self._update_sort_headers()
        # 検索・フィルターを再適用（リロード後もフィルター状態を維持）
        self._apply_filter()

    def _apply_filter(self):
        """検索テキストとモードフィルターに基づいて一覧を絞り込む"""
        keyword = self._search_edit.text().strip().lower()
        mode_key = self._mode_filter.currentData()

        self._filtered = [
            b for b in self._batches
            if (not keyword or keyword in (b.batch_name or "").lower())
            and (not mode_key or b.label_mode == mode_key)
        ]

        self._chk_header.set_checked(False)
        self._pagination.reset()
        self._pagination.set_total(len(self._filtered))
        self._render_page()
        self._update_statusbar()

    def _update_statusbar(self):
        """メインウィンドウのステータスバーにバッチ件数を表示する"""
        win = self.window()
        if not hasattr(win, "set_status"):
            return
        total    = len(self._batches)
        filtered = len(self._filtered)
        if total == 0:
            win.set_status("ラベルバッチはまだありません")
        elif filtered == total:
            win.set_status(f"ラベルバッチ: {total} 件")
        else:
            win.set_status(f"ラベルバッチ: {total} 件中 {filtered} 件表示中")

    def _on_sort(self, col: int):
        if col in (COL_CHK, COL_OPS):
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True
        if col == COL_ID:
            key = lambda b: b.id
        elif col == COL_NAME:
            key = lambda b: (b.batch_name or "").lower()
        elif col == COL_CNT:
            key = lambda b: self._filtered_counts.get(b.id, 0)
        elif col == COL_MODE:
            key = lambda b: MODE_LABEL.get(b.label_mode, b.label_mode or "")
        elif col == COL_DATE:
            key = lambda b: b.created_at or datetime.min
        else:
            return
        self._filtered.sort(key=key, reverse=not self._sort_asc)
        self._update_sort_headers()
        self._pagination.reset()
        self._pagination.set_total(len(self._filtered))
        self._render_page()

    def _update_sort_headers(self):
        for col, base in enumerate(self._BASE_HEADERS):
            if col == self._sort_col:
                label = base + (" ▲" if self._sort_asc else " ▼")
            else:
                label = base
            item = self.table.horizontalHeaderItem(col)
            if item:
                item.setText(label)
            else:
                self.table.setHorizontalHeaderItem(col, QTableWidgetItem(label))

    def _render_page(self):
        start, end = self._pagination.slice_range()
        self._render(self._filtered_counts, self._filtered[start:end])
        self._update_empty_state()

    def _render(self, counts: dict, batches: list | None = None):
        self.table.setRowCount(0)
        display_batches = batches if batches is not None else self._batches

        for b in display_batches:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # チェックボックス列
            chk_item = QTableWidgetItem()
            chk_item.setFlags(Qt.ItemFlag.ItemIsUserCheckable | Qt.ItemFlag.ItemIsEnabled)
            chk_item.setCheckState(Qt.CheckState.Unchecked)
            chk_item.setData(Qt.ItemDataRole.UserRole, b.id)
            self.table.setItem(row, COL_CHK, chk_item)

            created = (
                b.created_at.strftime("%Y-%m-%d %H:%M")
                if isinstance(b.created_at, datetime) else str(b.created_at or "")
            )
            for col, val in zip(
                [COL_ID, COL_NAME, COL_CNT, COL_MODE, COL_DATE],
                [str(b.id), b.batch_name or "",
                 str(counts.get(b.id, 0)),
                 MODE_LABEL.get(b.label_mode, b.label_mode or ""),
                 created],
            ):
                item = QTableWidgetItem(val)
                item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
                if col == COL_CNT:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, col, item)

            # 操作ボタン
            ops = QWidget()
            ops_layout = QHBoxLayout(ops)
            ops_layout.setContentsMargins(4, 6, 4, 6)
            ops_layout.setSpacing(4)

            btn_open = QPushButton("開く")
            btn_open.setStyleSheet(BTN_OUTLINE)
            btn_open.setToolTip("ダブルクリックでも開けます")
            btn_open.clicked.connect(lambda _, bid=b.id: self._open_batch(bid))

            # PDF再オープンボタン（保存済みPDFが存在する場合のみ有効）
            btn_pdf = QPushButton("PDF")
            pdf_exists = bool(b.pdf_path and os.path.isfile(b.pdf_path))
            btn_pdf.setEnabled(pdf_exists)
            btn_pdf.setStyleSheet(
                f"QPushButton {{ background: {'#E8F5E9' if pdf_exists else '#F5F5F5'}; "
                f"color: {'#2E7D32' if pdf_exists else '#BDBDBD'}; "
                f"border: 1px solid {'#A5D6A7' if pdf_exists else '#E0E0E0'}; "
                f"border-radius: 4px; font-size: 12px; padding: 0 8px; }}"
                f"QPushButton:hover:enabled {{ background: #C8E6C9; }}"
            )
            btn_pdf.setToolTip(b.pdf_path if pdf_exists else "PDFがまだ出力されていません")
            btn_pdf.clicked.connect(lambda _, p=b.pdf_path: self._open_pdf(p))

            btn_del = QPushButton("削除")
            btn_del.setStyleSheet(BTN_DANGER)
            btn_del.clicked.connect(lambda _, bid=b.id: self._delete(bid))

            ops_layout.addWidget(btn_open)
            ops_layout.addWidget(btn_pdf)
            ops_layout.addWidget(btn_del)
            self.table.setCellWidget(row, COL_OPS, ops)

        self._update_bulk_btn()

    # ── チェック操作 ───────────────────────────────────────────────────

    def _on_item_clicked(self, item):
        if item.column() != COL_CHK:
            return
        row = item.row()
        modifiers = QApplication.keyboardModifiers()
        if (modifiers & Qt.KeyboardModifier.ShiftModifier) and self._last_chk_row is not None:
            new_state = item.checkState()
            r0, r1 = sorted([self._last_chk_row, row])
            for r in range(r0, r1 + 1):
                it = self.table.item(r, COL_CHK)
                if it:
                    it.setCheckState(new_state)
        self._last_chk_row = row
        self._update_bulk_btn()

    def _on_header_toggled(self, checked: bool):
        state = Qt.CheckState.Checked if checked else Qt.CheckState.Unchecked
        self._last_chk_row = None
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_CHK)
            if item:
                item.setCheckState(state)
        self._update_bulk_btn()

    def _get_checked_ids(self) -> list[int]:
        ids = []
        for row in range(self.table.rowCount()):
            item = self.table.item(row, COL_CHK)
            if item and item.checkState() == Qt.CheckState.Checked:
                ids.append(item.data(Qt.ItemDataRole.UserRole))
        return ids

    def _update_bulk_btn(self):
        self._btn_bulk_del.setEnabled(bool(self._get_checked_ids()))

    def _update_empty_state(self):
        """データがゼロのときは Empty State を表示し、テーブルを隠す"""
        has_filter = bool(
            self._search_edit.text().strip()
            or self._mode_filter.currentData()
        )
        if not self._filtered:
            if has_filter:
                self._empty_title.setText("検索結果がありません")
                self._empty_sub.setText("検索条件を変更するか、フィルターをクリアしてください")
                self._empty_btn.setText("フィルターをクリア")
                try:
                    self._empty_btn.clicked.disconnect()
                except RuntimeError:
                    pass
                self._empty_btn.clicked.connect(self._clear_filter)
            else:
                self._empty_title.setText("まだラベルがありません")
                self._empty_sub.setText("「＋ 新規作成」からラベルを作成できます")
                self._empty_btn.setText("＋ 新規作成")
                try:
                    self._empty_btn.clicked.disconnect()
                except RuntimeError:
                    pass
                self._empty_btn.clicked.connect(self._open_new)
            self._stack.setCurrentIndex(1)
            self._pagination.setVisible(False)
        else:
            self._stack.setCurrentIndex(0)
            self._pagination.setVisible(True)

    def _clear_filter(self):
        """検索・フィルターをリセット"""
        self._search_edit.clear()
        self._mode_filter.setCurrentIndex(0)

    # ── ダイアログ操作 ────────────────────────────────────────────────────

    def _on_double_click(self, index):
        chk_item = self.table.item(index.row(), COL_CHK)
        if chk_item is None:
            return
        batch_id = chk_item.data(Qt.ItemDataRole.UserRole)
        if batch_id is not None:
            self._open_batch(batch_id)

    def _open_new(self, mode: str = "normal"):
        from app.ui.direct_label_dialog import DirectLabelDialog
        dlg = DirectLabelDialog(parent=self, initial_mode=mode)
        dlg.exec()
        self._load()

    def _open_batch(self, batch_id: int):
        from app.ui.direct_label_dialog import DirectLabelDialog
        dlg = DirectLabelDialog(batch_id=batch_id, parent=self)
        dlg.exec()
        self._load()

    def _open_pdf(self, pdf_path: str):
        """保存済みPDFをOSの既定アプリで開く"""
        if not pdf_path or not os.path.isfile(pdf_path):
            QMessageBox.warning(self, "PDFが見つかりません",
                                f"ファイルが存在しません:\n{pdf_path}")
            return
        try:
            os.startfile(os.path.normpath(pdf_path))
        except Exception as e:
            QMessageBox.warning(self, "PDFを開けません", str(e))

    # ── 削除 ──────────────────────────────────────────────────────────

    def _delete(self, batch_id: int):
        reply = QMessageBox.question(
            self, "削除確認",
            "このラベルを削除しますか？\n（関連する宛名データもすべて削除されます）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._delete_ids([batch_id])

    def _bulk_delete(self):
        ids = self._get_checked_ids()
        if not ids:
            return
        reply = QMessageBox.question(
            self, "一括削除確認",
            f"チェックした {len(ids)} 件のラベルを削除しますか？\n"
            "（関連する宛名データもすべて削除されます）",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._delete_ids(ids)

    def _delete_ids(self, ids: list[int]):
        session = get_session()
        try:
            for bid in ids:
                b = session.get(LabelBatch, bid)
                if b:
                    session.delete(b)
            session.commit()
        except Exception as e:
            session.rollback()
            QMessageBox.critical(self, "エラー", f"削除に失敗しました：\n{e}")
        finally:
            session.close()
        self._load()
