const { int32OrNull, numberOrNull, stringOrNull } = require("./coercion");

function normalizeSample(body) {
  const deviceId = stringOrNull(body.device_id);
  if (!deviceId) {
    const err = new Error("device_id is required");
    err.status = 400;
    throw err;
  }

  return {
    deviceId,
    hostname: stringOrNull(body.hostname),
    osName: stringOrNull(body.os_name),
    batteryName: stringOrNull(body.battery_name),
    status: stringOrNull(body.status),
    source: stringOrNull(body.source) || "battery_collector",
    collectedAt: body.collected_at ? new Date(body.collected_at) : new Date(),
    socPercent: numberOrNull(body.soc_percent),
    designedCapacityMah: int32OrNull(body.designed_capacity_mah, "designed_capacity_mah"),
    currentCapacityMah: int32OrNull(body.current_capacity_mah, "current_capacity_mah"),
    fullChargeCapacityMah: int32OrNull(body.full_charge_capacity_mah, "full_charge_capacity_mah"),
    currentMa: int32OrNull(body.current_ma, "current_ma"),
    voltageMv: int32OrNull(body.voltage_mv, "voltage_mv"),
    powerMw: int32OrNull(body.power_mw, "power_mw"),
    cycleCount: int32OrNull(body.cycle_count, "cycle_count"),
    temperatureC: numberOrNull(body.temperature_c),
    healthPercent: numberOrNull(body.health_percent),
    extra: body.extra && typeof body.extra === "object" ? body.extra : {},
  };
}

module.exports = {
  normalizeSample,
};
