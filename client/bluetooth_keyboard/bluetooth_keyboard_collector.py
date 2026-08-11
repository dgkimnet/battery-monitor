#!/usr/bin/env python3
import json
import os
import platform
import re
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path


def run_command(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""


def first_existing_path(paths):
    for path in paths:
        if Path(path).exists():
            return path
    return paths[0]


def read_text(path):
    try:
        return Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        return None


def read_int(path):
    value = read_text(path)
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def normalize_name(value):
    return re.sub(r"\s+", " ", value or "").strip()


def keyboard_name_filter():
    return os.getenv("BATTERY_MONITOR_KEYBOARD_NAME", "").strip().lower()


def name_matches(name):
    pattern = keyboard_name_filter()
    if not pattern:
        return True
    return pattern.lower() in name.lower()


def text_matches_configured_name(text):
    pattern = keyboard_name_filter()
    return bool(pattern and pattern in text.lower())


def looks_like_keyboard(text, name):
    lowered = text.lower()
    if text_matches_configured_name(lowered) or name_matches(name) and keyboard_name_filter():
        return True
    if any(token in lowered for token in ("mouse", "touchpad", "trackpad", "tablet")):
        return False
    return any(token in lowered for token in ("keyboard", "input-keyboard", "kbd"))


def parse_percent(value):
    if value is None:
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"(\d+)(?:\.\d+)?\s*%", str(value))
    if match:
        return int(match.group(1))
    match = re.search(r"\((\d+)\)", str(value))
    if match:
        return int(match.group(1))
    match = re.search(r"\b(\d{1,3})\b", str(value))
    if match:
        return int(match.group(1))
    return None


def sysfs_keyboards():
    results = []
    for supply in sorted(Path("/sys/class/power_supply").glob("*")):
        supply_type = read_text(supply / "type")
        if supply_type != "Battery":
            continue

        name = normalize_name(read_text(supply / "model_name") or read_text(supply / "manufacturer") or supply.name)
        scope = read_text(supply / "scope")
        capacity = read_int(supply / "capacity")

        text = " ".join(
            part
            for part in (
                supply.name,
                name,
                read_text(supply / "manufacturer"),
                read_text(supply / "model_name"),
            )
            if part
        ).lower()
        if capacity is None or not looks_like_keyboard(text, name) or not name_matches(name):
            continue

        results.append(
            {
                "name": name,
                "soc_percent": capacity,
                "status": read_text(supply / "status"),
                "extra": {
                    "power_supply": supply.name,
                    "scope": scope,
                    "manufacturer": read_text(supply / "manufacturer"),
                    "model_name": read_text(supply / "model_name"),
                    "serial_number": read_text(supply / "serial_number"),
                },
            }
        )

    return results


def parse_key_value_lines(output):
    values = {}
    for line in output.splitlines():
        match = re.match(r"\s*([^:]+):\s*(.+?)\s*$", line)
        if match:
            values[match.group(1).strip().lower()] = match.group(2).strip()
    return values


def upower_keyboards():
    devices = [line.strip() for line in run_command(["upower", "-e"]).splitlines() if line.strip()]
    results = []

    for device in devices:
        values = parse_key_value_lines(run_command(["upower", "-i", device]))
        name = normalize_name(values.get("model") or values.get("native-path") or Path(device).name)
        text = " ".join(
            part
            for part in (
                device,
                values.get("native-path"),
                values.get("vendor"),
                values.get("model"),
                values.get("serial"),
                values.get("icon-name"),
            )
            if part
        ).lower()
        capacity = parse_percent(values.get("percentage"))

        if capacity is None or not looks_like_keyboard(text, name) or not name_matches(name):
            continue

        results.append(
            {
                "name": name,
                "soc_percent": capacity,
                "status": values.get("state"),
                "extra": {
                    "source": "upower",
                    "upower_device": device,
                    "native_path": values.get("native-path"),
                    "vendor": values.get("vendor"),
                    "model": values.get("model"),
                    "serial": values.get("serial"),
                },
            }
        )

    return results


def bluetoothctl_keyboards():
    results = []
    for line in run_command(["bluetoothctl", "devices"]).splitlines():
        match = re.match(r"Device\s+([0-9A-Fa-f:]{17})\s+(.+)$", line.strip())
        if not match:
            continue

        address, listed_name = match.groups()
        values = parse_key_value_lines(run_command(["bluetoothctl", "info", address]))
        name = normalize_name(values.get("name") or listed_name)
        text = " ".join(
            part
            for part in (
                name,
                values.get("alias"),
                values.get("icon"),
                values.get("modalias"),
            )
            if part
        ).lower()
        capacity = parse_percent(values.get("battery percentage"))

        if capacity is None or not looks_like_keyboard(text, name) or not name_matches(name):
            continue

        results.append(
            {
                "name": name,
                "soc_percent": capacity,
                "status": "Discharging",
                "extra": {
                    "source": "bluetoothctl",
                    "bluetooth_address": address,
                    "alias": values.get("alias"),
                    "icon": values.get("icon"),
                    "modalias": values.get("modalias"),
                },
            }
        )

    return results


def linux_keyboards():
    results = []
    seen = set()
    for keyboard in sysfs_keyboards() + upower_keyboards() + bluetoothctl_keyboards():
        key = (keyboard["name"].lower(), keyboard["soc_percent"])
        if key in seen:
            continue
        seen.add(key)
        results.append(keyboard)
    return results


def parse_ioreg_value(value):
    value = value.strip()
    if value.startswith('"') and value.endswith('"'):
        return value[1:-1]
    if value in ("Yes", "No"):
        return value == "Yes"
    try:
        return int(value)
    except ValueError:
        return value


def parse_ioreg_blocks(output):
    blocks = []
    current = []
    for line in output.splitlines():
        if re.match(r"^\s*\+-o ", line):
            if current:
                blocks.append(current)
            current = [line]
        elif current:
            current.append(line)
    if current:
        blocks.append(current)
    return blocks


def block_values(block):
    values = {}
    header = block[0].strip()
    match = re.search(r"\+-o\s+(.+?)(?:\s+<|$)", header)
    if match:
        values["IORegistryName"] = normalize_name(match.group(1))
    for line in block[1:]:
        match = re.search(r'"([^"]+)"\s+=\s+(.+)$', line.strip())
        if match:
            values[match.group(1)] = parse_ioreg_value(match.group(2))
    return values


def macos_keyboards():
    ioreg = first_existing_path(("/usr/sbin/ioreg", "/usr/bin/ioreg", "ioreg"))
    output = run_command([ioreg, "-r", "-c", "AppleDeviceManagementHIDEventService"])
    if not output:
        output = run_command([ioreg, "-r", "-c", "IOBluetoothHIDDriver"])

    results = []
    for block in parse_ioreg_blocks(output):
        values = block_values(block)
        name = normalize_name(
            values.get("Product")
            or values.get("ProductName")
            or values.get("DeviceAddress")
            or values.get("IORegistryName")
            or "Bluetooth Keyboard"
        )
        text = " ".join(str(values.get(key, "")) for key in ("IORegistryName", "Product", "ProductName", "Transport")).lower()
        capacity = values.get("BatteryPercent") or values.get("BatteryPercentage") or values.get("BatteryLevel")

        if not isinstance(capacity, int):
            continue
        if "keyboard" not in text and not name_matches(name):
            continue
        if not name_matches(name):
            continue

        results.append(
            {
                "name": name,
                "soc_percent": capacity,
                "status": "Discharging",
                "extra": {
                    "transport": values.get("Transport"),
                    "product": values.get("Product"),
                    "product_name": values.get("ProductName"),
                    "device_address": values.get("DeviceAddress"),
                    "registry_name": values.get("IORegistryName"),
                },
            }
        )

    return results


def collect_keyboards():
    if sys.platform.startswith("linux"):
        return linux_keyboards()
    if sys.platform == "darwin":
        return macos_keyboards()
    return []


def sample_for_keyboard(keyboard):
    keyboard_slug = re.sub(r"[^a-zA-Z0-9_-]+", "-", keyboard["name"]).strip("-").lower()
    host = socket.gethostname()
    device_id = os.getenv("BATTERY_MONITOR_KEYBOARD_DEVICE_ID") or f"{host}-keyboard-{keyboard_slug}"
    return {
        "device_id": device_id,
        "hostname": host,
        "os_name": platform.platform(),
        "battery_name": keyboard["name"],
        "status": keyboard.get("status"),
        "source": "bluetooth_keyboard_collector.py",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "soc_percent": keyboard["soc_percent"],
        "extra": {
            "device_type": "bluetooth_keyboard",
            **{key: value for key, value in keyboard.get("extra", {}).items() if value is not None},
        },
    }


def post_sample(sample):
    api_url = os.environ["BATTERY_MONITOR_API_URL"].rstrip("/")
    token = os.getenv("BATTERY_MONITOR_API_TOKEN", "")
    data = json.dumps(sample).encode("utf-8")
    request = urllib.request.Request(
        f"{api_url}/api/v1/samples",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    if token:
        request.add_header("Authorization", f"Bearer {token}")

    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8")


def main():
    if "BATTERY_MONITOR_API_URL" not in os.environ:
        print("BATTERY_MONITOR_API_URL is required", file=sys.stderr)
        return 2

    keyboards = collect_keyboards()
    if not keyboards:
        print("no supported bluetooth keyboard battery metrics found", file=sys.stderr)
        return 1

    samples = [sample_for_keyboard(keyboard) for keyboard in keyboards]
    if os.getenv("BATTERY_MONITOR_DRY_RUN") == "1":
        print(json.dumps(samples, indent=2, sort_keys=True))
        return 0

    for sample in samples:
        for attempt in range(3):
            try:
                print(post_sample(sample))
                break
            except urllib.error.URLError as err:
                if attempt == 2:
                    print(f"failed to post sample for {sample['battery_name']}: {err}", file=sys.stderr)
                    return 1
                time.sleep(2**attempt)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
