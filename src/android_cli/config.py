"""Android SDK path detection."""

import os
import shutil
from pathlib import Path


def find_sdk_root(override: str | None = None) -> str | None:
    """Locate the Android SDK root directory.

    Checks, in order:
    1. Explicit override passed by the user
    2. ANDROID_HOME env var
    3. ANDROID_SDK_ROOT env var
    4. Common macOS paths (~/Library/Android/sdk)
    5. Common Linux paths (~/Android/Sdk, /usr/lib/android-sdk)
    6. `emulator` on PATH (walk up from its location)
    """
    if override:
        if _valid_sdk(override):
            return override
        return None

    for var in ("ANDROID_HOME", "ANDROID_SDK_ROOT"):
        val = os.environ.get(var)
        if val and _valid_sdk(val):
            return val

    candidates = [
        os.path.expanduser("~/Library/Android/sdk"),        # macOS
        os.path.expanduser("~/Android/Sdk"),                 # Linux
        "/usr/lib/android-sdk",                              # Debian/Ubuntu
        "/opt/android-sdk",                                  # Manual install
    ]
    for c in candidates:
        if _valid_sdk(c):
            return c

    # Try to locate via `emulator` on PATH
    emu = shutil.which("emulator")
    if emu:
        # Walk up from the emulator binary to find SDK root
        p = Path(emu).resolve().parent.parent  # .../emulator/ -> parent = emulator/
        if _valid_sdk(str(p)):
            return str(p)

    return None


def _valid_sdk(path: str) -> bool:
    """Check if a directory looks like a valid Android SDK root."""
    p = Path(path)
    return (p / "emulator" / "emulator").exists() or (p / "emulator" / "emulator.exe").exists()


def emulator_binary(sdk: str | None = None) -> str:
    """Get the full path to the emulator binary."""
    root = find_sdk_root(sdk)
    if not root:
        # Fall back to PATH
        emu = shutil.which("emulator")
        if emu:
            return emu
        raise FileNotFoundError("Android emulator not found. Set ANDROID_HOME or install Android SDK.")
    return os.path.join(root, "emulator", "emulator")


def adb_binary(sdk: str | None = None) -> str:
    """Get the full path to the ADB binary."""
    root = find_sdk_root(sdk)
    if not root:
        adb = shutil.which("adb")
        if adb:
            return adb
        raise FileNotFoundError("adb not found. Set ANDROID_HOME or install Android SDK.")
    return os.path.join(root, "platform-tools", "adb")


def avd_dir(sdk: str | None = None) -> str:
    """Get the AVD directory path."""
    root = find_sdk_root(sdk)
    if not root:
        return os.path.expanduser("~/.android/avd")
    avd = os.environ.get("ANDROID_AVD_HOME", "")
    if avd:
        return avd
    return os.path.expanduser("~/.android/avd")
