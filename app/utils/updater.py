# -*- coding: utf-8 -*-
"""
GitHub Releases を使った自動アップデートモジュール。
"""
import os
import sys
import json
import tempfile
import subprocess
import urllib.request
import urllib.error
from typing import Optional

from packaging.version import Version

GITHUB_API_URL = "https://api.github.com/repos/mozu93/label-ippatsusaku/releases/latest"
_TIMEOUT = 8


def is_newer_version(current: str, latest: str) -> bool:
    """latest が current より新しければ True。v プレフィックスは除去する。"""
    current = current.lstrip("v")
    latest  = latest.lstrip("v")
    return Version(latest) > Version(current)


def check_latest_version() -> Optional[dict]:
    """
    GitHub API で最新リリースを取得する。
    戻り値: {"tag_name": "v1.0.1", "download_url": "https://..."} または None（失敗時）
    """
    try:
        req = urllib.request.Request(
            GITHUB_API_URL,
            headers={"Accept": "application/vnd.github+json",
                     "User-Agent": "label-ippatsusaku-updater"},
        )
        with urllib.request.urlopen(req, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        tag = data.get("tag_name", "")
        assets = data.get("assets", [])
        if not tag or not assets:
            return None
        download_url = assets[0].get("browser_download_url", "")
        if not download_url:
            return None
        return {"tag_name": tag, "download_url": download_url}
    except Exception:
        return None


def download_new_exe(url: str, progress_callback=None) -> Optional[str]:
    """
    新しい exe を %TEMP% にダウンロードする。
    progress_callback(received_bytes, total_bytes) を呼び出す（total が不明な場合は -1）。
    成功時はダウンロード先パスを返す。失敗時は None。
    """
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "label-ippatsusaku-updater"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", -1))
            fd, tmp_path = tempfile.mkstemp(suffix=".exe", prefix="label_ippatsusaku_new_")
            received = 0
            with os.fdopen(fd, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    received += len(chunk)
                    if progress_callback:
                        progress_callback(received, total)
        return tmp_path
    except Exception:
        return None


def launch_updater(new_exe_path: str, current_exe_path: str):
    """
    updater.bat を %TEMP% に生成して起動し、アプリを終了する。
    リリース資産は Inno Setup インストーラーなので、直接起動するだけでよい。
    bat は: 3秒待機（アプリ終了を待つ）→ インストーラーを起動 → 自己削除
    """
    bat_fd, bat_path = tempfile.mkstemp(suffix=".bat", prefix="label_ippatsusaku_updater_")
    with os.fdopen(bat_fd, "w", encoding="cp932") as f:
        f.write("@echo off\r\n")
        f.write("timeout /t 3 /nobreak > nul\r\n")
        f.write(f'start "" "{new_exe_path}"\r\n')
        f.write('del "%~f0"\r\n')
    subprocess.Popen(["cmd", "/c", bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit(0)
