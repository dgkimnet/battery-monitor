const express = require("express");
const { createRequireToken } = require("../middleware/auth");
const { normalizeSample } = require("../utils/sample-normalizer");
const { serializeValue } = require("../utils/serialization");

function createSamplesRouter({ prisma, apiToken }) {
  const router = express.Router();
  const requireToken = createRequireToken(apiToken);

  router.post("/samples", requireToken, async (req, res, next) => {
    try {
      const sample = normalizeSample(req.body || {});
      if (Number.isNaN(sample.collectedAt.getTime())) {
        return res.status(400).json({ error: "collected_at must be an ISO timestamp" });
      }

      const result = await prisma.batterySample.create({
        data: sample,
        select: {
          id: true,
          collectedAt: true,
        },
      });

      return res.status(201).json(serializeValue(result));
    } catch (err) {
      return next(err);
    }
  });

  router.get("/devices/:deviceId/samples", requireToken, async (req, res, next) => {
    try {
      const requestedLimit = Number(req.query.limit || 100);
      const limit = Number.isFinite(requestedLimit) ? Math.min(requestedLimit, 500) : 100;
      const samples = await prisma.batterySample.findMany({
        where: {
          deviceId: req.params.deviceId,
        },
        orderBy: {
          collectedAt: "desc",
        },
        take: limit,
      });

      return res.json({ samples: samples.map(serializeValue) });
    } catch (err) {
      return next(err);
    }
  });

  return router;
}

module.exports = {
  createSamplesRouter,
};

