# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PyQt6.QtWidgets import QApplication, QMessageBox
_app = QApplication.instance() or QApplication(sys.argv)

from app.utils import app_config


def _use_tmp_config(monkeypatch, tmp_path):
    cfg_dir = str(tmp_path)
    monkeypatch.setattr(app_config, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", os.path.join(cfg_dir, "config.json"))


def test_dialog_excludes_split4_layout(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        assert "a4_4split" not in dlg._spins
        assert "a_one_28185" in dlg._spins
    finally:
        dlg.close()


def test_dialog_loads_existing_offset_into_spinboxes(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 3.0, -1.5)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        h_spin, v_spin = dlg._spins["a_one_28185"]
        assert h_spin.value() == 3.0
        assert v_spin.value() == -1.5
    finally:
        dlg.close()


def test_dialog_save_writes_all_layouts_to_app_config(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    monkeypatch.setattr(QMessageBox, "information", lambda *a, **k: None)
    from app.ui.print_offset_dialog import PrintOffsetDialog
    dlg = PrintOffsetDialog()
    try:
        h_spin, v_spin = dlg._spins["a_one_28187"]
        h_spin.setValue(4.5)
        v_spin.setValue(-2.0)
        dlg._save()
        h, v = app_config.get_label_offset("a_one_28187")
        assert h == 4.5
        assert v == -2.0
    finally:
        dlg.close()
