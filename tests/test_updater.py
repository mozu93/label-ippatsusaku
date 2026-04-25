# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.utils.updater import is_newer_version


def test_newer_version():
    assert is_newer_version("1.0.0", "1.0.1") is True

def test_same_version():
    assert is_newer_version("1.0.0", "1.0.0") is False

def test_older_version():
    assert is_newer_version("1.0.1", "1.0.0") is False

def test_minor_bump():
    assert is_newer_version("1.0.0", "1.1.0") is True

def test_major_bump():
    assert is_newer_version("1.0.0", "2.0.0") is True

def test_v_prefix_stripped():
    assert is_newer_version("1.0.0", "v1.0.1") is True
