"""Emulator lifecycle — list, boot, kill, status, snapshots."""

import os
import signal
import subprocess
import time
from pathlib import Path

from android_cli.config import emulator_binary, avd_dir, adb_binary


def list_avds(sdk: str | None = None) -> list[str]:
    """Return list of available AVD names."""
    emu = emulator_binary(sdk)
    result = subprocess.run([emu, "-list-avds"], capture_output=True, text=True, timeout=15)
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def boot_avd(
    avd_name: str,
    sdk: str | None = None,
    headed: bool = False,
    no_snapshot: bool = False,
    wipe_data: bool = False,
    read_only: bool = False,
    extra: list[str] | None = None,
) -> bool:
    """Boot an AVD in the background. Returns True if launched successfully."""
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
        return True
    except FileNotFoundError:
        print(f"Emulator binary not found at: {emu}", file=__import__("sys").stderr)
        return False


def kill_avd(avd_name: str | None = None, force: bool = False, sdk: str | None = None) -> bool:
    """Stop a running emulator.

    If avd_name is None, stops ALL running emulators.
    """
    emu = emulator_binary(sdk)
    cmd = [emu, "-kill"]
    if avd_name:
        cmd.extend(["-avd", avd_name])

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    if result.returncode != 0:
        print(f"Warning: emulator -kill returned {result.returncode}")
        print(result.stderr)
        return False
    print(f"Emulator {avd_name or '(all)'} stopped.")
    return True


def get_status(avd_name: str | None = None, sdk: str | None = None) -> list[dict]:
    """Check which AVDs are running.

    Returns list of dicts with keys: name, running, pid, boot_completed.
    """
    emu = emulator_binary(sdk)
    adb = adb_binary(sdk)

    # List running emulator processes
    try:
        result = subprocess.run(
            ["pgrep", "-f", "qemu-system"], capture_output=True, text=True, timeout=10
        )
        running_pids = [p.strip() for p in result.stdout.splitlines() if p.strip()]
    except (subprocess.TimeoutExpired, FileNotFoundError):
        running_pids = []

    # List all AVDs
    avds = list_avds(sdk)

    results = []
    for avd in avds:
        booted = False
        if running_pids:
            # Check if this AVD is running by trying ADB
            try:
                out = subprocess.run(
                    [adb, "shell", "getprop", "sys.boot_completed"],
                    capture_output=True, text=True, timeout=5,
                )
                booted = out.stdout.strip() == "1"
            except (subprocess.TimeoutExpired, FileNotFoundError):
                pass
        results.append({
            "name": avd,
            "running": bool(running_pids),
            "pid": int(running_pids[0]) if running_pids else None,
            "boot_completed": booted,
        })

    # If an AVD is running but not in the list, add a placeholder
    if running_pids and not results:
        results.append({
            "name": "(unknown)",
            "running": True,
            "pid": int(running_pids[0]),
            "boot_completed": False,
        })

    return results


def wait_for_boot(
    adb_path: str,
    timeout: int = 120,
    poll_interval: int = 3,
) -> bool:
    """Wait for the emulator to finish booting.

    Polls sys.boot_completed until it returns '1' or timeout is reached.
    """
    for _ in range(timeout // poll_interval):
        try:
            result = subprocess.run(
                [adb_path, "shell", "getprop", "sys.boot_completed"],
                capture_output=True, text=True, timeout=10,
            )
            if result.stdout.strip() == "1":
                return True
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        time.sleep(poll_interval)
    return False


def snapshot_list(avd_name: str, sdk: str | None = None) -> list[str]:
    """List snapshots for an AVD.

    Uses the 'emulator -avd <name> -snapshot-list' command.
    """
    emu = emulator_binary(sdk)
    try:
        result = subprocess.run(
            [emu, "-avd", avd_name, "-snapshot-list"],
            capture_output=True, text=True, timeout=15,
        )
        lines = result.stdout.splitlines()
        snapshots = []
        in_table = False
        for line in lines:
            if "Savegame" in line and "Tag" in line:
                in_table = True
                continue
            if in_table and line.strip() and not line.startswith("--"):
                parts = line.split()
                if len(parts) >= 2:
                    snapshots.append(parts[0])
        return snapshots
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return []


def snapshot_save(avd_name: str, name: str, sdk: str | None = None) -> bool:
    """Save a snapshot. Requires the emulator to be running."""
    emu = emulator_binary(sdk)
    try:
        result = subprocess.run(
            [emu, "-avd", avd_name, "-snapshot", name, "-snapshot-save"],
            capture_output=True, text=True, timeout=60,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def snapshot_delete(avd_name: str, name: str, sdk: str | None = None) -> bool:
    """Delete a snapshot."""
    emu = emulator_binary(sdk)
    try:
        result = subprocess.run(
            [emu, "-avd", avd_name, "-snapshot", name, "-snapshot-delete"],
            capture_output=True, text=True, timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
