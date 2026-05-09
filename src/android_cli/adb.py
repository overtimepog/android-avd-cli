"""ADB interaction — shell commands, device info, property queries."""

import subprocess

from android_cli.config import adb_binary


def find_adb(sdk: str | None = None) -> str | None:
    """Get the ADB binary path, or None if not found."""
    try:
        return adb_binary(sdk)
    except FileNotFoundError:
        return None


def adb_shell(
    cmd: list[str],
    avd_name: str | None = None,
    sdk: str | None = None,
    use_root: bool = False,
    timeout: int = 30,
) -> str | None:
    """Run a command via `adb shell`.

    If use_root is True, prefixes with `su -c`.
    Returns stdout, or None on failure.
    """
    adb = find_adb(sdk)
    if not adb:
        print("ADB not found", file=__import__("sys").stderr)
        return None

    if not cmd:
        return None

    shell_cmd = cmd if not use_root else ["su", "-c", " ".join(cmd)]

    try:
        result = subprocess.run(
            [adb, "shell"] + shell_cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode != 0 and result.stderr.strip():
            print(result.stderr.strip(), file=__import__("sys").stderr)
        return result.stdout
    except subprocess.TimeoutExpired:
        print("ADB shell command timed out", file=__import__("sys").stderr)
        return None
    except FileNotFoundError:
        print(f"ADB binary not found at: {adb}", file=__import__("sys").stderr)
        return None


def device_info(
    avd_name: str | None = None, sdk: str | None = None
) -> dict[str, str] | None:
    """Get device properties via ADB.

    Returns a dict of device info, or None if no device is connected.
    """
    adb = find_adb(sdk)
    if not adb:
        return None

    props = {
        "ro.product.model": "model",
        "ro.build.version.release": "android_version",
        "ro.build.version.sdk": "sdk_level",
        "ro.product.cpu.abi": "arch",
        "ro.serialno": "serial",
        "ro.build.display.id": "build",
        "persist.sys.timezone": "timezone",
    }

    info: dict[str, str] = {}
    for prop, key in props.items():
        try:
            result = subprocess.run(
                [adb, "shell", "getprop", prop],
                capture_output=True,
                text=True,
                timeout=5,
            )
            val = result.stdout.strip()
            if val:
                info[key] = val
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    # Also check root status
    try:
        result = subprocess.run(
            [adb, "shell", "which", "su"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        info["has_su"] = "yes" if result.stdout.strip() else "no"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        info["has_su"] = "unknown"

    try:
        result = subprocess.run(
            [adb, "shell", "su", "-v"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.stdout.strip():
            info["magisk_version"] = result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    return info if info else None


def devices(sdk: str | None = None) -> list[dict]:
    """List connected ADB devices."""
    adb = find_adb(sdk)
    if not adb:
        return []

    try:
        result = subprocess.run(
            [adb, "devices"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = result.stdout.splitlines()
        devices_list = []
        for line in lines[1:]:  # Skip "List of devices attached"
            line = line.strip()
            if line and "\t" in line:
                serial, status = line.split("\t", 1)
                devices_list.append({"serial": serial, "status": status})
        return devices_list
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []
