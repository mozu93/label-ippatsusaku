# -*- coding: utf-8 -*-
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
import app.utils.postal_lookup as pl


@pytest.fixture(autouse=True)
def _clear_cache():
    pl._postal_cache.clear()
    yield
    pl._postal_cache.clear()


class _FakeResponse:
    def __init__(self, body: bytes):
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_lookup_postal_code_caches_same_address(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"1000001")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    r1 = pl.lookup_postal_code("東京都千代田区")
    r2 = pl.lookup_postal_code("東京都千代田区")

    assert r1 == "100-0001"
    assert r2 == "100-0001"
    assert len(calls) == 1


def test_lookup_postal_code_different_addresses_each_call_api(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"1000001")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    pl.lookup_postal_code("東京都千代田区")
    pl.lookup_postal_code("大阪府大阪市")

    assert len(calls) == 2


def test_lookup_postal_code_not_found_result_is_not_cached(monkeypatch):
    calls = []

    def fake_urlopen(url, timeout=None):
        calls.append(url)
        return _FakeResponse(b"")

    monkeypatch.setattr(pl.urllib.request, "urlopen", fake_urlopen)

    r1 = pl.lookup_postal_code("存在しない住所")
    r2 = pl.lookup_postal_code("存在しない住所")

    assert r1 is None
    assert r2 is None
    # Noneは通信失敗（一時的な障害）と本当に見つからない場合の区別がつかないため
    # キャッシュしない。よって同一住所を再度検索するとAPIが再度呼ばれる。
    assert len(calls) == 2
