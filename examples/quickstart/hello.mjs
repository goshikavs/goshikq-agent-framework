/**
 * Standalone Node.js example. ESM only. Node.js 20+.
 * Install @goshikq/sdk first. That package is not on npm yet.
 * The runtime must already be healthy at GOSHIKQ_RUNTIME_URL.
 */
import { z } from "zod";
import { Agent, Goal, MockModel, Runtime, StateSnapshot, defineTool } from "@goshikq/sdk";

const greetings = {};

const recordGreeting = defineTool({
  name: "record_greeting",
  description: "Store a greeting for name.",
  schema: z.object({ name: z.string(), message: z.string() }),
  jsonSchema: {
    type: "object",
    properties: { name: { type: "string" }, message: { type: "string" } },
    required: ["name", "message"],
    additionalProperties: false,
  },
  effect: "IDEMPOTENT_WRITE",
  risk: "low",
  idempotent: true,
  execute: async ({ name, message }) => {
    greetings[name] = message;
    return { stored: true, name };
  },
});

const agent = new Agent({
  name: "hello-agent",
  model: new MockModel({
    script: [
      { tool_calls: [["record_greeting", { name: "Ada", message: "Hello, Ada!" }]] },
      { content: "Greeted Ada." },
    ],
  }),
  instructions: "Greet the person named in the input.",
  tools: [recordGreeting],
});

const goal = new Goal({
  description: "Ada has been greeted exactly once",
  success: (state) => {
    const greeting = state.get("greetings.Ada");
    return typeof greeting === "string" && greeting.includes("Ada");
  },
  invariants: [
    (state) => {
      const stored = state.get("greetings") ?? {};
      return Object.keys(stored).length <= 1;
    },
  ],
  maxSteps: 4,
});

const runtime = new Runtime(agent, {
  stateProvider: {
    snapshot: () =>
      new StateSnapshot({
        state: { greetings: { ...greetings } },
        version: String(Object.keys(greetings).length),
        source: "greetings-memory",
      }),
  },
});

const result = await runtime.run(goal, { input: { name: "Ada" }, timeoutMs: 60_000 });
console.log(`status:        ${result.status}`);
console.log(`verification:  ${result.verificationStatus}`);
if (result.status !== "COMPLETED" || result.verificationStatus !== "VERIFIED") {
  process.exit(1);
}
