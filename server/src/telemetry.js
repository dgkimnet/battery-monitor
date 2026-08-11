const { diag, DiagConsoleLogger, DiagLogLevel } = require("@opentelemetry/api");
const { getNodeAutoInstrumentations } = require("@opentelemetry/auto-instrumentations-node");
const { NodeSDK } = require("@opentelemetry/sdk-node");
const { PrismaInstrumentation } = require("@prisma/instrumentation");

let sdk = null;

function telemetryEnabled() {
  if (process.env.OTEL_SDK_DISABLED === "true") {
    return false;
  }

  return Boolean(
    process.env.OTEL_EXPORTER_OTLP_ENDPOINT ||
      process.env.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT ||
      process.env.OTEL_TRACES_EXPORTER,
  );
}

function startTelemetry() {
  if (!telemetryEnabled()) {
    return null;
  }

  process.env.OTEL_TRACES_EXPORTER = process.env.OTEL_TRACES_EXPORTER || "otlp";
  process.env.OTEL_EXPORTER_OTLP_PROTOCOL = process.env.OTEL_EXPORTER_OTLP_PROTOCOL || "http/protobuf";

  if (process.env.OTEL_LOG_LEVEL) {
    const level = DiagLogLevel[process.env.OTEL_LOG_LEVEL.toUpperCase()] || DiagLogLevel.INFO;
    diag.setLogger(new DiagConsoleLogger(), level);
  }

  sdk = new NodeSDK({
    serviceName: process.env.OTEL_SERVICE_NAME || "battery-monitor",
    instrumentations: [
      getNodeAutoInstrumentations({
        "@opentelemetry/instrumentation-fs": {
          enabled: false,
        },
        "@opentelemetry/instrumentation-http": {
          ignoreIncomingRequestHook: (req) => req.url === "/healthz",
        },
      }),
      new PrismaInstrumentation(),
    ],
  });

  sdk.start();
  console.log("OpenTelemetry tracing enabled");
  return sdk;
}

async function shutdownTelemetry() {
  if (!sdk) {
    return;
  }

  await sdk.shutdown();
}

module.exports = {
  shutdownTelemetry,
  startTelemetry,
};

