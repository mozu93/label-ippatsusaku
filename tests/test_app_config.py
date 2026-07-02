# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils import app_config


def _use_tmp_config(monkeypatch, tmp_path):
    cfg_dir = str(tmp_path)
    monkeypatch.setattr(app_config, "_CONFIG_DIR", cfg_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", os.path.join(cfg_dir, "config.json"))


def test_get_label_offset_default_is_zero(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    h, v = app_config.get_label_offset("a_one_28185")
    assert h == 0.0
    assert v == 0.0


def test_save_and_get_label_offset_roundtrip(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 2.5, -1.0)
    h, v = app_config.get_label_offset("a_one_28185")
    assert h == 2.5
    assert v == -1.0


def test_save_label_offset_keeps_other_layouts_independent(monkeypatch, tmp_path):
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_28185", 1.0, 1.0)
    app_config.save_label_offset("a_one_28187", -2.0, 3.0)
    h1, v1 = app_config.get_label_offset("a_one_28185")
    h2, v2 = app_config.get_label_offset("a_one_28187")
    assert (h1, v1) == (1.0, 1.0)
    assert (h2, v2) == (-2.0, 3.0)


def test_save_label_offset_does_not_mutate_defaults(monkeypatch, tmp_path):
    """_DEFAULTS を変更しない設計であることの回帰テスト:
    保存後に _DEFAULTS['label_offset'] のようなキーが増えていないことを確認する。
    """
    _use_tmp_config(monkeypatch, tmp_path)
    app_config.save_label_offset("a_one_51002", 9.0, 9.0)
    assert "label_offset" not in app_config._DEFAULTS
