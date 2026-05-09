"""Main CLI entry point for android-cli.

Subcommands:
  list          List available AVDs
  boot          Boot an emulator
  status        Check boot status
  root          Grant root via Magisk
  kill          Stop an emulator
  shell         Run ADB commands
  info          Get device info
  snapshot      Manage snapshots
  sdk-path      Show Android SDK path
"""

import argparse
import sys

from android_cli.config import find_sdk_root
from android_cli.emulator import (
    list_avds,
    boot_avd,
    kill_avd,
    get_status,
    snapshot_list,
    snapshot_save,
    snapshot_delete,
)
from android_cli.adb import adb_shell, device_info
from android_cli.root import grant_magisk_root


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="android",
        description="Android Emulator AVD CLI",
        usage="android <command> [options]",
    )
    parser.add_argument(
        "--version", action="version", version=f"android-cli {__import__('android_cli').__version__}"
    )
    parser.add_argument(
        "--sdk", help="Path to Android SDK root (auto-detected if omitted)"
    )

    sub = parser.add_subparsers(dest="command", required=True)

    # --- list ---
    p_list = sub.add_parser("list", help="List available AVDs")

    # --- boot ---
    p_boot = sub.add_parser("boot", help="Boot an emulator")
    p_boot.add_argument("avd", help="AVD name (use `android list`)")
    p_boot.add_argument("--headed", action="store_true", help="Show emulator window (not headless)")
    p_boot.add_argument("--no-snapshot", action="store_true", help="Skip snapshot loading")
    p_boot.add_argument("--wipe-data", action="store_true", help="Wipe user data partition")
    p_boot.add_argument("--read-only", action="store_true", help="Boot read-only")
    p_boot.add_argument("--wait", "-w", action="store_true",
                        help="Wait for boot to complete before returning")
    p_boot.add_argument("--root", action="store_true",
                        help="Auto-grant root via Magisk after boot (implies --wait)")
    p_boot.add_argument("--timeout", type=int, default=120,
                        help="Max seconds to wait for boot (default: 120)")
    p_boot.add_argument("--extra", "-X", action="append", help="Extra emulator flags (can repeat)")

    # --- status ---
    p_status = sub.add_parser("status", help="Check if emulator is booted")
    p_status.add_argument("avd", nargs="?", help="AVD name (lists all if omitted)")

    # --- root ---
    p_root = sub.add_parser("root", help="Grant root via Magisk")
    p_root.add_argument("avd", nargs="?", help="AVD name (uses running emulator)")
    p_root.add_argument("--check", action="store_true",
                        help="Check root status without triggering dialog")
    p_root.add_argument("--persist", action="store_true",
                        help="Check 'Remember' in the su dialog for persistent root")
    p_root.add_argument("--retries", type=int, default=3,
                        help="Max retry attempts (default: 3)")

    # --- kill ---
    p_kill = sub.add_parser("kill", help="Stop a running emulator")
    p_kill.add_argument("avd", nargs="?", help="AVD name (stops all if omitted)")
    p_kill.add_argument("--force", "-f", action="store_true", help="Force kill")

    # --- shell ---
    p_shell = sub.add_parser("shell", help="Run an ADB shell command")
    p_shell.add_argument("cmd", nargs=argparse.REMAINDER, help="Command and arguments")
    p_shell.add_argument("--avd", help="Target AVD (uses first if omitted)")

    # --- info ---
    p_info = sub.add_parser("info", help="Get device info")
    p_info.add_argument("avd", nargs="?", help="AVD name")

    # --- snapshot ---
    p_snap = sub.add_parser("snapshot", help="Manage snapshots")
    p_snap.add_argument("action", choices=["list", "save", "delete"], help="Snapshot action")
    p_snap.add_argument("name", nargs="?", help="Snapshot name (required for save/delete)")
    p_snap.add_argument("--avd", required=True, help="AVD name")

    # --- sdk-path ---
    sub.add_parser("sdk-path", help="Show detected Android SDK path")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "sdk-path":
        path = find_sdk_root(args.sdk)
        if path:
            print(path)
            return 0
        print("SDK root not found", file=sys.stderr)
        return 1

    if args.command == "list":
        for avd in list_avds(args.sdk):
            print(avd)
        return 0

    if args.command == "boot":
        ok = boot_avd(args.avd, sdk=args.sdk, headed=args.headed,
                       no_snapshot=args.no_snapshot, wipe_data=args.wipe_data,
                       read_only=args.read_only, wait=args.wait or args.root,
                       auto_root=args.root, timeout=args.timeout,
                       extra=args.extra)
        return 0 if ok else 1

    if args.command == "status":
        results = get_status(args.sdk, args.avd)
        for r in results:
            extra = f"  PID {r['pid']}" if r["running"] else ""
            print(f"  {r['name']:30}  {'RUNNING' if r['running'] else 'STOPPED'}{extra}")
        return 0

    if args.command == "root":
        ok = grant_magisk_root(args.avd, sdk=args.sdk,
                               check_only=args.check, persist=args.persist,
                               max_attempts=args.retries)
        return 0 if ok else 1

    if args.command == "kill":
        ok = kill_avd(args.avd, force=args.force, sdk=args.sdk)
        return 0 if ok else 1

    if args.command == "shell":
        out = adb_shell(args.cmd, avd_name=args.avd, sdk=args.sdk)
        if out is not None:
            print(out, end="")
            return 0
        return 1

    if args.command == "info":
        info = device_info(args.avd, sdk=args.sdk)
        if info:
            for k, v in info.items():
                print(f"{k}: {v}")
            return 0
        return 1

    if args.command == "snapshot":
        if args.action == "list":
            for s in snapshot_list(args.avd, sdk=args.sdk):
                print(s)
            return 0
        elif args.action == "save":
            ok = snapshot_save(args.avd, args.name, sdk=args.sdk)
            return 0 if ok else 1
        elif args.action == "delete":
            ok = snapshot_delete(args.avd, args.name, sdk=args.sdk)
            return 0 if ok else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
