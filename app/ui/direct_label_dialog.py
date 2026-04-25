# -*- coding: utf-8 -*-
"""
宛名ラベル新規作成ダイアログ
（貼り付け / CSV → テーブル編集 → PDF 出力）
"""
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QPushButton, QLabel, QButtonGroup, QRadioButton,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
    QComboBox,
    QDialogButtonBox, QPlainTextEdit, QStyledItemDelegate,
    QAbstractItemDelegate,
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

from app.database.models import get_session, LabelBatch, LabelEntry
from app.utils.label_import import (
    parse_direct_csv_bytes, parse_raw_clipboard,
    DirectRow,
    _normalize, _DIR_COMPANY, _DIR_POSTAL, _DIR_ADDR1, _DIR_TITLE, _DIR_PERSON,
    _FALLBACK_COLS,
)
from app.services.label_pdf_service import (
    generate_label_pdf, LABEL_LAYOUTS, DEFAULT_LAYOUT_KEY,
    FONT_OPTIONS, DEFAULT_FONT_KEY,
)
from app.utils.app_config import (
    get_label_save_path,
    get_direct_label_save_path, set_direct_label_save_path,
)

_BTN_PRIMARY = (
    "QPushButton { background: #1565C0; color: white; border-radius: 4px; "
    "padding: 0 20px; font-size: 13px; min-height: 34px; }"
    "QPushButton:hover { background: #1976D2; }"
    "QPushButton:disabled { background: #BDBDBD; }"
)
_BTN_SECONDARY = (
    "QPushButton { background: white; color: #1565C0; border: 1px solid #1565C0; "
    "border-radius: 4px; padding: 0 20px; font-size: 13px; min-height: 34px; }"
    "QPushButton:hover { background: #E3F2FD; }"
    "QPushButton:disabled { color: #BDBDBD; border-color: #BDBDBD; }"
)
_BTN_DANGER = (
    "QPushButton { background: #D32F2F; color: white; border-radius: 4px; "
    "padding: 0 16px; font-size: 12px; min-height: 28px; }"
    "QPushButton:hover { background: #B71C1C; }"
)


class _MultilineDelegate(QStyledItemDelegate):
    """Alt+Enter で改行を挿入できる企業名セル用デリゲート"""

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        return editor

    def setEditorData(self, editor, index):
        editor.setPlainText(index.data(Qt.ItemDataRole.EditRole) or "")
        editor.selectAll()

    def setModelData(self, editor, model, index):
        model.setData(index, editor.toPlainText(), Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)

    def displayText(self, value, locale):
        return (value or "").replace("\n", " ｜ ")

    def eventFilter(self, obj, event):
        if isinstance(obj, QPlainTextEdit) and event.type() == event.Type.KeyPress:
            key  = event.key()
            mods = event.modifiers()
            if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                if mods & Qt.KeyboardModifier.AltModifier:
                    obj.insertPlainText("\n")
                    return True
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QAbstractItemDelegate.EndEditHint.NoHint)
                return True
            if key == Qt.Key.Key_Tab:
                self.commitData.emit(obj)
                self.closeEditor.emit(obj, QAbstractItemDelegate.EndEditHint.NoHint)
                return True
        return super().eventFilter(obj, event)


class ColumnMappingDialog(QDialog):
    """貼り付けデータの列を各フィールドに対応付けるダイアログ"""

    _FIELDS = [
        ("company_name", "企業名",     True),
        ("postal_code",  "郵便番号",   False),
        ("address1",     "住所",       False),
        ("title",        "所属・役職", False),
        ("person_name",  "氏名",       False),
    ]

    def __init__(self, headers: list, preview_rows: list, parent=None):
        super().__init__(parent)
        self.setWindowTitle("列の対応を設定")
        self.setMinimumSize(720, 520)
        self._headers = headers
        self._preview_rows = preview_rows
        self._combos: dict = {}
        self._init_ui()
        self._auto_detect()

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        lbl_pre = QLabel("貼り付けデータのプレビュー（先頭 5 行）")
        lbl_pre.setStyleSheet("font-weight: bold;")
        root.addWidget(lbl_pre)

        self._preview_tbl = QTableWidget(len(self._preview_rows), len(self._headers))
        self._preview_tbl.setHorizontalHeaderLabels(self._headers)
        self._preview_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._preview_tbl.setMaximumHeight(170)
        self._preview_tbl.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(self._preview_rows):
            for c, val in enumerate(row):
                self._preview_tbl.setItem(r, c, QTableWidgetItem(val))
        root.addWidget(self._preview_tbl)

        lbl_map = QLabel("各フィールドに対応する列を選択してください")
        lbl_map.setStyleSheet("font-weight: bold; margin-top: 8px;")
        root.addWidget(lbl_map)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        choices = ["（使用しない）"] + self._headers

        for field_id, field_label, required in self._FIELDS:
            combo = QComboBox()
            combo.addItems(choices)
            suffix = " <span style='color:red'>*</span>" if required else ""
            lbl = QLabel(f"{field_label}{suffix}")
            lbl.setTextFormat(Qt.TextFormat.RichText)
            form.addRow(lbl, combo)
            self._combos[field_id] = combo

        root.addLayout(form)
        root.addStretch()

        btns = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        btns.button(QDialogButtonBox.StandardButton.Ok).setText("取込む")
        btns.button(QDialogButtonBox.StandardButton.Cancel).setText("キャンセル")
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        root.addWidget(btns)

    def _auto_detect(self):
        field_keys = {
            "company_name": _DIR_COMPANY,
            "postal_code":  _DIR_POSTAL,
            "address1":     _DIR_ADDR1,
            "title":        _DIR_TITLE,
            "person_name":  _DIR_PERSON,
        }
        used: set = set()
        matched = 0
        for field_id, keys in field_keys.items():
            norm_keys = {_normalize(k) for k in keys}
            for i, h in enumerate(self._headers):
                if _normalize(h) in norm_keys and i not in used:
                    self._combos[field_id].setCurrentIndex(i + 1)
                    used.add(i)
                    matched += 1
                    break

        if matched == 0:
            ncols = len(self._headers)
            field_order = _FALLBACK_COLS.get(ncols) or _FALLBACK_COLS.get(
                min(_FALLBACK_COLS.keys(), key=lambda k: abs(k - ncols))
            )
            if field_order:
                for col_idx, field_id in enumerate(field_order):
                    if col_idx < len(self._headers):
                        self._combos[field_id].setCurrentIndex(col_idx + 1)

    def _on_ok(self):
        if self._combos["company_name"].currentIndex() == 0:
            QMessageBox.warning(self, "入力エラー", "「企業名」列を選択してください。")
            return
        self.accept()

    def get_mapping(self) -> dict:
        result = {}
        for field_id, _, _ in self._FIELDS:
            idx = self._combos[field_id].currentIndex()
            result[field_id] = (idx - 1) if idx > 0 else None
        return result


class DirectLabelDialog(QDialog):
    """
    取引先マスタを使わず、貼り付け/CSV から直接ラベルを作成するダイアログ。

    入力列（ヘッダーあり推奨）:
      企業名 / 郵便番号 / 住所 / 肩書 / 氏名
    ヘッダーなしのフォールバック（列数で自動判定）:
      2列: 企業名, 氏名
      3列: 企業名, 肩書, 氏名
      4列: 企業名, 住所, 肩書, 氏名
      5列: 企業名, 郵便番号, 住所, 肩書, 氏名
      6列: 企業名, 郵便番号, 住所1, 住所2, 肩書, 氏名
    """

    _COLS = [
        ("企業名",    200, QHeaderView.ResizeMode.Stretch),
        ("郵便番号",   90, QHeaderView.ResizeMode.Fixed),
        ("住所",      250, QHeaderView.ResizeMode.Stretch),
        ("所属・役職", 120, QHeaderView.ResizeMode.Interactive),
        ("氏名",      120, QHeaderView.ResizeMode.Interactive),
    ]

    def __init__(self, batch_id: int | None = None, parent=None):
        super().__init__(parent)
        self._batch_id = batch_id
        self.setWindowTitle("宛名ラベル 新規作成")
        self.setMinimumSize(900, 580)
        self.resize(980, 640)
        self._init_ui()
        if batch_id is not None:
            self._load_batch(batch_id)

    def _init_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        banner = QLabel(
            "取引先マスタを使わず、貼り付けた内容をそのままラベルに出力します。<br>"
            "データは一時的なスナップショットとして保存され、マスタには反映されません。"
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background: #F0FDF4; border: 1px solid #86EFAC; "
            "border-radius: 4px; padding: 8px 12px; font-size: 12px; color: #166534;"
        )
        root.addWidget(banner)

        top_form = QHBoxLayout()
        top_form.setSpacing(16)
        mode_lbl = QLabel("モード")
        mode_lbl.setFixedWidth(44)
        self._radio_normal  = QRadioButton("通常（住所・氏名あり）")
        self._radio_simple  = QRadioButton("簡易（企業名のみ）")
        self._radio_nametag = QRadioButton("名札（氏名を大きく）")
        self._radio_split4  = QRadioButton("プレートモード（均等割付）")
        self._radio_normal.setChecked(True)
        grp = QButtonGroup(self)
        grp.addButton(self._radio_normal,  0)
        grp.addButton(self._radio_simple,  1)
        grp.addButton(self._radio_nametag, 2)
        grp.addButton(self._radio_split4,  3)
        self._radio_normal.toggled.connect(self._on_mode_toggled)
        self._radio_simple.toggled.connect(self._on_mode_toggled)
        self._radio_nametag.toggled.connect(self._on_mode_toggled)
        self._radio_split4.toggled.connect(self._on_mode_toggled)
        top_form.addWidget(mode_lbl)
        top_form.addWidget(self._radio_normal)
        top_form.addWidget(self._radio_simple)
        top_form.addWidget(self._radio_nametag)
        top_form.addWidget(self._radio_split4)
        top_form.addStretch()
        root.addLayout(top_form)

        ops = QHBoxLayout()
        ops.setSpacing(6)
        btn_paste = QPushButton("貼り付けから取込")
        btn_paste.setFixedHeight(32)
        btn_paste.setStyleSheet(_BTN_SECONDARY)
        btn_paste.setToolTip(
            "Excel からコピーしたデータを取込みます。\n"
            "推奨列順（ヘッダーあり）: 企業名 / 郵便番号 / 住所 / 所属・役職 / 氏名\n"
            "ヘッダーなしの場合は列数で自動判定します。"
        )
        btn_paste.clicked.connect(self._do_paste)

        btn_csv = QPushButton("CSV から取込")
        btn_csv.setFixedHeight(32)
        btn_csv.setStyleSheet(_BTN_SECONDARY)
        btn_csv.clicked.connect(self._do_csv)

        btn_add = QPushButton("＋ 行を追加")
        btn_add.setFixedHeight(32)
        btn_add.setStyleSheet(_BTN_SECONDARY)
        btn_add.clicked.connect(self._add_row)

        btn_del = QPushButton("選択行を削除")
        btn_del.setFixedHeight(32)
        btn_del.setStyleSheet(_BTN_DANGER)
        btn_del.clicked.connect(self._del_rows)

        btn_postal = QPushButton("郵便番号を自動入力")
        btn_postal.setFixedHeight(32)
        btn_postal.setStyleSheet(_BTN_SECONDARY)
        btn_postal.setToolTip(
            "住所が入力されていて郵便番号が空の行に、\n"
            "zipcloud API（インターネット接続必要）で郵便番号を補完します。"
        )
        btn_postal.clicked.connect(self._fill_postal_codes)

        hint = QLabel(
            "推奨列順（ヘッダーなし）: 企業名 → 郵便番号 → 住所 → 所属・役職 → 氏名"
            "　※所属・役職は省略可（4列: 企業名→郵便番号→住所→氏名）"
        )
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")

        ops.addWidget(btn_paste)
        ops.addWidget(btn_csv)
        ops.addWidget(btn_add)
        ops.addWidget(btn_del)
        ops.addWidget(btn_postal)
        ops.addStretch()
        ops.addWidget(hint)
        root.addLayout(ops)

        self._simple_banner = QLabel(
            "⚠  簡易モード：企業名のみ出力されます。住所・肩書・氏名は印刷されません。"
        )
        self._simple_banner.setStyleSheet(
            "background: #FFF3E0; color: #E65100; border: 1px solid #FFB74D; "
            "border-radius: 4px; padding: 6px 12px; font-size: 11px;"
        )
        self._simple_banner.setVisible(False)
        root.addWidget(self._simple_banner)

        self._nametag_banner = QLabel(
            "名札モード：氏名を大きく出力します。住所は印刷されません（A-ONE 51002 等に最適）。"
        )
        self._nametag_banner.setStyleSheet(
            "background: #EFF6FF; color: #1D4ED8; border: 1px solid #BFDBFE; "
            "border-radius: 4px; padding: 6px 12px; font-size: 11px;"
        )
        self._nametag_banner.setVisible(False)
        root.addWidget(self._nametag_banner)

        self._split4_banner = QLabel(
            "プレートモード：企業名を上下中央・均等割付で出力します。"
            "1・3番ラベルは自動的に 180° 回転します（A4 4長4分割用紙向け）。"
        )
        self._split4_banner.setStyleSheet(
            "background: #F0FDF4; color: #166534; border: 1px solid #86EFAC; "
            "border-radius: 4px; padding: 6px 12px; font-size: 11px;"
        )
        self._split4_banner.setVisible(False)
        root.addWidget(self._split4_banner)

        self.table = QTableWidget(0, len(self._COLS))
        self.table.setHorizontalHeaderLabels([c[0] for c in self._COLS])
        hdr = self.table.horizontalHeader()
        for i, (_, width, mode) in enumerate(self._COLS):
            hdr.setSectionResizeMode(i, mode)
            if mode == QHeaderView.ResizeMode.Fixed:
                self.table.setColumnWidth(i, width)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setItemDelegateForColumn(0, _MultilineDelegate(self.table))
        root.addWidget(self.table)

        foot = QHBoxLayout()
        self._count_lbl = QLabel("0 件")
        self._count_lbl.setStyleSheet("color: #64748B; font-size: 12px;")

        layout_lbl = QLabel("用紙:")
        layout_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        self._layout_combo = QComboBox()
        self._layout_combo.setFixedHeight(34)
        for key, layout_obj in LABEL_LAYOUTS.items():
            self._layout_combo.addItem(layout_obj.name, key)
        default_idx = self._layout_combo.findData(DEFAULT_LAYOUT_KEY)
        if default_idx >= 0:
            self._layout_combo.setCurrentIndex(default_idx)

        font_lbl = QLabel("フォント:")
        font_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        self._font_combo = QComboBox()
        self._font_combo.setFixedHeight(34)
        for key in FONT_OPTIONS:
            self._font_combo.addItem(key, key)
        font_idx = self._font_combo.findData(DEFAULT_FONT_KEY)
        if font_idx >= 0:
            self._font_combo.setCurrentIndex(font_idx)

        btn_cancel = QPushButton("閉じる")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            "QPushButton { color: #64748B; border: 1px solid #CBD5E1; "
            "border-radius: 4px; background: white; padding: 0 16px; }"
            "QPushButton:hover { background: #F1F5F9; }"
        )
        btn_cancel.clicked.connect(self.reject)

        self._btn_export = QPushButton("PDF を出力する")
        self._btn_export.setFixedHeight(36)
        self._btn_export.setStyleSheet(_BTN_PRIMARY)
        self._btn_export.clicked.connect(self._export)

        foot.addWidget(self._count_lbl)
        foot.addStretch()
        foot.addWidget(layout_lbl)
        foot.addWidget(self._layout_combo)
        foot.addSpacing(8)
        foot.addWidget(font_lbl)
        foot.addWidget(self._font_combo)
        foot.addSpacing(8)
        foot.addWidget(btn_cancel)
        foot.addWidget(self._btn_export)
        root.addLayout(foot)

    def _fill_postal_codes(self):
        from app.utils.postal_lookup import lookup_postal_code
        from PyQt6.QtWidgets import QApplication

        targets = [
            row for row in range(self.table.rowCount())
            if not (self.table.item(row, 1) or QTableWidgetItem()).text().strip()
            and (self.table.item(row, 2) or QTableWidgetItem()).text().strip()
        ]
        if not targets:
            QMessageBox.information(self, "郵便番号補完",
                                    "補完対象の行がありません。\n"
                                    "（郵便番号が空で住所が入力されている行が対象です）")
            return

        self._btn_export.setEnabled(False)
        filled = skipped = 0
        for row in targets:
            address = (self.table.item(row, 2) or QTableWidgetItem()).text().strip()
            QApplication.processEvents()
            zipcode = lookup_postal_code(address)
            if zipcode:
                item = self.table.item(row, 1)
                if item:
                    item.setText(zipcode)
                filled += 1
            else:
                skipped += 1

        self._btn_export.setEnabled(True)
        msg = f"{filled} 件の郵便番号を補完しました。"
        if skipped:
            msg += f"\n（{skipped} 件は住所から特定できませんでした）"
        QMessageBox.information(self, "郵便番号補完", msg)

    def _load_batch(self, batch_id: int):
        session = get_session()
        try:
            batch = session.get(LabelBatch, batch_id)
            if not batch:
                QMessageBox.warning(self, "エラー", "指定されたバッチが見つかりません。")
                return
            if batch.label_mode == "simple":
                self._radio_simple.setChecked(True)
            elif batch.label_mode == "nametag":
                self._radio_nametag.setChecked(True)
            elif batch.label_mode == "split4":
                self._radio_split4.setChecked(True)
            else:
                self._radio_normal.setChecked(True)
            entries = list(batch.entries)
            session.expunge_all()
        finally:
            session.close()

        self.table.setRowCount(0)
        for e in entries:
            addr = e.address1 or ""
            if e.address2:
                addr = addr + (" " if addr else "") + e.address2
            self._add_row([
                e.company_name or "",
                e.postal_code  or "",
                addr,
                e.title        or "",
                e.person_name  or "",
            ])

    def _on_mode_toggled(self, checked: bool):
        if not checked:
            return
        self._simple_banner.setVisible(self._radio_simple.isChecked())
        self._nametag_banner.setVisible(self._radio_nametag.isChecked())
        self._split4_banner.setVisible(self._radio_split4.isChecked())

    def _current_mode(self) -> str:
        if self._radio_simple.isChecked():
            return "simple"
        if self._radio_nametag.isChecked():
            return "nametag"
        if self._radio_split4.isChecked():
            return "split4"
        return "normal"

    def _add_row(self, values: list[str] | None = None):
        row = self.table.rowCount()
        self.table.insertRow(row)
        for col in range(len(self._COLS)):
            item = QTableWidgetItem(values[col] if values and col < len(values) else "")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)
        self._update_count()

    def _del_rows(self):
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        for r in rows:
            self.table.removeRow(r)
        self._update_count()

    def _update_count(self):
        self._count_lbl.setText(f"{self.table.rowCount()} 件")

    def _fill_rows(self, direct_rows):
        if not direct_rows:
            QMessageBox.information(self, "取込結果", "取込可能なデータがありませんでした。")
            return

        if self.table.rowCount() > 0:
            reply = QMessageBox.question(
                self, "取込方法の確認",
                f"現在 {self.table.rowCount()} 件のデータが入力されています。\n\n"
                "「上書き」: 現在のデータをすべて削除して取込む\n"
                "「追記」: 現在のデータの後ろに追加する",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            )
            if reply == QMessageBox.StandardButton.Cancel:
                return
            if reply == QMessageBox.StandardButton.Yes:
                self.table.setRowCount(0)

        for dr in direct_rows:
            self._add_row([
                dr.company_name,
                dr.postal_code,
                dr.address1 + (" " + dr.address2 if dr.address2 else ""),
                dr.title,
                dr.person_name,
            ])
        QMessageBox.information(self, "取込完了", f"{len(direct_rows)} 件を取り込みました。")

    def _do_paste(self):
        from PyQt6.QtWidgets import QApplication
        text = QApplication.clipboard().text()
        if not text.strip():
            QMessageBox.information(self, "貼り付け", "クリップボードにテキストがありません。")
            return
        try:
            headers, data_rows = parse_raw_clipboard(text)
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"貼り付けデータの解析に失敗しました：\n{e}")
            return
        if not headers:
            QMessageBox.information(self, "貼り付け", "取込可能なデータがありませんでした。")
            return

        dlg = ColumnMappingDialog(headers, data_rows[:5], self)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        mapping = dlg.get_mapping()
        rows = []
        for row in data_rows:
            def _get(field_id, _row=row):
                idx = mapping.get(field_id)
                return _row[idx] if idx is not None and idx < len(_row) else ""
            dr = DirectRow(
                company_name=_get("company_name"),
                postal_code =_get("postal_code"),
                address1    =_get("address1"),
                title       =_get("title"),
                person_name =_get("person_name"),
            )
            if dr.company_name:
                rows.append(dr)
        self._fill_rows(rows)

    def _do_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "CSV ファイルを選択", "", "CSV ファイル (*.csv);;すべてのファイル (*)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                rows = parse_direct_csv_bytes(f.read())
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"CSV 読み込みエラー：\n{e}")
            return
        self._fill_rows(rows)

    def _export(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "データなし", "出力するデータがありません。")
            return

        last_dir = (
            get_direct_label_save_path()
            or get_label_save_path()
            or os.path.expanduser("~/Documents")
        )
        default_name = ""
        if self._batch_id is not None:
            session = get_session()
            try:
                b = session.get(LabelBatch, self._batch_id)
                if b:
                    default_name = b.batch_name or ""
            finally:
                session.close()

        default_path = os.path.join(
            last_dir, f"{default_name}.pdf" if default_name else "宛名ラベル.pdf"
        )

        pdf_path, _ = QFileDialog.getSaveFileName(
            self, "ラベルを保存", default_path, "PDF ファイル (*.pdf)",
        )
        if not pdf_path:
            return
        if not pdf_path.lower().endswith(".pdf"):
            pdf_path += ".pdf"

        name     = os.path.splitext(os.path.basename(pdf_path))[0]
        dest_dir = os.path.dirname(pdf_path)
        mode     = self._current_mode()

        entry_dicts = []
        for row in range(self.table.rowCount()):
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            entry_dicts.append({
                "sort_order":   row,
                "client_id":    None,
                "company_name": _cell(0),
                "postal_code":  _cell(1),
                "address1":     _cell(2),
                "address2":     "",
                "title":        _cell(3),
                "person_name":  _cell(4),
                "entry_mode":   "inherit",
            })

        session = get_session()
        try:
            if self._batch_id is not None:
                batch = session.get(LabelBatch, self._batch_id)
                if batch:
                    batch.batch_name = name
                    batch.label_mode = mode
                    for old_e in list(batch.entries):
                        session.delete(old_e)
                    session.flush()
                else:
                    batch = LabelBatch(batch_name=name, label_mode=mode)
                    session.add(batch)
                    session.flush()
                    self._batch_id = batch.id
            else:
                batch = LabelBatch(batch_name=name, label_mode=mode)
                session.add(batch)
                session.flush()
                self._batch_id = batch.id
            for ed in entry_dicts:
                e = LabelEntry(batch_id=batch.id, **{k: v for k, v in ed.items()})
                session.add(e)
            session.commit()
            batch_id = batch.id

            orm_entries = (
                session.query(LabelEntry)
                .filter_by(batch_id=batch_id)
                .order_by(LabelEntry.sort_order)
                .all()
            )
            session.expunge_all()
        except Exception as ex:
            session.rollback()
            QMessageBox.critical(self, "保存エラー", f"DB 保存に失敗しました：\n{ex}")
            return
        finally:
            session.close()

        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        try:
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key)
        except Exception as ex:
            QMessageBox.critical(self, "PDF 出力エラー", f"PDF の生成に失敗しました：\n{ex}")
            return

        set_direct_label_save_path(dest_dir)

        _s = get_session()
        try:
            _b = _s.get(LabelBatch, self._batch_id)
            if _b:
                _b.pdf_path = os.path.normpath(pdf_path)
                _s.commit()
        except Exception:
            _s.rollback()
        finally:
            _s.close()

        reply = QMessageBox.question(
            self, "出力完了",
            f"PDF を出力しました。\n{pdf_path}\n\nファイルを開きますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                os.startfile(os.path.normpath(pdf_path))
            except Exception as ex:
                QMessageBox.warning(self, "ファイルを開けません",
                                    f"PDF を開けませんでした：\n{ex}")
