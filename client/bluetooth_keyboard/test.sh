#!/usr/bin/env sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

set -a
. "$SCRIPT_DIR/../.env"
set +a

python3 "$SCRIPT_DIR/bluetooth_keyboard_collector.py"
