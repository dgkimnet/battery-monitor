const express = require("express");
const { createHealthRouter } = require("./routes/health");
const { createSamplesRouter } = require("./routes/samples");
const { errorHandler } = require("./middleware/error-handler");

function createApp({ prisma, apiToken }) {
  const app = express();

  app.use(express.json({ limit: "64kb" }));
  app.use(createHealthRouter({ prisma }));
  app.use("/api/v1", createSamplesRouter({ prisma, apiToken }));
  app.use(errorHandler);

  return app;
}

module.exports = {
  createApp,
};

