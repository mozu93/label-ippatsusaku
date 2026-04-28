# -*- coding: utf-8 -*-
from PyQt6.QtWidgets import QHeaderView, QStyle, QStyleOptionButton
from PyQt6.QtCore import Qt, pyqtSignal, QRect

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
            self.sort_requested.emit(idx)
