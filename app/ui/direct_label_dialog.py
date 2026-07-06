# -*- coding: utf-8 -*-
"""
宛名ラベル新規作成ダイアログ
（貼り付け / CSV → テーブル編集 → PDF 出力）
"""
import os

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QButtonGroup,
    QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog,
    QComboBox, QLineEdit, QSpinBox,
    QApplication,
    QCheckBox, QWidget, QFrame, QMenu,
)
from PyQt6.QtCore import Qt, QEvent, QPoint
from PyQt6.QtGui import QBrush, QColor, QKeySequence, QShortcut, QAction

from app.database.models import get_session, LabelBatch, LabelEntry
from app.utils.label_import import parse_raw_csv_bytes, parse_raw_clipboard, DirectRow
from app.services.label_pdf_service import (
    generate_label_pdf, LABEL_LAYOUTS, DEFAULT_LAYOUT_KEY,
    FONT_OPTIONS, DEFAULT_FONT_KEY,
)
from app.ui.theme import (
    BTN_PRIMARY, BTN_OUTLINE,
    BTN_TB_OUTLINE, BTN_TB_DANGER,
    seg_btn_style, STEP_STYLES,
    INFO_BANNER,
    C_PRIMARY, C_TEXT_MUTED,
    FONT_FAMILY,
)
from app.ui.widgets import CheckableHeader, DraggableTable, MultilineDelegate
from app.ui.column_mapping_dialog import ColumnMappingDialog
from app.utils.app_config import (
    get_label_save_path,
    get_direct_label_save_path, set_direct_label_save_path,
    get_label_offset,
)



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

    COL_CHK      = 0
    COL_COMPANY  = 1
    COL_COMPANY2 = 2
    COL_KANA     = 3
    COL_TITLE    = 4
    COL_PERSON   = 5
    COL_POSTAL   = 6
    COL_ADDR1    = 7
    COL_ADDR2    = 8
    COL_BC_ADDR  = 9

    _REQUIRED_COLS: dict[str, set] = {
        "normal":    {COL_COMPANY, COL_PERSON, COL_ADDR1},
        "no_person": {COL_COMPANY, COL_ADDR1},
        "simple":    {COL_COMPANY},
        "nametag":   {COL_COMPANY, COL_PERSON},
        "split4":    {COL_COMPANY},
    }

    _COLS = [
        ("",              32,  QHeaderView.ResizeMode.Fixed),
        ("事業所名",      170, QHeaderView.ResizeMode.Stretch),
        ("事業所名2",     130, QHeaderView.ResizeMode.Interactive),
        ("フリガナ",      130, QHeaderView.ResizeMode.Interactive),
        ("所属・役職名",  130, QHeaderView.ResizeMode.Interactive),
        ("氏名",          120, QHeaderView.ResizeMode.Interactive),
        ("郵便番号",       90, QHeaderView.ResizeMode.Fixed),
        ("住所1",         180, QHeaderView.ResizeMode.Stretch),
        ("住所2",         130, QHeaderView.ResizeMode.Interactive),
        ("住所表示番号",  130, QHeaderView.ResizeMode.Fixed),
    ]

    def __init__(self, batch_id: int | None = None, parent=None, initial_mode: str = "normal"):
        super().__init__(parent)
        self._batch_id = batch_id
        self._last_chk_row: int | None = None
        self._sort_col: int | None = None
        self._sort_asc: bool = True
        self._loading_batch: bool = False
        self._undo_stack: list = []
        self.setWindowTitle("宛名ラベル 新規作成" if batch_id is None else "宛名ラベル 編集")
        self.setMinimumSize(940, 580)
        self.resize(1020, 640)
        self._init_ui()
        if batch_id is not None:
            self._load_batch(batch_id)
        elif initial_mode != "normal":
            self._set_initial_mode(initial_mode)

    def _init_ui(self) -> None:
        """ルートレイアウトを構築し、各セクションをヘルパーメソッドで組み立てる"""
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 16, 20, 16)
        root.setSpacing(10)

        root.addWidget(self._build_info_banner())
        root.addWidget(self._build_step_bar())
        root.addLayout(self._build_name_row())
        root.addLayout(self._build_mode_row())
        self._add_mode_banners(root)
        root.addLayout(self._build_toolbar())
        root.addWidget(self._build_table())
        root.addLayout(self._build_save_row())
        root.addLayout(self._build_footer())

    # ── UI 構築ヘルパー ─────────────────────────────────────────────────

    def _build_info_banner(self) -> QLabel:
        """最上部のインフォバナーを生成する"""
        banner = QLabel(
            "データ名を入力し、モードを選択してデータを取り込んでください。"
            "Excel からコピー（Ctrl+V）または CSV ファイルで取込できます。"
        )
        banner.setWordWrap(True)
        banner.setStyleSheet(
            "background: #F0FDF4; border: 1px solid #86EFAC; "
            "border-radius: 4px; padding: 6px 12px; font-size: 12px; color: #166534;"
        )
        return banner

    def _build_name_row(self) -> QHBoxLayout:
        """データ名入力行を生成する"""
        row = QHBoxLayout()
        row.setSpacing(8)

        name_lbl = QLabel("データ名")
        name_lbl.setStyleSheet("font-weight: bold; font-size: 13px;")
        name_lbl.setFixedWidth(60)

        self._data_name_edit = QLineEdit()
        self._data_name_edit.setPlaceholderText("例）〇〇部会、〇〇視察研修会")
        self._data_name_edit.setFixedHeight(34)
        self._data_name_edit.setStyleSheet(
            f"QLineEdit {{ border: 1px solid #D1D5DB; border-radius: 5px; "
            f"padding: 0 8px; font-size: 13px; font-family: '{FONT_FAMILY}'; }}"
            f"QLineEdit:focus {{ border-color: {C_PRIMARY}; }}"
        )
        row.addWidget(name_lbl)
        row.addWidget(self._data_name_edit)
        return row

    def _build_mode_row(self) -> QHBoxLayout:
        """モード選択セグメントボタン行を生成する"""
        row = QHBoxLayout()
        row.setSpacing(10)

        mode_lbl = QLabel("モード")
        mode_lbl.setStyleSheet(f"font-size: 12px; color: #475569;")
        mode_lbl.setFixedWidth(44)

        def _seg(label: str, pos: str) -> QPushButton:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setFixedHeight(30)
            btn.setStyleSheet(seg_btn_style(pos))
            return btn

        self._radio_normal    = _seg("宛名（氏名あり）",   "left")
        self._radio_no_person = _seg("宛名（氏名なし）",   "mid")
        self._radio_simple    = _seg("事業所名のみ",       "mid")
        self._radio_nametag   = _seg("名札",               "mid")
        self._radio_split4    = _seg("卓上プレート",       "right")
        self._radio_normal.setChecked(True)

        grp = QButtonGroup(self)
        grp.setExclusive(True)
        for i, btn in enumerate([
            self._radio_normal, self._radio_no_person,
            self._radio_simple, self._radio_nametag, self._radio_split4,
        ]):
            grp.addButton(btn, i)
            btn.toggled.connect(self._on_mode_toggled)

        seg_wrap = QWidget()
        seg_layout = QHBoxLayout(seg_wrap)
        seg_layout.setContentsMargins(0, 0, 0, 0)
        seg_layout.setSpacing(0)
        for btn in [
            self._radio_normal, self._radio_no_person,
            self._radio_simple, self._radio_nametag, self._radio_split4,
        ]:
            seg_layout.addWidget(btn)

        row.addWidget(mode_lbl)
        row.addWidget(seg_wrap)
        row.addStretch()
        return row

    def _add_mode_banners(self, root: QVBoxLayout) -> None:
        """5モードの説明バナーをルートに追加する（各モード切替で表示/非表示）"""
        def _banner(text: str, visible: bool) -> QLabel:
            lbl = QLabel(text)
            lbl.setWordWrap(True)
            lbl.setStyleSheet(INFO_BANNER)
            lbl.setVisible(visible)
            root.addWidget(lbl)
            return lbl

        self._normal_banner = _banner(
            "事業所名、郵便番号、住所、所属・役職、氏名を Excel からコピーするか、"
            "CSV ファイルで取り込んでください。"
            "郵便番号がわからない場合は住所から変換できます。（要インターネット接続）",
            visible=True,
        )
        self._no_person_banner = _banner(
            "事業所名・住所のみ出力します。氏名・所属・役職は印刷されません。"
            "「御中」が自動的に付きます。",
            visible=False,
        )
        self._simple_banner = _banner(
            "事業所名のみ出力されます。住所・肩書・氏名は印刷されません。",
            visible=False,
        )
        self._nametag_banner = _banner(
            "事業所名、所属・役職、氏名を名刺サイズで出力します。",
            visible=False,
        )
        self._split4_banner = _banner(
            "事業所名を A4 用紙横長４分割で均等割付して出力します。"
            "上下回転させた事業所名を同時出力するので半分に折って使用します。",
            visible=False,
        )

    def _build_toolbar(self) -> QHBoxLayout:
        """ツールバーレイアウトを生成する（キーボードショートカット登録も含む）"""
        toolbar = QHBoxLayout()
        toolbar.setSpacing(4)

        def _tb(label: str, style: str = BTN_TB_OUTLINE) -> QPushButton:
            b = QPushButton(label)
            b.setFixedHeight(30)
            b.setStyleSheet(style)
            return b

        def _sep() -> QFrame:
            f = QFrame()
            f.setFrameShape(QFrame.Shape.VLine)
            f.setFixedWidth(1)
            f.setFixedHeight(20)
            f.setStyleSheet("color: #CBD5E1;")
            return f

        # グループA：取込
        btn_paste = _tb("貼り付けから取込")
        btn_paste.setToolTip(
            "Excel からコピーしたデータを取込みます。\n"
            "推奨列順（ヘッダーあり）: 企業名 / 郵便番号 / 住所 / 所属・役職 / 氏名\n"
            "ヘッダーなし: 列数で自動判定（2列=企業名・氏名 / 5列=企業名・〒・住所・役職・氏名 など）"
        )
        btn_paste.clicked.connect(self._do_paste)

        btn_csv = _tb("CSV 取込")
        btn_csv.clicked.connect(self._do_csv)

        # グループB：行編集
        btn_add = _tb("＋ 追加")
        btn_add.clicked.connect(self._add_row)

        btn_del = _tb("行を削除", BTN_TB_DANGER)
        btn_del.clicked.connect(self._del_rows)

        btn_clear = _tb("全クリア", BTN_TB_DANGER)
        btn_clear.clicked.connect(self._clear_all)

        # グループC：自動補完
        btn_postal = _tb("〒 自動補完")
        btn_postal.setToolTip(
            "住所が入力されていて郵便番号が空の行に、\n"
            "zipcloud API（インターネット接続必要）で郵便番号を補完します。"
        )
        btn_postal.clicked.connect(self._fill_postal_codes)

        btn_kana = _tb("フリガナ補完")
        btn_kana.setToolTip(
            "事業所名が入力されていてフリガナが空の行に、\n"
            "カタカナのフリガナを自動補完します。\n"
            "株式会社・有限会社などの法人種別名は除いて変換します。"
        )
        btn_kana.clicked.connect(self._fill_kana)

        # グループD：アンドゥ
        self._btn_undo = _tb("↩ 元に戻す")
        self._btn_undo.setToolTip("Ctrl+Z")
        self._btn_undo.setEnabled(False)
        self._btn_undo.clicked.connect(self._undo)

        QShortcut(QKeySequence("Ctrl+Z"), self).activated.connect(self._undo)
        QShortcut(QKeySequence("Ctrl+V"), self).activated.connect(self._do_paste)
        QShortcut(QKeySequence("Ctrl+P"), self).activated.connect(self._preview_pdf)

        for widget in [
            btn_paste, btn_csv,
            None,       # sep
            btn_add, btn_del, btn_clear,
            None,       # sep
            btn_postal, btn_kana,
            None,       # sep
            self._btn_undo,
        ]:
            if widget is None:
                toolbar.addSpacing(4)
                toolbar.addWidget(_sep())
                toolbar.addSpacing(4)
            else:
                toolbar.addWidget(widget)
        toolbar.addStretch()
        return toolbar

    def _build_table(self) -> QWidget:
        """データテーブルを生成・設定して返す"""
        self.table = DraggableTable(0, len(self._COLS))
        self._chk_header = CheckableHeader(self.table, initial_checked=True)
        self._chk_header.toggled.connect(self._on_header_toggled)
        self._chk_header.sort_requested.connect(self._on_sort)
        self.table.setHorizontalHeader(self._chk_header)
        self._chk_header.setStretchLastSection(False)

        self.table.setHorizontalHeaderLabels([c[0] for c in self._COLS])
        hdr = self.table.horizontalHeader()
        for i, (_, width, resize_mode) in enumerate(self._COLS):
            hdr.setSectionResizeMode(i, resize_mode)
            if resize_mode == QHeaderView.ResizeMode.Fixed:
                self.table.setColumnWidth(i, width)

        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            "QTableWidget::item:selected { background-color: #DBEAFE; color: black; }"
            "QTableWidget::item:selected:active { background-color: #DBEAFE; color: black; }"
            "QTableWidget::item:hover { background-color: #DBEAFE; color: black; }"
        )
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Fixed)
        self.table.setSelectionBehavior(self.table.SelectionBehavior.SelectRows)
        self.table.setItemDelegateForColumn(self.COL_COMPANY, MultilineDelegate(self.table))
        self.table.setItemDelegateForColumn(self.COL_TITLE,   MultilineDelegate(self.table))
        self.table.installEventFilter(self)
        self.table.itemChanged.connect(self._on_item_changed)
        self.table.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._show_context_menu)
        self.table.rows_dropped.connect(self._on_rows_dropped)

        self._chk_header.set_required_cols(self._REQUIRED_COLS.get("normal", set()))
        self._update_column_visibility()
        return self.table

    def _build_save_row(self) -> QHBoxLayout:
        """保存先表示行を生成する"""
        row = QHBoxLayout()
        row.setSpacing(6)

        save_icon = QLabel("📁")
        save_icon.setStyleSheet("font-size: 13px;")

        save_title = QLabel("保存先:")
        save_title.setStyleSheet("font-size: 12px; color: #64748B;")

        self._save_path_lbl = QLabel()
        self._save_path_lbl.setStyleSheet(
            f"font-size: 12px; color: {C_PRIMARY}; "
            "text-decoration: underline; cursor: pointer;"
        )
        self._save_path_lbl.setToolTip("クリックしてフォルダを変更")
        self._save_path_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self._save_path_lbl.mousePressEvent = lambda _: self._change_save_dir()
        self._refresh_save_path_label()

        btn_change = QPushButton("変更")
        btn_change.setFixedHeight(24)
        btn_change.setStyleSheet(
            "QPushButton { font-size: 11px; color: #475569; background: white; "
            "border: 1px solid #CBD5E1; border-radius: 3px; padding: 0 8px; }"
            "QPushButton:hover { background: #F1F5F9; }"
        )
        btn_change.clicked.connect(self._change_save_dir)

        row.addWidget(save_icon)
        row.addWidget(save_title)
        row.addWidget(self._save_path_lbl, 1)
        row.addWidget(btn_change)
        return row

    def _build_footer(self) -> QHBoxLayout:
        """フッター行（件数・用紙・フォント・ボタン群）を生成する"""
        foot = QHBoxLayout()

        self._count_lbl = QLabel("0 件")
        self._count_lbl.setStyleSheet("color: #64748B; font-size: 12px;")

        self._chk_barcode = QCheckBox("カスタマバーコードを印字する")
        self._chk_barcode.setStyleSheet("font-size: 12px; color: #475569;")
        self._chk_barcode.toggled.connect(self._on_barcode_toggled)
        self._chk_barcode.setVisible(False)   # 機能一時無効化

        def _lbl(text: str) -> QLabel:
            l = QLabel(text)
            l.setStyleSheet("color: #475569; font-size: 12px;")
            return l

        self._layout_combo = QComboBox()
        self._layout_combo.setFixedHeight(34)
        for key, lo in LABEL_LAYOUTS.items():
            self._layout_combo.addItem(lo.name, key)
        idx = self._layout_combo.findData(DEFAULT_LAYOUT_KEY)
        if idx >= 0:
            self._layout_combo.setCurrentIndex(idx)

        self._start_slot_lbl = _lbl("開始位置:")
        self._start_slot_spin = QSpinBox()
        self._start_slot_spin.setFixedHeight(34)
        self._start_slot_spin.setMinimum(1)
        self._start_slot_spin.setToolTip(
            "印刷を開始する面番号（1 = 1面目・左上）。\n"
            "使いかけのラベルシートの空いている面から印刷したいときに変更します。"
        )
        self._layout_combo.currentIndexChanged.connect(self._on_layout_changed)
        self._on_layout_changed()

        self._font_combo = QComboBox()
        self._font_combo.setFixedHeight(34)
        for key in FONT_OPTIONS:
            self._font_combo.addItem(key, key)
        idx = self._font_combo.findData(DEFAULT_FONT_KEY)
        if idx >= 0:
            self._font_combo.setCurrentIndex(idx)

        btn_cancel = QPushButton("閉じる")
        btn_cancel.setFixedHeight(36)
        btn_cancel.setStyleSheet(
            "QPushButton { color: #64748B; border: 1px solid #CBD5E1; "
            "border-radius: 4px; background: white; padding: 0 16px; }"
            "QPushButton:hover { background: #F1F5F9; }"
        )
        btn_cancel.clicked.connect(self.reject)

        self._btn_preview = QPushButton("👁 プレビュー")
        self._btn_preview.setFixedHeight(36)
        self._btn_preview.setStyleSheet(BTN_OUTLINE)
        self._btn_preview.setToolTip("PDF を保存せずにプレビュー表示します（Ctrl+P）")
        self._btn_preview.clicked.connect(self._preview_pdf)

        self._btn_export = QPushButton("PDF を出力する")
        self._btn_export.setFixedHeight(36)
        self._btn_export.setStyleSheet(BTN_PRIMARY)
        self._btn_export.clicked.connect(self._export)

        foot.addWidget(self._count_lbl)
        foot.addWidget(self._chk_barcode)
        foot.addStretch()
        foot.addWidget(_lbl("用紙:"))
        foot.addWidget(self._layout_combo)
        foot.addSpacing(8)
        foot.addWidget(self._start_slot_lbl)
        foot.addWidget(self._start_slot_spin)
        foot.addSpacing(8)
        foot.addWidget(_lbl("フォント:"))
        foot.addWidget(self._font_combo)
        foot.addSpacing(8)
        foot.addWidget(btn_cancel)
        foot.addSpacing(4)
        foot.addWidget(self._btn_preview)
        foot.addWidget(self._btn_export)
        return foot

    def _on_layout_changed(self) -> None:
        """用紙切替時に開始位置スピンボックスの範囲・表示を更新する"""
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        layout = LABEL_LAYOUTS.get(layout_key) or LABEL_LAYOUTS[DEFAULT_LAYOUT_KEY]
        is_plate = layout_key == "a4_4split"
        self._start_slot_lbl.setVisible(not is_plate)
        self._start_slot_spin.setVisible(not is_plate)
        if not is_plate:
            per_page = layout.cols * layout.rows
            self._start_slot_spin.setMaximum(per_page)
            if self._start_slot_spin.value() > per_page:
                self._start_slot_spin.setValue(per_page)

    # ── ステップインジケーター ───────────────────────────────────────

    def _build_step_bar(self) -> QWidget:
        """① モード → ② 取込 → ③ プレビュー → ④ 出力 のステップバーを構築する"""
        bar = QWidget()
        bar.setFixedHeight(36)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._step_labels: list[QLabel] = []
        steps = ["① モード選択", "② データ取込", "③ プレビュー", "④ PDF出力"]

        for i, text in enumerate(steps):
            lbl = QLabel(text)
            lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lbl.setFixedHeight(28)
            self._step_labels.append(lbl)
            layout.addWidget(lbl)

            if i < len(steps) - 1:
                arrow = QLabel("›")
                arrow.setAlignment(Qt.AlignmentFlag.AlignCenter)
                arrow.setFixedWidth(16)
                arrow.setStyleSheet("color: #CBD5E1; font-size: 16px;")
                layout.addWidget(arrow)

        layout.addStretch()
        self._update_step(2)  # モードは常に初期選択済みなので②から開始
        return bar

    def _update_step(self, active: int) -> None:
        """active: 現在のステップ番号（1〜4）。それ以前は完了、それ以降は未着手スタイル"""
        for i, lbl in enumerate(self._step_labels):
            step = i + 1
            key = "done" if step < active else ("active" if step == active else "pending")
            lbl.setStyleSheet(STEP_STYLES[key])

    def _refresh_save_path_label(self):
        """保存先ラベルを現在の設定値で更新する"""
        path = (
            get_direct_label_save_path()
            or get_label_save_path()
            or os.path.expanduser("~/Documents")
        )
        # 長いパスは末尾を省略して表示
        display = path if len(path) <= 60 else "…" + path[-57:]
        self._save_path_lbl.setText(display)
        self._save_path_lbl.setToolTip(path)

    def _change_save_dir(self):
        """保存先フォルダをユーザーに選択させて更新する"""
        current = (
            get_direct_label_save_path()
            or get_label_save_path()
            or os.path.expanduser("~/Documents")
        )
        new_dir = QFileDialog.getExistingDirectory(
            self, "保存先フォルダを選択", current
        )
        if new_dir:
            set_direct_label_save_path(new_dir)
            self._refresh_save_path_label()

    def _on_barcode_toggled(self, enabled: bool):
        self.table.setColumnHidden(self.COL_BC_ADDR, not enabled)
        if enabled and not self._loading_batch:
            self._populate_barcode_addr()

    def _populate_barcode_addr(self):
        from app.utils.customer_barcode import extract_address_code
        from PyQt6.QtGui import QColor
        self.table.blockSignals(True)
        for row in range(self.table.rowCount()):
            item_bc = self.table.item(row, self.COL_BC_ADDR)
            if item_bc and item_bc.text().strip():
                continue
            addr = (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text()
            code, confident = extract_address_code(addr)
            self._set_barcode_addr_item(row, code, warn=not confident)
        self.table.blockSignals(False)

    def _set_barcode_addr_item(self, row: int, code: str, warn: bool = False):
        from PyQt6.QtGui import QColor
        item = self.table.item(row, self.COL_BC_ADDR)
        if item is None:
            item = QTableWidgetItem(code)
            self.table.setItem(row, self.COL_BC_ADDR, item)
        else:
            item.setText(code)
        if warn:
            item.setBackground(QColor('#FFF59D'))
            item.setToolTip("住所から自動取得できませんでした。手入力で修正してください。")
        else:
            item.setBackground(QColor('white'))
            item.setToolTip("")

    def _on_item_changed(self, item: QTableWidgetItem):
        if item.column() == self.COL_BC_ADDR:
            from PyQt6.QtGui import QColor
            item.setBackground(QColor('white'))
            item.setToolTip("")

    # ── 行データ ヘルパー ───────────────────────────────────────────────

    def _read_all_rows(self) -> list[tuple[list[str], bool]]:
        """全行の (cell_values, is_checked) タプルリストを返す"""
        result = []
        for r in range(self.table.rowCount()):
            chk = self._get_row_chk(r)
            vals = [
                (self.table.item(r, c) or QTableWidgetItem()).text()
                for c in range(self.COL_COMPANY, len(self._COLS))
            ]
            result.append((vals, chk.isChecked() if chk else True))
        return result

    def _rebuild_table(self, rows: list[tuple[list[str], bool]]) -> None:
        """(vals, is_checked) リストからテーブルを再構築する"""
        self.table.setRowCount(0)
        self._last_chk_row = None
        for vals, checked in rows:
            self._add_row(vals)
            chk = self._get_row_chk(self.table.rowCount() - 1)
            if chk:
                chk.blockSignals(True)
                chk.setChecked(checked)
                chk.blockSignals(False)
        self._update_count()

    # ── ソート ──────────────────────────────────────────────────────────

    def _on_sort(self, col: int) -> None:
        if col == self.COL_CHK:
            return
        if self._sort_col == col:
            self._sort_asc = not self._sort_asc
        else:
            self._sort_col = col
            self._sort_asc = True

        rows_data = [(vals, checked) for vals, checked in self._read_all_rows()]
        col_offset = col - self.COL_COMPANY
        rows_data.sort(
            key=lambda x: x[0][col_offset].lower(),
            reverse=not self._sort_asc,
        )
        # _rebuild_table は (vals, checked) 順を期待する
        self._rebuild_table(rows_data)
        self._update_sort_headers()

    def _update_sort_headers(self):
        for col, (base, _, _) in enumerate(self._COLS):
            if col == self._sort_col:
                label = base + (" ▲" if self._sort_asc else " ▼")
            else:
                label = base
            item = self.table.horizontalHeaderItem(col)
            if item:
                item.setText(label)
            else:
                self.table.setHorizontalHeaderItem(col, QTableWidgetItem(label))

    def _get_row_chk(self, row: int) -> QCheckBox | None:
        w = self.table.cellWidget(row, self.COL_CHK)
        return w.findChild(QCheckBox) if w else None

    def _on_chk_clicked(self):
        sender = self.sender()
        clicked_row = next(
            (r for r in range(self.table.rowCount())
             if self._get_row_chk(r) is sender),
            None,
        )
        if clicked_row is None:
            return
        modifiers = QApplication.keyboardModifiers()
        if (modifiers & Qt.KeyboardModifier.ShiftModifier) and self._last_chk_row is not None:
            new_checked = sender.isChecked()
            r0, r1 = sorted([self._last_chk_row, clicked_row])
            for r in range(r0, r1 + 1):
                c = self._get_row_chk(r)
                if c:
                    c.blockSignals(True)
                    c.setChecked(new_checked)
                    c.blockSignals(False)
        self._last_chk_row = clicked_row
        self._update_count()

    def _on_header_toggled(self, checked: bool):
        self._last_chk_row = None
        for row in range(self.table.rowCount()):
            c = self._get_row_chk(row)
            if c:
                c.blockSignals(True)
                c.setChecked(checked)
                c.blockSignals(False)
        self._update_count()

    def _get_checked_rows(self) -> list[int]:
        return [r for r in range(self.table.rowCount())
                if (c := self._get_row_chk(r)) and c.isChecked()]

    def _fill_postal_codes(self):
        from app.utils.postal_lookup import lookup_postal_code
        from PyQt6.QtWidgets import QApplication

        targets = [
            row for row in range(self.table.rowCount())
            if not (self.table.item(row, self.COL_POSTAL) or QTableWidgetItem()).text().strip()
            and (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip()
        ]
        if not targets:
            QMessageBox.information(self, "郵便番号補完",
                                    "補完対象の行がありません。\n"
                                    "（郵便番号が空で住所が入力されている行が対象です）")
            return

        self._btn_export.setEnabled(False)
        filled = skipped = 0
        for row in targets:
            address = (self.table.item(row, self.COL_ADDR1) or QTableWidgetItem()).text().strip()
            QApplication.processEvents()
            zipcode = lookup_postal_code(address)
            if zipcode:
                item = self.table.item(row, self.COL_POSTAL)
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

    def _fill_kana(self):
        try:
            from app.utils.kana_lookup import get_company_kana
        except ImportError:
            QMessageBox.critical(
                self, "ライブラリ不足",
                "pykakasi がインストールされていません。\n"
                "pip install pykakasi を実行してください。"
            )
            return

        targets = [
            row for row in range(self.table.rowCount())
            if not (self.table.item(row, self.COL_KANA) or QTableWidgetItem()).text().strip()
            and (self.table.item(row, self.COL_COMPANY) or QTableWidgetItem()).text().strip()
        ]
        if not targets:
            QMessageBox.information(self, "フリガナ補完",
                                    "補完対象の行がありません。\n"
                                    "（フリガナが空で事業所名が入力されている行が対象です）")
            return

        filled = 0
        for row in targets:
            company = (self.table.item(row, self.COL_COMPANY) or QTableWidgetItem()).text().strip()
            kana = get_company_kana(company)
            if kana:
                item = self.table.item(row, self.COL_KANA)
                if item:
                    item.setText(kana)
                filled += 1

        QMessageBox.information(self, "フリガナ補完",
                                f"{filled} 件のフリガナを補完しました。")

    def _load_batch(self, batch_id: int):
        session = get_session()
        try:
            batch = session.get(LabelBatch, batch_id)
            if not batch:
                QMessageBox.warning(self, "エラー", "指定されたバッチが見つかりません。")
                return
            self._data_name_edit.setText(batch.batch_name or "")
            if batch.label_mode == "no_person":
                self._radio_no_person.setChecked(True)
            elif batch.label_mode == "simple":
                self._radio_simple.setChecked(True)
            elif batch.label_mode == "nametag":
                self._radio_nametag.setChecked(True)
            elif batch.label_mode == "split4":
                self._radio_split4.setChecked(True)
            else:
                self._radio_normal.setChecked(True)
            entries        = list(batch.entries)
            barcode_enabled = bool(batch.barcode_enabled)
            session.expunge_all()
        finally:
            session.close()

        self._loading_batch = True
        self.table.setRowCount(0)
        self._last_chk_row = None
        for e in entries:
            self._add_row([
                e.company_name    or "",
                getattr(e, "company_name2", "") or "",
                e.company_kana    or "",
                e.title           or "",
                e.person_name     or "",
                e.postal_code     or "",
                e.address1        or "",
                e.address2        or "",
                e.barcode_address or "",
            ])
        self._loading_batch = False
        self._chk_barcode.setChecked(False)   # 機能一時無効化

    def eventFilter(self, obj, event):
        if obj is self.table and event.type() == QEvent.Type.KeyPress:
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                return True
        return super().eventFilter(obj, event)

    def _save_undo_snapshot(self) -> None:
        self._undo_stack.append(self._read_all_rows())
        if len(self._undo_stack) > 10:
            self._undo_stack.pop(0)
        self._btn_undo.setEnabled(True)

    def _undo(self) -> None:
        if not self._undo_stack:
            return
        self._rebuild_table(self._undo_stack.pop())
        self._btn_undo.setEnabled(bool(self._undo_stack))

    def _clear_all(self):
        if self.table.rowCount() == 0:
            return
        reply = QMessageBox.question(
            self, "全件クリア",
            f"現在の {self.table.rowCount()} 件のデータをすべて削除しますか？\n"
            "この操作は「元に戻す」（Ctrl+Z）で取り消せます。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._save_undo_snapshot()
        self.table.setRowCount(0)
        self._last_chk_row = None
        self._update_count()

    def _check_required_and_warn(self, checked_rows: list[int]) -> bool:
        required = self._REQUIRED_COLS.get(self._current_mode(), set())
        if not required:
            return True
        bad = []
        for row in checked_rows:
            missing = [self._COLS[col][0] for col in required
                       if not (self.table.item(row, col) and
                               self.table.item(row, col).text().strip())]
            if missing:
                company = (self.table.item(row, self.COL_COMPANY) or
                           QTableWidgetItem()).text().strip() or "（空白）"
                bad.append(f"行 {row + 1}　{company}：{', '.join(missing)} が未入力")
        if not bad:
            return True
        detail = "\n".join(bad[:15])
        if len(bad) > 15:
            detail += f"\n… 他 {len(bad) - 15} 件"
        reply = QMessageBox.warning(
            self, "必須項目が未入力の行があります",
            f"以下の行に必須項目の未入力があります。\n\n{detail}\n\n"
            "このまま出力しますか？",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _apply_required_bg_to_row(self, row: int):
        required = self._REQUIRED_COLS.get(self._current_mode(), set())
        pink = QBrush(QColor("#FFF0F3"))
        for col in range(self.COL_COMPANY, self.COL_BC_ADDR):
            item = self.table.item(row, col)
            if item:
                item.setBackground(pink if col in required else QBrush())

    def _update_required_highlights(self):
        required = self._REQUIRED_COLS.get(self._current_mode(), set())
        self._chk_header.set_required_cols(required)
        for row in range(self.table.rowCount()):
            self._apply_required_bg_to_row(row)

    # モードごとに非表示にする列（COL_BC_ADDR は常時非表示のため除外）
    _HIDDEN_COLS: dict[str, set] = {
        "normal":    set(),
        "no_person": {COL_TITLE, COL_PERSON},
        "simple":    {COL_TITLE, COL_PERSON, COL_POSTAL, COL_ADDR1, COL_ADDR2},
        "nametag":   {COL_POSTAL, COL_ADDR1, COL_ADDR2},
        "split4":    {COL_TITLE, COL_PERSON, COL_POSTAL, COL_ADDR1, COL_ADDR2},
    }

    def _on_mode_toggled(self, checked: bool):
        if not checked:
            return
        self._normal_banner.setVisible(self._radio_normal.isChecked())
        self._no_person_banner.setVisible(self._radio_no_person.isChecked())
        self._simple_banner.setVisible(self._radio_simple.isChecked())
        self._nametag_banner.setVisible(self._radio_nametag.isChecked())
        self._split4_banner.setVisible(self._radio_split4.isChecked())

        if self._radio_nametag.isChecked():
            idx = self._layout_combo.findData("a_one_51002")
        elif self._radio_split4.isChecked():
            idx = self._layout_combo.findData("a4_4split")
        else:
            idx = self._layout_combo.findData(DEFAULT_LAYOUT_KEY)
        if idx >= 0:
            self._layout_combo.setCurrentIndex(idx)
        self._update_required_highlights()
        self._update_column_visibility()

    def _update_column_visibility(self):
        """モードに応じて不要な列を非表示にする"""
        mode = self._current_mode()
        hidden = self._HIDDEN_COLS.get(mode, set())
        # CHK・COMPANY・KANA は常時表示、BC_ADDR は常時非表示
        always_visible = {self.COL_CHK, self.COL_COMPANY, self.COL_KANA}
        always_hidden  = {self.COL_BC_ADDR}
        for col in range(len(self._COLS)):
            if col in always_hidden:
                self.table.setColumnHidden(col, True)
            elif col in always_visible:
                self.table.setColumnHidden(col, False)
            else:
                self.table.setColumnHidden(col, col in hidden)

    def _current_mode(self) -> str:
        if self._radio_no_person.isChecked():
            return "no_person"
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
        chk = QCheckBox()
        chk.setChecked(True)
        chk.clicked.connect(self._on_chk_clicked)
        cell = QWidget()
        lay = QHBoxLayout(cell)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lay.addWidget(chk)
        self.table.setCellWidget(row, self.COL_CHK, cell)
        for offset, col in enumerate(range(self.COL_COMPANY, len(self._COLS))):
            item = QTableWidgetItem(values[offset] if values and offset < len(values) else "")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, col, item)
        self._apply_required_bg_to_row(row)
        self._update_count()

    def _show_context_menu(self, pos: QPoint):
        """テーブル右クリックメニューを表示する"""
        selected_rows = sorted({i.row() for i in self.table.selectedItems()})
        menu = QMenu(self)

        act_add = QAction("＋ 行を追加", self)
        act_add.triggered.connect(self._add_row)
        menu.addAction(act_add)

        act_dup = QAction("この行を複製", self)
        act_dup.setEnabled(bool(selected_rows))
        act_dup.triggered.connect(self._duplicate_rows)
        menu.addAction(act_dup)

        menu.addSeparator()

        act_del = QAction("選択行を削除", self)
        act_del.setEnabled(bool(selected_rows))
        act_del.triggered.connect(self._del_rows)
        menu.addAction(act_del)

        menu.exec(self.table.viewport().mapToGlobal(pos))

    def _on_rows_dropped(self, target_row: int, source_rows: list) -> None:
        """ドラッグ＆ドロップで行を並び替える"""
        if not source_rows:
            return

        self._save_undo_snapshot()
        all_rows = self._read_all_rows()

        # 移動元を取り出して挿入先に差し込む
        source_set = set(source_rows)
        moving = [all_rows[r] for r in source_rows if r < len(all_rows)]
        rest   = [row for i, row in enumerate(all_rows) if i not in source_set]

        # 挿入位置：source_rows のうちターゲットより前にある行の数だけ補正
        adj_target = target_row - sum(1 for r in source_rows if r < target_row)
        adj_target = max(0, min(adj_target, len(rest)))
        new_order = rest[:adj_target] + moving + rest[adj_target:]

        # 順序が変わっていなければ Undo スタックを戻して終了
        if new_order == all_rows:
            if self._undo_stack:
                self._undo_stack.pop()
            self._btn_undo.setEnabled(bool(self._undo_stack))
            return

        self._rebuild_table(new_order)

    def _duplicate_rows(self):
        """選択行を直下に複製する"""
        rows = sorted({i.row() for i in self.table.selectedItems()})
        if not rows:
            return
        self._save_undo_snapshot()
        for row in reversed(rows):
            chk = self._get_row_chk(row)
            vals = [(self.table.item(row, c) or QTableWidgetItem()).text()
                    for c in range(self.COL_COMPANY, len(self._COLS))]
            insert_at = row + 1
            self.table.insertRow(insert_at)
            new_chk = QCheckBox()
            new_chk.setChecked(chk.isChecked() if chk else True)
            new_chk.clicked.connect(self._on_chk_clicked)
            cell = QWidget()
            lay = QHBoxLayout(cell)
            lay.setContentsMargins(0, 0, 0, 0)
            lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay.addWidget(new_chk)
            self.table.setCellWidget(insert_at, self.COL_CHK, cell)
            for offset, col in enumerate(range(self.COL_COMPANY, len(self._COLS))):
                item = QTableWidgetItem(vals[offset] if offset < len(vals) else "")
                item.setFlags(item.flags() | Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(insert_at, col, item)
            self._apply_required_bg_to_row(insert_at)
        self._update_count()

    def _del_rows(self):
        rows = sorted({i.row() for i in self.table.selectedItems()}, reverse=True)
        if not rows:
            return
        self._save_undo_snapshot()
        for r in rows:
            self.table.removeRow(r)
        self._update_count()

    def _update_count(self):
        total   = self.table.rowCount()
        checked = len(self._get_checked_rows())
        if checked == total:
            self._count_lbl.setText(f"{total} 件")
        else:
            self._count_lbl.setText(f"{total} 件（{checked} 件を出力対象）")
        # ステップ更新: データが入れば②完了→③プレビューへ
        self._update_step(3 if total > 0 else 2)

    def _set_initial_mode(self, mode: str):
        """カードから開いたときの初期モードを設定する"""
        btn_map = {
            "normal":    self._radio_normal,
            "no_person": self._radio_no_person,
            "simple":    self._radio_simple,
            "nametag":   self._radio_nametag,
            "split4":    self._radio_split4,
        }
        btn = btn_map.get(mode)
        if btn:
            btn.setChecked(True)

    def _preview_pdf(self):
        """データを PDF 化してプレビュー表示する（ファイル保存なし）"""
        from io import BytesIO
        try:
            import fitz  # noqa: F401  PyMuPDF 確認用
        except ImportError:
            QMessageBox.critical(
                self, "ライブラリ不足",
                "PyMuPDF がインストールされていません。\n"
                "pip install PyMuPDF を実行してください。"
            )
            return

        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "データなし", "プレビューするデータがありません。")
            return

        checked_rows = self._get_checked_rows()
        if not checked_rows:
            QMessageBox.warning(
                self, "出力対象なし",
                "チェックされたデータがありません。\n"
                "プレビューしたい行にチェックを入れてください。"
            )
            return

        mode       = self._current_mode()
        layout_key = self._layout_combo.currentData() or DEFAULT_LAYOUT_KEY
        font_key   = self._font_combo.currentData()   or DEFAULT_FONT_KEY
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
        start_slot = 0 if layout_key == "a4_4split" else self._start_slot_spin.value() - 1

        # テーブルの選択行を LabelEntry 互換の軽量オブジェクトに変換
        entries = []
        for row in checked_rows:
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            entries.append(type("_E", (), {
                "company_name":    _cell(self.COL_COMPANY),
                "company_name2":   _cell(self.COL_COMPANY2),
                "company_kana":    _cell(self.COL_KANA),
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR1),
                "address2":        _cell(self.COL_ADDR2),
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })())

        buf = BytesIO()
        try:
            generate_label_pdf(entries, buf, mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v,
                               start_slot=start_slot)
        except Exception as ex:
            QMessageBox.critical(self, "プレビューエラー",
                                 f"PDF の生成に失敗しました：\n{ex}")
            return

        from app.ui.pdf_preview_dialog import PdfPreviewDialog
        dlg = PdfPreviewDialog(buf.getvalue(), "PDF プレビュー", parent=self)
        dlg.exec()

    def _fill_rows(self, direct_rows):
        if not direct_rows:
            QMessageBox.information(self, "取込結果", "取込可能なデータがありませんでした。")
            return

        do_clear = False
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
            do_clear = (reply == QMessageBox.StandardButton.Yes)

        self._save_undo_snapshot()
        if do_clear:
            self.table.setRowCount(0)
            self._last_chk_row = None

        for dr in direct_rows:
            self._add_row([
                dr.company_name,
                dr.company_name2,
                dr.company_kana,
                dr.title,
                dr.person_name,
                dr.postal_code,
                dr.address1,
                dr.address2,
            ])
        QMessageBox.information(self, "取込完了", f"{len(direct_rows)} 件を取り込みました。")

    def _import_rows(self, headers: list, data_rows: list) -> None:
        if not headers:
            QMessageBox.information(self, "取込結果", "取込可能なデータがありませんでした。")
            return

        dlg = ColumnMappingDialog(headers, data_rows[:5], self._current_mode(), self)
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
                company_name2=_get("company_name2"),
                company_kana=_get("company_kana"),
                postal_code =_get("postal_code"),
                address1    =_get("address1"),
                address2    =_get("address2"),
                title       =_get("title"),
                person_name =_get("person_name"),
            )
            if dr.company_name:
                rows.append(dr)
        self._fill_rows(rows)

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
        self._import_rows(headers, data_rows)

    def _do_csv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "CSV ファイルを選択", "", "CSV ファイル (*.csv);;すべてのファイル (*)"
        )
        if not path:
            return
        try:
            with open(path, "rb") as f:
                headers, data_rows = parse_raw_csv_bytes(f.read())
        except Exception as e:
            QMessageBox.critical(self, "エラー", f"CSV 読み込みエラー：\n{e}")
            return
        self._import_rows(headers, data_rows)

    def _export(self):
        if self.table.rowCount() == 0:
            QMessageBox.warning(self, "データなし", "出力するデータがありません。")
            return

        data_name = self._data_name_edit.text().strip()
        if not data_name:
            QMessageBox.warning(self, "データ名が未入力", "データ名を入力してください。")
            self._data_name_edit.setFocus()
            return

        last_dir = (
            get_direct_label_save_path()
            or get_label_save_path()
            or os.path.expanduser("~/Documents")
        )
        default_path = os.path.join(last_dir, f"{data_name}.pdf")

        pdf_path, _ = QFileDialog.getSaveFileName(
            self, "ラベルを保存", default_path, "PDF ファイル (*.pdf)",
        )
        if not pdf_path:
            return
        if not pdf_path.lower().endswith(".pdf"):
            pdf_path += ".pdf"

        dest_dir = os.path.dirname(pdf_path)
        mode     = self._current_mode()

        checked_rows = self._get_checked_rows()
        if not checked_rows:
            QMessageBox.warning(self, "出力対象なし",
                                "チェックされたデータがありません。\n"
                                "出力したい行にチェックを入れてください。")
            return

        if not self._check_required_and_warn(checked_rows):
            return

        # 全行をDBに保存（sort_order = テーブル行インデックス）
        all_entry_dicts = []
        for row in range(self.table.rowCount()):
            def _cell(col, _row=row):
                item = self.table.item(_row, col)
                return item.text().strip() if item else ""
            all_entry_dicts.append({
                "sort_order":      row,
                "client_id":       None,
                "company_name":    _cell(self.COL_COMPANY),
                "company_name2":   _cell(self.COL_COMPANY2),
                "company_kana":    _cell(self.COL_KANA),
                "postal_code":     _cell(self.COL_POSTAL),
                "address1":        _cell(self.COL_ADDR1),
                "address2":        _cell(self.COL_ADDR2),
                "title":           _cell(self.COL_TITLE),
                "person_name":     _cell(self.COL_PERSON),
                "barcode_address": _cell(self.COL_BC_ADDR),
                "entry_mode":      "inherit",
            })

        checked_set = set(checked_rows)

        session = get_session()
        try:
            bc_enabled = 1 if self._chk_barcode.isChecked() else 0
            if self._batch_id is not None:
                batch = session.get(LabelBatch, self._batch_id)
                if batch:
                    batch.batch_name      = data_name
                    batch.label_mode      = mode
                    batch.barcode_enabled = bc_enabled
                    for old_e in list(batch.entries):
                        session.delete(old_e)
                    session.flush()
                else:
                    batch = LabelBatch(batch_name=data_name, label_mode=mode,
                                       barcode_enabled=bc_enabled)
                    session.add(batch)
                    session.flush()
                    self._batch_id = batch.id
            else:
                batch = LabelBatch(batch_name=data_name, label_mode=mode,
                                   barcode_enabled=bc_enabled)
                session.add(batch)
                session.flush()
                self._batch_id = batch.id
            for ed in all_entry_dicts:
                e = LabelEntry(batch_id=batch.id, **{k: v for k, v in ed.items()})
                session.add(e)
            session.commit()
            batch_id = batch.id

            # PDF出力はチェック済み行のみ（sort_order = テーブル行インデックス）
            orm_entries = (
                session.query(LabelEntry)
                .filter(LabelEntry.batch_id == batch_id,
                        LabelEntry.sort_order.in_(checked_set))
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
        offset_h, offset_v = (
            (0.0, 0.0) if layout_key == "a4_4split" else get_label_offset(layout_key)
        )
        start_slot = 0 if layout_key == "a4_4split" else self._start_slot_spin.value() - 1
        try:
            generate_label_pdf(orm_entries, os.path.normpath(pdf_path), mode, layout_key, font_key,
                               barcode_enabled=self._chk_barcode.isChecked(),
                               offset_h_mm=offset_h, offset_v_mm=offset_v,
                               start_slot=start_slot)
        except Exception as ex:
            QMessageBox.critical(self, "PDF 出力エラー", f"PDF の生成に失敗しました：\n{ex}")
            return

        set_direct_label_save_path(dest_dir)
        self._refresh_save_path_label()
        self._update_step(4)   # PDF出力完了 → ④

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
