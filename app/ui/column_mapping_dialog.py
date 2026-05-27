# -*- coding: utf-8 -*-
"""
列マッピングダイアログ

貼り付けデータ / CSV の列を各フィールドに対応付けるダイアログ。
DirectLabelDialog から呼び出される。
"""
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout,
    QLabel, QComboBox, QDialogButtonBox,
    QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox,
)
from PyQt6.QtCore import Qt

from app.utils.label_import import (
    _normalize, _DIR_COMPANY, _DIR_KANA, _DIR_POSTAL, _DIR_ADDR1, _DIR_TITLE, _DIR_PERSON,
    _FALLBACK_COLS,
)


class ColumnMappingDialog(QDialog):
    """貼り付けデータの列を各フィールドに対応付けるダイアログ"""

    _FIELDS = [
        ("company_name", "事業所名"),
        ("company_kana", "フリガナ（読み）"),
        ("title",        "所属・役職名"),
        ("person_name",  "氏名"),
        ("postal_code",  "郵便番号"),
        ("address1",     "住所"),
    ]

    _REQUIRED_BY_MODE: dict[str, set] = {
        "normal":    {"company_name", "address1", "person_name"},
        "no_person": {"company_name", "address1"},
        "simple":    {"company_name"},
        "nametag":   {"company_name", "person_name"},
        "split4":    {"company_name"},
    }

    _FIELD_HINTS: dict[str, str] = {
        "company_kana": "任意・自動入力可",
        "title":        "任意",
        "postal_code":  "任意・自動入力可",
    }

    def __init__(self, headers: list[str], preview_rows: list[list[str]],
                 mode: str = "normal", parent=None):
        super().__init__(parent)
        self.setWindowTitle("列の対応を設定")
        self.setMinimumSize(720, 520)
        self._headers = headers
        self._preview_rows = preview_rows
        self._required = self._REQUIRED_BY_MODE.get(mode, {"company_name"})
        self._combos: dict[str, QComboBox] = {}
        self._init_ui()
        self._auto_detect()

    # ── UI 構築 ────────────────────────────────────────────────────────

    def _init_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setSpacing(12)
        root.setContentsMargins(20, 16, 20, 16)

        lbl_pre = QLabel("貼り付けデータのプレビュー（先頭 5 行）")
        lbl_pre.setStyleSheet("font-weight: bold;")
        root.addWidget(lbl_pre)

        preview_tbl = QTableWidget(len(self._preview_rows), len(self._headers))
        preview_tbl.setHorizontalHeaderLabels(self._headers)
        preview_tbl.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        preview_tbl.setMaximumHeight(170)
        preview_tbl.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        for r, row in enumerate(self._preview_rows):
            for c, val in enumerate(row):
                preview_tbl.setItem(r, c, QTableWidgetItem(val))
        root.addWidget(preview_tbl)

        lbl_map = QLabel("各フィールドに対応する列を選択してください")
        lbl_map.setStyleSheet("font-weight: bold; margin-top: 8px;")
        root.addWidget(lbl_map)

        form = QFormLayout()
        form.setSpacing(8)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        choices = ["（使用しない）"] + self._headers

        for field_id, field_label in self._FIELDS:
            combo = QComboBox()
            combo.addItems(choices)
            required = field_id in self._required
            hint = self._FIELD_HINTS.get(field_id)
            if required:
                suffix = " <span style='color:red'>*</span>"
            elif hint:
                suffix = (f" <span style='color:#94A3B8; font-size:11px'>"
                          f"（{hint}）</span>")
            else:
                suffix = ""
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

    # ── 自動検出 ────────────────────────────────────────────────────────

    def _auto_detect(self) -> None:
        """ヘッダー名からフィールドを自動マッピングする"""
        field_keys = {
            "company_name": _DIR_COMPANY,
            "company_kana": _DIR_KANA,
            "postal_code":  _DIR_POSTAL,
            "address1":     _DIR_ADDR1,
            "title":        _DIR_TITLE,
            "person_name":  _DIR_PERSON,
        }
        used: set[int] = set()
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
                    if col_idx < len(self._headers) and field_id in self._combos:
                        self._combos[field_id].setCurrentIndex(col_idx + 1)

    # ── スロット ────────────────────────────────────────────────────────

    def _on_ok(self) -> None:
        label_map = {fid: lbl for fid, lbl in self._FIELDS}
        for field_id in self._required:
            if self._combos[field_id].currentIndex() == 0:
                QMessageBox.warning(
                    self, "入力エラー",
                    f"「{label_map.get(field_id, field_id)}」列を選択してください。"
                )
                return
        self.accept()

    # ── 公開 API ────────────────────────────────────────────────────────

    def get_mapping(self) -> dict[str, int | None]:
        """フィールドID → 列インデックス（0-based, Noneは未選択）のマッピングを返す"""
        return {
            field_id: (idx - 1) if (idx := self._combos[field_id].currentIndex()) > 0 else None
            for field_id, _ in self._FIELDS
        }
