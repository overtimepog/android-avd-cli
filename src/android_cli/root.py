"""Magisk root grant — auto-approve su requests on boot.

Handles the chicken-and-egg problem on fresh AVD boots:
Magisk prompts for approval via a dialog in the Magisk app,
but the emulator runs headless. This module auto-approves
by sending key events to the SuRequestActivity dialog.

Usage:
    android root [avd_name]          # Grant root
    android root [avd_name] --check  # Verify root without triggering dialog
    android root [avd_name] --persist  # Grant + remember decision
"""

import subprocess
import time
from typing import Optional

from android_cli.config import adb_binary

# Approval button press patterns (key sequences to try in order).
# Each pattern is a list of (action, key) tuples where action is:
#   'key'  — press a key
#   'sleep' — wait N seconds
_APPROVAL_PATTERNS: list[list[tuple[str, str | float]]] = [
    # Pattern 1: Tab -> Tab -> Enter (focus: Deny -> Grant -> Click Grant)
    [("key", "KEYCODE_TAB"), ("sleep", 0.5),
     ("key", "KEYCODE_TAB"), ("sleep", 0.5),
     ("key", "KEYCODE_ENTER")],

    # Pattern 2: Tab -> Tab -> Tab -> Enter (includes Remember checkbox)
    [("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER")],

    # Pattern 3: Tab -> Down -> Down -> Enter (alternative layout)
    [("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_DOWN"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_DOWN"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER")],

    # Pattern 4: Tab -> Tab -> Right -> Enter (focus: Deny -> Grant -> Remember checkbox -> Enter toggles)
    [("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_RIGHT"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER")],
]

# Approval patterns with "Remember" checked (extra Tab to reach checkbox, Enter to toggle, Tab back, Enter to approve)
_APPROVAL_PATTERNS_PERSIST: list[list[tuple[str, str | float]]] = [
    # Pattern 1P: Tab -> Tab -> Tab (focus Remember checkbox) -> Enter (check it) -> Tab -> Enter (Grant)
    [("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER"), ("sleep", 0.3),
     ("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER")],

    # Pattern 2P: Tab -> Down -> Down -> Enter (check remember) -> Left -> Enter (Grant)
    [("key", "KEYCODE_TAB"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_DOWN"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_DOWN"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER"), ("sleep", 0.3),
     ("key", "KEYCODE_DPAD_LEFT"), ("sleep", 0.3),
     ("key", "KEYCODE_ENTER")],
]


def grant_magisk_root(
    avd_name: str | None = None,
    sdk: str | None = None,
    check_only: bool = False,
    persist: bool = False,
    max_attempts: int = 3,
) -> bool:
    """Auto-grant root via Magisk su dialog key events.

    Works by:
    1. Running `su -c id` which triggers the Magisk su dialog
    2. Trying multiple key-event patterns to approve
    3. Verifying root access was granted
    4. Retrying with alternative patterns if needed

    Args:
        avd_name: AVD name (unused currently, for future multi-emu support)
        sdk: Android SDK path override
        check_only: If True, only check root status (no dialog trigger)
        persist: If True, also check "Remember" in the su dialog
        max_attempts: Max retry attempts with different patterns

    Returns:
        True if root is confirmed.
    """
    adb = find_adb(sdk)
    if not adb:
        return False

    # Check-only mode
    if check_only:
        if _check_root(adb):
            print("Root: GRANTED")
            return True
        else:
            print("Root: NOT GRANTED")
            return False

    # Check if already rooted
    if _check_root(adb):
        print("Root access already granted.")
        return True

    # Retry loop with different patterns
    patterns = _APPROVAL_PATTERNS_PERSIST if persist else _APPROVAL_PATTERNS

    for attempt in range(1, max_attempts + 1):
        if attempt > 1:
            print(f"Retry {attempt}/{max_attempts}...")

        # First, try opening the Magisk app to ensure it's ready
        if attempt == 1 or attempt == 3:
            _open_magisk_app(adb)

        # Trigger the su request
        print("  Triggering su request...")
        _trigger_su(adb)
        time.sleep(2)

        # Try each pattern until one works
        for i, pattern in enumerate(patterns):
            _send_key_sequence(adb, pattern)
            time.sleep(1.5)

            if _check_root(adb):
                print("Root access granted successfully.")
                return True

            # Brief cooldown before next pattern
            time.sleep(1)

    print("Failed to grant root after multiple attempts.")
    print("Try: 1) 'android boot <avd> --root' to boot with auto-grant")
    print("     2) Open Magisk Manager on the emulator manually")
    print("     3) Reboot the emulator and try again")
    return False


def check_root(sdk: str | None = None) -> bool:
    """Quick check: is root available? Returns True if `su -c id` returns uid=0."""
    adb = find_adb(sdk)
    if not adb:
        return False
    return _check_root(adb)


def _check_root(adb: str) -> bool:
    """Check if `su -c id` returns uid=0."""
    try:
        result = subprocess.run(
            [adb, "shell", "su", "-c", "id"],
            capture_output=True, text=True, timeout=10,
        )
        return "uid=0" in result.stdout
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError):
        return False


def _trigger_su(adb: str) -> None:
    """Trigger a su request that opens the Magisk approval dialog."""
    try:
        subprocess.Popen(
            [adb, "shell", "su", "-c", "echo root_granted > /dev/null"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception:
        pass


def _open_magisk_app(adb: str) -> None:
    """Launch the Magisk app so the su dialog can be displayed."""
    try:
        subprocess.run(
            [adb, "shell", "monkey", "-p", "com.topjohnwu.magisk", "1"],
            capture_output=True, text=True, timeout=5,
        )
    except Exception:
        pass


def _send_key_sequence(adb: str, pattern: list[tuple[str, str | float]]) -> None:
    """Execute a sequence of key events and sleeps."""
    for action, value in pattern:
        if action == "key":
            try:
                subprocess.run(
                    [adb, "shell", "input", "keyevent", str(value)],
                    capture_output=True, text=True, timeout=5,
                )
            except Exception:
                return
        elif action == "sleep":
            time.sleep(float(value))


def find_adb(sdk: str | None = None) -> str | None:
    """Get the ADB binary path, or None if not found."""
    try:
        return adb_binary(sdk)
    except FileNotFoundError:
        print("ADB not found. Is the Android SDK installed?", file=__import__("sys").stderr)
        return None
