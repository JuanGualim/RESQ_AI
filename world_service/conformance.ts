// Runs the official World Model conformance suite against the vendored implementation
// that server.ts uses. Cross-platform replacement for WORLD_MODEL_IMPL=... npx tsx runner.ts.
import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
process.env.WORLD_MODEL_IMPL = path.join(here, "vendor", "world-model", "src", "index.ts").replaceAll("\\", "/");
await import("./vendor/world-model/conformance/runner.ts");
