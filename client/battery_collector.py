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


def run_command(args):
    try:
        return subprocess.check_output(args, text=True, stderr=subprocess.DEVNULL)
    except (OSError, subprocess.CalledProcessError):
        return ""


def linux_sample():
    power_supply = Path("/sys/class/power_supply")
    batteries = sorted(path for path in power_supply.glob("BAT*") if path.is_dir())
    if not batteries:
        return None

    battery = batteries[0]
    energy_now = read_int(battery / "energy_now")
    charge_now = read_int(battery / "charge_now")
    energy_full = read_int(battery / "energy_full")
    charge_full = read_int(battery / "charge_full")
    energy_design = read_int(battery / "energy_full_design")
    charge_design = read_int(battery / "charge_full_design")
    power_now = read_int(battery / "power_now")
    current_now = read_int(battery / "current_now")
    voltage_now = read_int(battery / "voltage_now")
    capacity = read_int(battery / "capacity")
    temp_raw = read_int(battery / "temp")

    extra = {}
    for key in ("manufacturer", "model_name", "serial_number", "technology"):
        value = read_text(battery / key)
        if value:
            extra[key] = value

    sample = {
        "battery_name": battery.name,
        "status": read_text(battery / "status"),
        "soc_percent": capacity,
        "designed_capacity_mah": micro_to_milli(charge_design),
        "current_capacity_mah": micro_to_milli(charge_now),
        "full_charge_capacity_mah": micro_to_milli(charge_full),
        "current_ma": signed_current_ma(current_now, read_text(battery / "status")),
        "voltage_mv": micro_to_milli(voltage_now),
        "power_mw": micro_to_milli(power_now),
        "cycle_count": read_int(battery / "cycle_count"),
        "temperature_c": temp_raw / 10 if temp_raw is not None else None,
        "extra": extra,
    }

    if sample["current_capacity_mah"] is None and energy_now and voltage_now:
        sample["current_capacity_mah"] = energy_to_mah(energy_now, voltage_now)
    if sample["full_charge_capacity_mah"] is None and energy_full and voltage_now:
        sample["full_charge_capacity_mah"] = energy_to_mah(energy_full, voltage_now)
    if sample["designed_capacity_mah"] is None and energy_design and voltage_now:
        sample["designed_capacity_mah"] = energy_to_mah(energy_design, voltage_now)

    add_health(sample)
    return sample


def macos_sample():
    output = run_command(["ioreg", "-rn", "AppleSmartBattery"])
    if not output:
        return None

    values = {}
    for line in output.splitlines():
        match = re.search(r'"([^"]+)"\s+=\s+(.+)$', line.strip())
        if match:
            values[match.group(1)] = parse_ioreg_value(match.group(2))

    amperage = signed_int64(as_int(values.get("Amperage")))
    voltage = as_int(values.get("Voltage"))
    display_current_capacity = as_int(values.get("CurrentCapacity"))
    display_max_capacity = as_int(values.get("MaxCapacity"))
    current_capacity = as_int(values.get("AppleRawCurrentCapacity"))
    max_capacity = as_int(values.get("AppleRawMaxCapacity"))
    design_capacity = as_int(values.get("DesignCapacity"))
    cycle_count = as_int(values.get("CycleCount"))
    temperature = as_int(values.get("Temperature"))

    if current_capacity is None and looks_like_mah(display_current_capacity, design_capacity):
        current_capacity = display_current_capacity
    if max_capacity is None and looks_like_mah(display_max_capacity, design_capacity):
        max_capacity = display_max_capacity

    sample = {
        "battery_name": "AppleSmartBattery",
        "status": macos_status(values),
        "soc_percent": macos_soc_percent(values, display_current_capacity, display_max_capacity),
        "designed_capacity_mah": design_capacity,
        "current_capacity_mah": current_capacity,
        "full_charge_capacity_mah": max_capacity,
        "current_ma": amperage,
        "voltage_mv": voltage,
        "power_mw": abs(amperage * voltage) // 1000 if amperage is not None and voltage is not None else None,
        "cycle_count": cycle_count,
        "temperature_c": temperature / 100 if temperature is not None else None,
        "extra": {
            key: values[key]
            for key in (
                "Manufacturer",
                "DeviceName",
                "Serial",
                "FirmwareSerialNumber",
                "CurrentCapacity",
                "MaxCapacity",
                "AppleRawCurrentCapacity",
                "AppleRawMaxCapacity",
            )
            if key in values
        },
    }
    add_health(sample)
    return sample


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


def macos_status(values):
    if values.get("ExternalConnected") and values.get("IsCharging"):
        return "Charging"
    if values.get("ExternalConnected"):
        return "Not Charging"
    return "Discharging"


def signed_int64(value):
    if value is None:
        return None
    if value >= 2**63:
        return value - 2**64
    return value


def looks_like_mah(value, design_capacity):
    if value is None:
        return False
    if design_capacity is None:
        return value > 100
    return value > 100 and value <= design_capacity * 2


def macos_soc_percent(values, current_capacity, max_capacity):
    legacy_capacity = as_int(values.get("LegacyBatteryInfo", {}).get("Capacity")) if isinstance(values.get("LegacyBatteryInfo"), dict) else None
    if legacy_capacity is not None:
        return legacy_capacity
    return percent(current_capacity, max_capacity)


def micro_to_milli(value):
    return value // 1000 if value is not None else None


def signed_current_ma(current_microamps, status):
    current_ma = micro_to_milli(current_microamps)
    if current_ma is None:
        return None
    if status and status.lower() == "discharging":
        return -abs(current_ma)
    return current_ma


def energy_to_mah(energy_microwh, voltage_microv):
    if not energy_microwh or not voltage_microv:
        return None
    return round((energy_microwh / voltage_microv) * 1000)


def percent(value, total):
    if value is None or not total:
        return None
    return round((value / total) * 100, 2)


def as_int(value):
    return value if isinstance(value, int) else None


def add_health(sample):
    health = percent(sample.get("full_charge_capacity_mah"), sample.get("designed_capacity_mah"))
    if health is not None:
        sample["health_percent"] = health


def collect_sample():
    if sys.platform.startswith("linux"):
        sample = linux_sample()
    elif sys.platform == "darwin":
        sample = macos_sample()
    else:
        sample = None

    if not sample:
        raise RuntimeError(f"no supported battery metrics found for {platform.system()}")

    sample.update(
        {
            "device_id": os.getenv("BATTERY_MONITOR_DEVICE_ID") or socket.gethostname(),
            "hostname": socket.gethostname(),
            "os_name": platform.platform(),
            "source": "battery_collector.py",
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
    )
    return {key: value for key, value in sample.items() if value is not None}


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

    sample = collect_sample()
    if os.getenv("BATTERY_MONITOR_DRY_RUN") == "1":
        print(json.dumps(sample, indent=2, sort_keys=True))
        return 0

    for attempt in range(3):
        try:
            print(post_sample(sample))
            return 0
        except urllib.error.URLError as err:
            if attempt == 2:
                print(f"failed to post sample: {err}", file=sys.stderr)
                return 1
            time.sleep(2**attempt)

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
