function numberOrNull(value) {
  if (value === undefined || value === null || value === "") {
    return null;
  }
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function int32OrNull(value, fieldName) {
  const parsed = numberOrNull(value);
  if (parsed === null) {
    return null;
  }
  if (!Number.isInteger(parsed) || parsed < -2147483648 || parsed > 2147483647) {
    const err = new Error(`${fieldName} must be a 32-bit integer`);
    err.status = 400;
    throw err;
  }
  return parsed;
}

function stringOrNull(value) {
  if (typeof value !== "string" || value.trim() === "") {
    return null;
  }
  return value.trim();
}

module.exports = {
  int32OrNull,
  numberOrNull,
  stringOrNull,
};
