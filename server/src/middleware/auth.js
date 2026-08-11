function createRequireToken(apiToken) {
  return function requireToken(req, res, next) {
    if (!apiToken) {
      return next();
    }

    const auth = req.get("authorization") || "";
    const expected = `Bearer ${apiToken}`;
    if (auth !== expected) {
      return res.status(401).json({ error: "unauthorized" });
    }

    return next();
  };
}

module.exports = {
  createRequireToken,
};

