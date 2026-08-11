function serializeValue(value) {
  return JSON.parse(
    JSON.stringify(value, (_key, nestedValue) => {
      if (typeof nestedValue === "bigint") {
        return nestedValue.toString();
      }
      return nestedValue;
    }),
  );
}

module.exports = {
  serializeValue,
};

