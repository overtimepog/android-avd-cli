"""Emulator lifecycle — list, boot, kill, status, snapshots."""

import os
import subprocess
import time
from typing import Optional, List

from android_cli.config import emulator_binary, adb_binary


def list_avds(sdk: Optional[str] = None) -> List[str]:
    """Return list of available AVD names."""
    try:
        emu = emulator_binary(sdk)
    except FileNotFoundError:
        return []
    result = subprocess.run(
        [emu, "-list-avds"], capture_output=True, text=True, timeout=15
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def boot_avd(
    avd_name: str,
    sdk: Optional[str] = None,
    headed: bool = True,
    no_snapshot: bool = False,
    wipe_data: bool = False,
    read_only: bool = False,
    wait: bool = False,
    auto_root: bool = False,
    timeout: int = 120,
    extra: Optional[List[str]] = None,
) -> bool:
    """Boot an AVD in the background. Returns True if launched successfully.

    If wait=True, blocks until sys.boot_completed.
    If auto_root=True, grants root via Magisk after boot.
    """
    emu = emulator_binary(sdk)
    adb = adb_binary(sdk)

    cmd = [emu, "-avd", avd_name]
    if not headed:
        cmd.append("-no-window")
    if no_snapshot:
        cmd.append("-no-snapshot")
    if wipe_data:
        cmd.append("-wipe-data")
    if read_only:
        cmd.append("-read-only")
    if extra:
        cmd.extend(extra)

    try:
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        print(f"Booting {avd_name} (PID {proc.pid})...")

        if wait:
            print(f"Waiting up to {timeout}s for boot... ", end="", flush=True)
            ok = wait_for_boot(adb, timeout=timeout)
            print("OK" if ok else "TIMEOUT")

            if ok and auto_root:
                from android_cli.root import grant_magisk_root  # noqa: PLC0415

                grant_magisk_root(sdk=sdk)

        return True
    except FileNotFoundError:
        print(f"Emulator binary not found at: {emu}", file=__import__("sys").stderr)
        return False


def kill_avd(
    avd_name: Optional[str] = None, force: bool = False, sdk: Optional[str] = None
) -> bool:
    """Stop a running emulator.

    If avd_name is None, stops ALL running emulators.
    Uses ADB emu kill first (reliable), then process kill as fallback.
    """
    adb = adb_binary(sdk)
    killed = False

    # Method 1: ADB emu kill (most reliable)
    try:
        result = subprocess.run(
            [adb, "emu", "kill"], capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            killed = True
    except (subprocess.TimeoutExpired, FileNotFoundError):
        pass

    # Method 2: Force kill by PID
    if force or not killed:
        try:
            result = subprocess.run(
                ["pkill", "-f", "qemu-system"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                killed = True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass

    if killed:
        print(f"Emulator {avd_name or '(all)'} stopped.")
        return True
    print("No running emulator found.")
    return False


def get_status(avd_name: Optional[str] = None, sdk: Optional[str] = None) -> List[dict]:
    """Check which AVDs are running.

    Returns list of dicts with keys: name, running, pid, port, serial, boot_completed.
    Supports multiple running emulators.
    """
    from android_cli.adb import devices as adb_devices  # noqa: PLC0415

    adb = adb_binary(sdk)

    # Get AVD names from running emulator processes (via their cmdline)
    running_avds = {}  # pid -> avd_name
    try:
        result = subprocess.run(
            ["pgrep", "-f", "qemu-system"], capture_output=True, text=True, timeout=10
        )
        pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
        for pid in pids:
            try:
                cmdline = subprocess.run(
                    ["ps", "-p", pid, "-o", "command="],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                # Extract -avd <name> from cmdline
                import re  # noqa: PLC0415

                m = re.search(r"-avd\s+(\S+)", cmdline.stdout)
                if m:
                    running_avds[pid] = m.group(1)
                else:
                    running_avds[pid] = "(unknown)"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                running_avds[pid] = "(unknown)"
    except (subprocess.TimeoutExpired, FileNotFoundError):
        running_avds = {}

    # Get connected ADB devices with serials
    adb_device_list = adb_devices(sdk)

    # List all available AVDs
    all_avds = list_avds(sdk)

    results = []
    # Add running AVDs first
    for pid, name in running_avds.items():
        booted = False
        serial = None
        port = None

        # Find matching ADB device
        for d in adb_device_list:
            if d["status"] == "device":
                serial = d["serial"]
                m = __import__("re").search(r"emulator-(\d+)", serial)
                if m:
                    port = int(m.group(1))

        # Check boot status
        if serial:
            try:
                out = subprocess.run(
                    [adb, "-s", serial, "shell", "getprop", "sys.boot_completed"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                booted = out.stdout.strip() == "1"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass

        results.append(
            {
                "name": name,
                "running": True,
                "pid": int(pid),
                "port": port,
                "serial": serial,
                "boot_completed": booted,
            }
        )

    # Add available (stopped) AVDs if looking for a specific one or all
    if avd_name:
        if avd_name not in [r["name"] for r in results]:
            results.append(
                {
                    "name": avd_name,
                    "running": False,
                    "pid": None,
                    "port": None,
                    "serial": None,
                    "boot_completed": False,
                }
            )
    elif not running_avds:
        for avd in all_avds:
            if avd not in [r["name"] for r in results]:
                results.append(
                    {
                        "name": avd,
                        "running": False,
                        "pid": None,
                        "port": None,
                        "serial": None,
                        "boot_completed": False,
                    }
                )

    return results


def wait_for_boot(
    adb_path: str,
    timeout: int = 120,
    poll_interval: int = 3,
    show_progress: bool = True,
) -> bool:
    """Wait for the emulator to finish booting.

    Polls sys.boot_completed until it returns '1' or timeout is reached.
    If show_progress=True, prints dots and an elapsed timer.
    """

    start = time.monotonic()
    for _ in range(timeout // poll_interval):
        try:
            result = subprocess.run(
                [adb_path, "shell", "getprop", "sys.boot_completed"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.stdout.strip() == "1":
                if show_progress:
                    elapsed = time.monotonic() - start
                    print(f" [{elapsed:.0f}s]")
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        if show_progress:
            print(".", end="", flush=True)
        time.sleep(poll_interval)
    if show_progress:
        elapsed = time.monotonic() - start
        print(f" TIMEOUT [{elapsed:.0f}s]")
    return False


def snapshot_list(avd_name: str, sdk: Optional[str] = None) -> List[str]:
    """List snapshots for an AVD by reading the snapshots directory."""
    adb = adb_binary(sdk)
    avd_path = os.path.expanduser(f"~/.android/avd/{avd_name}.avd/snapshots")
    try:
        snapshots = [
            d
            for d in os.listdir(avd_path)
            if os.path.isdir(os.path.join(avd_path, d)) and d != "default_boot"
        ]
        return sorted(snapshots)
    except (FileNotFoundError, OSError):
        # Fallback: try ADB emu command
        try:
            result = subprocess.run(
                [adb, "emu", "avd", "snapshot", "list"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            lines = [ln.strip() for ln in result.stdout.splitlines() if ln.strip()]
            return [ln for ln in lines if ln and ":" not in ln]
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return []


def snapshot_save(avd_name: str, name: str, sdk: Optional[str] = None) -> bool:
    """Save a snapshot via ADB emu console (more reliable than emulator binary)."""
    adb = adb_binary(sdk)
    try:
        result = subprocess.run(
            [adb, "emu", "avd", "snapshot", "save", name],
            capture_output=True,
            text=True,
            timeout=60,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def snapshot_delete(avd_name: str, name: str, sdk: Optional[str] = None) -> bool:
    """Delete a snapshot via ADB emu console."""
    adb = adb_binary(sdk)
    try:
        result = subprocess.run(
            [adb, "emu", "avd", "snapshot", "delete", name],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
