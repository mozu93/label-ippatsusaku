# -*- coding: utf-8 -*-
import json, os

_CONFIG_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "LabelIppatsusaku")
_CONFIG_PATH = os.path.join(_CONFIG_DIR, "config.json")
_DEFAULTS = {
    "label_save_path": "",
    "direct_label_save_path": "",
}


def _load() -> dict:
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    if not os.path.exists(_CONFIG_PATH):
        return dict(_DEFAULTS)
    try:
        with open(_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        cfg = dict(_DEFAULTS)
        cfg.update(data)
        return cfg
    except Exception:
        return dict(_DEFAULTS)


def _save(cfg: dict):
    os.makedirs(_CONFIG_DIR, exist_ok=True)
    with open(_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


def get_label_save_path() -> str:
    return _load().get("label_save_path", "")


def get_direct_label_save_path() -> str:
    return _load().get("direct_label_save_path", "")


def set_direct_label_save_path(path: str):
    cfg = _load()
    cfg["direct_label_save_path"] = path
    _save(cfg)
