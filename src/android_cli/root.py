"""Magisk root grant — auto-approve su requests on boot.

Handles the chicken-and-egg problem on fresh AVD boots:
Magisk prompts for approval via a dialog in the Magisk app,
but the emulator runs headless. This module auto-approves
by sending key events to the SuRequestActivity dialog.

Usage:
    android root [avd_name]
"""

import subprocess
import time
from typing import Optional

from android_cli.config import adb_binary


def grant_magisk_root(avd_name: str | None = None, sdk: str | None = None) -> bool:
    """Auto-grant root via Magisk su dialog key events.

    Works by:
    1. Running `su -c id` which triggers the Magisk su dialog
    2. Sending Tab → Tab → Enter to approve
    3. Verifying root access was granted

    Returns True if root is confirmed.
    """
    adb = find_adb(sdk)
    if not adb:
        return False

    # Step 1: Check if already rooted
    if _check_root(adb):
        print("Root access already granted.")
        return True

    # Step 2: Launch su request in the background
    print("Triggering Magisk su dialog...")
    _trigger_su(adb)

    # Step 3: Wait for dialog to appear
    time.sleep(3)

    # Step 4: Auto-approve via key events
    print("Auto-approving root request...")
    _auto_approve(adb)

    # Step 5: Wait for approval to process
    time.sleep(2)

    # Step 6: Verify
    if _check_root(adb):
        print("Root access granted successfully.")
        return True
    else:
        print("Failed to grant root. Try running 'android root' again, or open Magisk manually.")
        return False


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


def _auto_approve(adb: str) -> None:
    """Send key events to approve the Magisk su dialog.

    The Magisk SuRequestActivity dialog has:
    - Tab moves focus between Deny/Grant/Remember buttons
    - Enter confirms the focused button
    """
    for key in ["KEYCODE_TAB", "KEYCODE_TAB", "KEYCODE_ENTER"]:
        try:
            subprocess.run(
                [adb, "shell", "input", "keyevent", key],
                capture_output=True, text=True, timeout=5,
            )
            time.sleep(0.5)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass


def find_adb(sdk: str | None = None) -> str | None:
    """Get the ADB binary path, or None if not found."""
    try:
        return adb_binary(sdk)
    except FileNotFoundError:
        print("ADB not found. Is the Android SDK installed?", file=__import__("sys").stderr)
        return None
