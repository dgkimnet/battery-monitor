#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
ENV_FILE=${BATTERY_MONITOR_ENV_FILE:-$SCRIPT_DIR/.env}

if [ -f "$ENV_FILE" ]; then
  set -a
  . "$ENV_FILE"
  set +a
fi

: "${BATTERY_MONITOR_API_URL:?BATTERY_MONITOR_API_URL is required}"

DEVICE_ID=${BATTERY_MONITOR_DEVICE_ID:-$(hostname)}
TOKEN=${BATTERY_MONITOR_API_TOKEN:-}
PYTHON_BIN=${PYTHON_BIN:-python3}
INTERVAL=${BATTERY_MONITOR_CRON_INTERVAL:-*/5 * * * *}

quote_cron_value() {
  printf "'%s'" "$(printf '%s' "$1" | sed "s/%/\\\\%/g; s/'/'\\\\''/g")"
}

CRON_LINE="$INTERVAL BATTERY_MONITOR_API_URL=$(quote_cron_value "$BATTERY_MONITOR_API_URL") BATTERY_MONITOR_DEVICE_ID=$(quote_cron_value "$DEVICE_ID") BATTERY_MONITOR_API_TOKEN=$(quote_cron_value "$TOKEN") $(quote_cron_value "$PYTHON_BIN") $(quote_cron_value "$SCRIPT_DIR/battery_collector.py") >> /tmp/battery-monitor.log 2>&1"

(crontab -l 2>/dev/null | grep -v "$SCRIPT_DIR/battery_collector.py" || true; printf '%s\n' "$CRON_LINE") | crontab -
printf 'installed cron entry for %s\n' "$SCRIPT_DIR/battery_collector.py"
