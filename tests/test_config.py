"""Tests for config module."""

from android_cli import __version__
from android_cli.config import find_sdk_root, _valid_sdk


class TestVersion:
    def test_version(self):
        assert isinstance(__version__, str)
        assert "." in __version__


class TestValidSdk:
    def test_invalid_path(self):
        assert not _valid_sdk("/nonexistent/path")

    def test_empty_path(self):
        assert not _valid_sdk("")


class TestFindSdkRoot:
    def test_override_invalid(self):
        assert find_sdk_root("/nonexistent") is None
