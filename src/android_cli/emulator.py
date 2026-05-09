"""Emulator lifecycle — list, boot, kill, status, snapshots."""

import subprocess
import time

from android_cli.config import emulator_binary, adb_binary


def list_avds(sdk: str | None = None) -> list[str]:
    """Return list of available AVD names."""
    emu = emulator_binary(sdk)
    result = subprocess.run(
        [emu, "-list-avds"], capture_output=True, text=True, timeout=15
    )
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
    wait: bool = False,
    auto_root: bool = False,
    timeout: int = 120,
    extra: list[str] | None = None,
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
    avd_name: str | None = None, force: bool = False, sdk: str | None = None
) -> bool:
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


def snapshot_list(avd_name: str, sdk: str | None = None) -> list[str]:
    """List snapshots for an AVD.

    Uses the 'emulator -avd <name> -snapshot-list' command.
    """
    emu = emulator_binary(sdk)
    try:
        result = subprocess.run(
            [emu, "-avd", avd_name, "-snapshot-list"],
            capture_output=True,
            text=True,
            timeout=15,
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
            capture_output=True,
            text=True,
            timeout=60,
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
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
