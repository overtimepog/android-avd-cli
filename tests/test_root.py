"""Tests for root module."""

import subprocess
from unittest.mock import patch, MagicMock
from android_cli.root import _check_root, grant_magisk_root, _APPROVAL_PATTERNS


class TestCheckRoot:
    def test_root_granted(self):
        """Should return True when su -c id returns uid=0."""
        mock_result = MagicMock()
        mock_result.stdout = "uid=0(root) gid=0(root)"

        with patch("subprocess.run", return_value=mock_result):
            assert _check_root("/fake/adb") is True

    def test_root_not_granted_timeout(self):
        """Should return False when su times out."""
        with patch(
            "subprocess.run",
            side_effect=subprocess.TimeoutExpired(cmd="su", timeout=10),
        ):
            assert _check_root("/fake/adb") is False

    def test_root_not_granted_no_root(self):
        """Should return False when su -c id doesn't show uid=0."""
        mock_result = MagicMock()
        mock_result.stdout = "uid=2000(shell)"

        with patch("subprocess.run", return_value=mock_result):
            assert _check_root("/fake/adb") is False


class TestGrantMagiskRoot:
    def test_already_rooted(self):
        """Should return immediately if root already granted."""
        with patch("android_cli.root._check_root", return_value=True):
            with patch("android_cli.root._trigger_su") as mock:
                with patch("android_cli.root.find_adb", return_value="/fake/adb"):
                    result = grant_magisk_root(sdk="/fake/sdk", max_attempts=1)
                    assert result is True
                    mock.assert_not_called()

    def test_grant_succeeds_on_first_try(self):
        """Should succeed when the first approval pattern works."""
        # First check shows no root, second check (after pattern) shows root
        calls = [False, True]

        with patch("android_cli.root._check_root", side_effect=calls):
            with patch("android_cli.root.find_adb", return_value="/fake/adb"):
                with patch("android_cli.root._trigger_su"):
                    with patch("android_cli.root._open_magisk_app"):
                        with patch("android_cli.root._send_key_sequence"):
                            result = grant_magisk_root(max_attempts=1)
                            assert result is True

    def test_all_patterns_fail(self):
        """Should return False after all attempts fail."""
        with patch("android_cli.root._check_root", return_value=False):
            with patch("android_cli.root.find_adb", return_value="/fake/adb"):
                with patch("android_cli.root._trigger_su"):
                    with patch("android_cli.root._open_magisk_app"):
                        with patch("android_cli.root._send_key_sequence"):
                            result = grant_magisk_root(max_attempts=1)
                            assert result is False

    def test_check_only_rooted(self):
        """Check-only mode should verify without triggering."""
        with patch("android_cli.root._check_root", return_value=True):
            with patch("android_cli.root.find_adb", return_value="/fake/adb"):
                result = grant_magisk_root(check_only=True, max_attempts=1)
                assert result is True

    def test_check_only_not_rooted(self):
        """Check-only mode should return False if not rooted."""
        with patch("android_cli.root._check_root", return_value=False):
            with patch("android_cli.root.find_adb", return_value="/fake/adb"):
                result = grant_magisk_root(check_only=True, max_attempts=1)
                assert result is False


def test_approval_patterns_defined():
    """Should have at least one approval pattern."""
    assert len(_APPROVAL_PATTERNS) > 0
    for pattern in _APPROVAL_PATTERNS:
        assert len(pattern) > 0
