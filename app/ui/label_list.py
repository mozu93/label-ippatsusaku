# -*- coding: utf-8 -*-
"""
宛名ラベル一覧画面
"""
from datetime import datetime

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QTableWidget, QTableWidgetItem,
    QHeaderView, QMessageBox, QStyle, QStyleOptionButton, QApplication,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QFont

from app.database.models import get_session, LabelBatch
from app.ui.pagination_bar import PaginationBar
from app.ui.theme import (
    BTN_PRIMARY, BTN_DANGER,
    TABLE_STYLE, PAGE_TITLE_STYLE, PAGE_MARGIN,
    C_TEXT_SUB, BTN_H, BTN_H_SM, ROW_H,
    font_page_title,
)

COL_CHK  = 0
COL_ID   = 1
COL_NAME = 2
COL_CNT  = 3
COL_MODE = 4
COL_DATE = 5
COL_OPS  = 6


class _CheckableHeader(QHeaderView):
    """列0にチェックボックスを描画するカスタムヘッダー"""
    toggled = pyqtSignal(bool)

    def __init__(self, parent=None):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = False
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool):
        self._checked = checked
        self.viewport().update()

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()
        if logical_index == 0:
            opt = QStyleOptionButton()
            cb = 14
            opt.rect = QRect(
                rect.x() + (rect.width() - cb) // 2,
                rect.y() + (rect.height() - cb) // 2,
                cb, cb,
            )
            opt.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active
            opt.state |= (QStyle.StateFlag.State_On if self._checked
                          else QStyle.StateFlag.State_Off)
            self.style().drawControl(QStyle.ControlElement.CE_CheckBox, opt, painter)

    def mousePressEvent(self, event):
        idx = self.logicalIndexAt(event.pos())
        if idx == 0:
            self._checked = not self._checked
            self.viewport().update()
            self.toggled.emit(self._checked)
        else:
            super().mousePressEvent(event)


class LabelListWidget(QWidget):
    """宛名ラベル一覧"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._batches: list[LabelBatch] = []
        self._filtered: list[LabelBatch] = []
        self._filtered_counts: dict = {}
        self._last_chk_row: int | None = None
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
        title_lbl = QLabel("宛名ラベル")
        title_lbl.setFont(font_page_title())
        title_lbl.setStyleSheet(PAGE_TITLE_STYLE)

        btn_direct = QPushButton("＋ 新規作成")
        btn_direct.setFixedHeight(BTN_H)
        btn_direct.setStyleSheet(BTN_PRIMARY)
        btn_direct.setToolTip(
            "取引先マスタを使わず、貼り付けたデータ（企業名・住所・肩書・氏名）を\n"
            "そのままラベルに出力します。"
        )
        btn_direct.clicked.connect(self._open_new)

        toolbar.addWidget(title_lbl)
        toolbar.addStretch()
        toolbar.addWidget(btn_direct)
        layout.addLayout(toolbar)

        # ── 説明テキスト ────────────────────────────────────────────
        desc = QLabel(
            "企業名・住所・所属・役職・氏名を貼り付けてラベルを作成します。"
            "取引先マスタへの登録は不要です。郵便番号は住所から自動補完できます（インターネット接続必要）。"
        )
        desc.setStyleSheet(f"color: {C_TEXT_SUB}; font-size: 12px;")
        desc.setWordWrap(True)
        layout.addWidget(desc)

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
        self._chk_header = _CheckableHeader(self.table)
        self._chk_header.toggled.connect(self._on_header_toggled)
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
        self.table.setColumnWidth(COL_OPS,  80)
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
        layout.addWidget(self.table)

        # ── ページネーション ──────────────────────────────
        self._pagination = PaginationBar()
        self._pagination.changed.connect(self._render_page)
        layout.addWidget(self._pagination)

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
        self._filtered = list(self._batches)
        self._pagination.reset()
        self._pagination.set_total(len(self._filtered))
        self._render_page()

    def _render_page(self):
        start, end = self._pagination.slice_range()
        self._render(self._filtered_counts, self._filtered[start:end])

    def _render(self, counts: dict, batches: list | None = None):
        self.table.setRowCount(0)
        MODE_LABEL = {
            "normal":    "宛名(氏名あり)",
            "no_person": "宛名(氏名なし)",
            "simple":    "事業所名のみ",
            "nametag":   "名札",
            "split4":    "卓上プレート",
        }
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

            btn_del = QPushButton("削除")
            btn_del.setStyleSheet(BTN_DANGER)
            btn_del.clicked.connect(lambda _, bid=b.id: self._delete(bid))

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

    # ── ダイアログ操作 ────────────────────────────────────────────────────

    def _on_double_click(self, index):
        chk_item = self.table.item(index.row(), COL_CHK)
        if chk_item is None:
            return
        batch_id = chk_item.data(Qt.ItemDataRole.UserRole)
        if batch_id is not None:
            self._open_batch(batch_id)

    def _open_new(self):
        from app.ui.direct_label_dialog import DirectLabelDialog
        dlg = DirectLabelDialog(parent=self)
        dlg.exec()
        self._load()

    def _open_batch(self, batch_id: int):
        from app.ui.direct_label_dialog import DirectLabelDialog
        dlg = DirectLabelDialog(batch_id=batch_id, parent=self)
        dlg.exec()
        self._load()

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
