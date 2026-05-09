# android-cli

Android Emulator AVD CLI — manage emulators, grant root via Magisk, and run ADB commands from the terminal.

```bash
pip install android-cli
```

## Quick Start

```bash
# List available AVDs
android list

# Boot an emulator (headless by default)
android boot rooted-playstore33

# Wait for boot, then auto-grant root via Magisk
android root

# Check device info
android info

# Run ADB shell commands
android shell pm list packages

# Stop the emulator
android kill
```

## Installation

```bash
pip install android-cli
```

Or install from source:

```bash
git clone https://github.com/overtimepog/android-cli.git
cd android-cli
pip install -e .
```

### Prerequisites

- Android SDK with platform tools and a system image installed
- An AVD created (via Android Studio CLI or `avdmanager`)
- For root features: a Magisk-patched system image

## Commands

| Command | Description |
|---------|-------------|
| `android list` | List all available AVDs |
| `android boot <avd>` | Boot an AVD (headless by default) |
| `android status [avd]` | Show running emulators |
| `android root [avd]` | Auto-grant root via Magisk |
| `android kill [avd]` | Stop emulator(s) |
| `android shell <cmd>` | Run ADB shell commands |
| `android info [avd]` | Get device properties |
| `android snapshot <list\|save\|delete>` | Manage snapshots |
| `android sdk-path` | Show detected Android SDK path |

### Boot Options

```bash
# Show the emulator window
android boot <avd> --headed

# Skip snapshots (clean boot)
android boot <avd> --no-snapshot

# Wipe user data
android boot <avd> --wipe-data

# Boot read-only
android boot <avd> --read-only

# Wait for boot to complete
android boot <avd> --wait

# Boot, wait, and auto-grant root
android boot <avd> --root

# Boot with longer timeout
android boot <avd> --wait --timeout 300

# Pass extra emulator flags
android boot <avd> -X "-memory" -X "2048" -X "-cores" -X "4"
```

## How Root Grant Works

When a Magisk-patched emulator boots for the first time, `su -c` opens a dialog in the Magisk app asking for approval. Since the emulator runs headless, `android root`:

1. Triggers a `su` request
2. Sends key events (Tab → Tab → Enter) to auto-approve
3. Verifies root access was granted

## SDK Detection

The tool auto-detects the Android SDK by checking (in order):

1. `--sdk` CLI flag
2. `ANDROID_HOME` environment variable
3. `ANDROID_SDK_ROOT` environment variable
4. Common paths (`~/Library/Android/sdk`, `~/Android/Sdk`)
5. `emulator` on PATH

## Requirements

- Python 3.8+
- Android SDK (emulator must be on PATH or SDK root set)
- ADB (platform-tools)

## License

MIT
