# -*- coding: utf-8 -*-
"""
郵便番号 ↔ 住所 変換ユーティリティ
- lookup_postal_code  : 住所 → 郵便番号（ExcelAPI）
- lookup_address      : 郵便番号 → 住所（zipcloud）
"""
import json
import re
import urllib.request
import urllib.parse

_API_URL = "https://api.excelapi.org/post/zipcode"
_HEARTRAILS_URL = "http://geoapi.heartrails.com/api/json"
_TIMEOUT = 5  # seconds


def lookup_postal_code(address: str) -> str | None:
    """
    住所文字列から郵便番号（XXX-XXXX 形式）を返す。
    見つからない・通信失敗の場合は None。
    """
    addr = address.strip()
    if not addr:
        return None
    params = urllib.parse.urlencode({"address": addr})
    try:
        with urllib.request.urlopen(f"{_API_URL}?{params}", timeout=_TIMEOUT) as resp:
            code = resp.read().decode("utf-8").strip()
        if not code:
            return None
        # 7桁 → XXX-XXXX に整形
        digits = code.replace("-", "")
        if len(digits) == 7 and digits.isdigit():
            return f"{digits[:3]}-{digits[3:]}"
        return code if code else None
    except Exception:
        return None


def lookup_address(postal: str) -> str | None:
    """
    郵便番号（XXX-XXXX または 7桁）から住所文字列を返す（HeartRails Geo API）。
    - 住所が見つからない場合は None を返す。
    - 通信エラーの場合は ConnectionError を送出する。
    """
    digits = re.sub(r"\D", "", postal)
    if len(digits) != 7:
        return None
    url = f"{_HEARTRAILS_URL}?method=searchByPostal&postal={digits}"
    try:
        with urllib.request.urlopen(url, timeout=_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        raise ConnectionError(f"郵便番号検索APIへの接続に失敗しました：{e}") from e
    locations = data.get("response", {}).get("location")
    if not locations:
        return None
    loc = locations[0]
    return (loc.get("prefecture") or "") + (loc.get("city") or "") + (loc.get("town") or "")
