# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import (
    QHeaderView, QStyle, QStyleOptionButton,
    QTableWidget, QPlainTextEdit, QAbstractItemDelegate, QStyledItemDelegate,
)
from PyQt6.QtCore import Qt, pyqtSignal, QRect
from PyQt6.QtGui import QColor

MODE_LABEL: dict[str, str] = {
    "normal":    "宛名(氏名あり)",
    "no_person": "宛名(氏名なし)",
    "simple":    "事業所名のみ",
    "nametag":   "名札",
    "split4":    "卓上プレート",
}


class CheckableHeader(QHeaderView):
    """列0にチェックボックスを描画するカスタムヘッダー"""
    toggled = pyqtSignal(bool)
    sort_requested = pyqtSignal(int)

    def __init__(self, parent=None, initial_checked: bool = False):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self._checked = initial_checked
        self._required_cols: set = set()
        self.setSectionsClickable(True)

    def set_checked(self, checked: bool):
        self._checked = checked
        self.viewport().update()

    def set_required_cols(self, cols: set):
        self._required_cols = cols
        self.viewport().update()

    def paintSection(self, painter, rect, logical_index):
        painter.save()
        super().paintSection(painter, rect, logical_index)
        painter.restore()
        if logical_index in self._required_cols:
            painter.save()
            c = QColor("#FF6B8A")
            c.setAlpha(55)
            painter.fillRect(rect.adjusted(1, 2, -1, 0), c)
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
            self.sort_requested.emit(idx)


class DraggableTable(QTableWidget):
    """行のドラッグ＆ドロップ並び替えに対応した QTableWidget サブクラス。
    cell widget（チェックボックス）を含む行を正しく移動するため、
    dropEvent でシグナルを発行してダイアログ側で再構築する。"""

    rows_dropped = pyqtSignal(int, list)   # (挿入先行番号, 移動元行番号リスト)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        # DragDrop モード: DropIndicator を表示しつつ Qt の自動移動は行わせない
        self.setDragDropMode(QTableWidget.DragDropMode.DragDrop)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.DropAction.CopyAction)

    def dropEvent(self, event):
        if event.source() is not self:
            super().dropEvent(event)
            return

        target_row = self.indexAt(event.position().toPoint()).row()
        if target_row < 0:
            target_row = self.rowCount()

        source_rows = sorted(set(idx.row() for idx in self.selectedIndexes()))

        # IgnoreAction にすることで Qt がアイテムを自動削除するのを防ぐ
        # 実際の並び替えは rows_dropped シグナルで受け取るダイアログ側が行う
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()

        if source_rows:
            self.rows_dropped.emit(target_row, source_rows)


class MultilineDelegate(QStyledItemDelegate):
    """Alt+Enter で改行を挿入できる企業名セル用デリゲート"""

    def createEditor(self, parent, option, index):
        editor = QPlainTextEdit(parent)
        editor.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        editor.setStyleSheet("background: white; border: 1px solid #2563EB;")
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
