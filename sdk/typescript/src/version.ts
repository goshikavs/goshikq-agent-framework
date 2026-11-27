export const VERSION = "1.0.1";
export const PROTOCOL_VERSION = "1.0";
export const SOURCE_FRAMEWORK = "goshikq-typescript";
export const WORKER_CAPABILITIES = [
  "model.generate",
  "tool.execute",
  "state.snapshot",
  "goal.evaluate",
  "action.verify",
] as const;
