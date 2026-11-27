# @goshikq/sdk

TypeScript and JavaScript client for the Goshikq runtime.

This package is **not on npm**. Version `1.0.1` is prepared for a later owner-approved publish. The stable runtime install remains GitHub Release `v1.0.0`.

The package is ESM (`"type": "module"`). Node.js 20 or newer can import it. CommonJS `require()` is not provided. Bun can import the same build.

## Install from this repository

```bash
cd sdk/typescript
bun install
bun run build
```

A consumer outside the repo installs the packed tarball (`npm pack` or `bun pm pack`), not the package name `@goshikq/sdk`.

## Minimal example

```javascript
import { Agent, Goal, Runtime, MockModel } from "@goshikq/sdk";

const agent = new Agent({
  name: "hello",
  model: new MockModel({ script: [{ content: "done" }] }),
});
const result = await new Runtime(agent).run(new Goal({ description: "Say hello" }));
console.log(result.status, result.verification);
```

`GOSHIKQ_RUNTIME_URL` defaults to `http://127.0.0.1:7400`. A completed run is not `VERIFIED` unless the goal predicate accepts authoritative state.

Apache-2.0. See the repository `LICENSE`.
