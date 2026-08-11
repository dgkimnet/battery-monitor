require("dotenv").config();

const { shutdownTelemetry, startTelemetry } = require("./telemetry");

startTelemetry();

const { prisma, close } = require("./db");
const { createApp } = require("./app");

const port = Number(process.env.PORT || 3000);
const apiToken = process.env.BATTERY_MONITOR_API_TOKEN || "";
const app = createApp({ prisma, apiToken });

const server = app.listen(port, () => {
  console.log(`battery monitor api listening on :${port}`);
});

async function shutdown() {
  server.close(async () => {
    await close();
    await shutdownTelemetry();
    process.exit(0);
  });
}

process.on("SIGTERM", shutdown);
process.on("SIGINT", shutdown);
