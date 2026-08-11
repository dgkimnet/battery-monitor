const express = require("express");

function createHealthRouter({ prisma }) {
  const router = express.Router();

  router.get("/healthz", async (_req, res) => {
    await prisma.$queryRaw`select 1`;
    res.json({ ok: true });
  });

  return router;
}

module.exports = {
  createHealthRouter,
};

