"""Tests for emulator module."""

from unittest.mock import patch, MagicMock
from android_cli.emulator import wait_for_boot, list_avds


def test_list_avds_no_sdk(tmp_path):
    """list_avds should return empty list if emulator binary not found."""
    from android_cli.config import find_sdk_root
    if not find_sdk_root():
        assert list_avds() == []


class TestWaitForBoot:
    def test_immediate_boot_complete(self):
        """Should return True when boot_completed=1 on first poll."""
        mock_result = MagicMock()
        mock_result.stdout = "1"

        with patch("subprocess.run", return_value=mock_result):
            result = wait_for_boot("/fake/adb", timeout=30, show_progress=False)
            assert result is True

    def test_timeout(self):
        """Should return False when boot never completes."""
        mock_result = MagicMock()
        mock_result.stdout = "0"

        with patch("subprocess.run", return_value=mock_result):
            result = wait_for_boot("/fake/adb", timeout=6, poll_interval=2, show_progress=False)
            assert result is False
