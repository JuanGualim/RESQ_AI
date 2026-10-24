// RESQ AI World Model service: a thin HTTP layer over the Meterless World Model
// reference implementation (vendor/world-model, Apache-2.0). It is the shared,
// event-sourced state of every RESQ agent. Python talks to it from resq/world/.
//
//   npm start                          # http://127.0.0.1:4380
//   WORLD_PORT=4400 npm start          # another port
//
// Every write carries provenance (kind + by + at) as the World Model requires.
// Scenario entities use external keys "type:resq:id" (e.g. road_segment:resq:T7);
// agent conclusions are facts about them.

import http from "node:http";
import path from "node:path";
import fs from "node:fs";
import { fileURLToPath } from "node:url";
import { WorldModel, canonicalJson } from "./vendor/world-model/src/index.ts";

const here = path.dirname(fileURLToPath(import.meta.url));
const PORT = Number(process.env.WORLD_PORT ?? 4380);
const HOST = process.env.WORLD_HOST ?? "127.0.0.1";
const NAMESPACE = process.env.WORLD_NAMESPACE ?? "resq";
const SYSTEM = "resq";

const newWorld = () => new WorldModel({ storage: "local", namespace: NAMESPACE, directory: here, conflictPolicy: "most-recent-wins" });
let world = newWorld();

type EntityInput = { type: string; id: string; attrs: Record<string, unknown>; at: string; by?: string };
type FactInput = {
  about_type: string; about_id: string; predicate: string; value: unknown; confidence?: number;
  source: { kind: string; by?: string; at: string; runId?: string };
};

const key = (type: string, id: string) => `${type}:${SYSTEM}:${id}`;
const unkey = (fullId: string) => {
  const [type, , ...rest] = fullId.split(":");
  return { type, id: rest.join(":") };
};

async function upsertEntities(items: EntityInput[]) {
  let written = 0;
  for (const item of items) {
    const existing = world.view("graph").entity(key(item.type, item.id));
    // Same content already stored: skip, so re-seeding every run adds no events.
    if (existing && canonicalJson(pick(existing.attrs, Object.keys(item.attrs))) === canonicalJson(item.attrs)) continue;
    await world.upsertEntity({
      type: item.type,
      externalKey: { system: SYSTEM, id: item.id },
      name: typeof item.attrs.name === "string" ? item.attrs.name : undefined,
      attrs: item.attrs,
      source: { kind: "pipeline", by: item.by ?? "loader", at: item.at },
    });
    written++;
  }
  return { written, skipped: items.length - written };
}

async function assertFact(input: FactInput) {
  const fact = await world.assertFact({
    about: key(input.about_type, input.about_id),
    predicate: input.predicate,
    value: input.value,
    confidence: input.confidence,
    source: input.source,
  });
  return { id: fact.id };
}

function entities() {
  return world.view("graph").query({}).map((e) => ({ ...unkey(e.id), attrs: e.attrs, updatedAt: e.updatedAt }));
}

function facts() {
  // Facts in append order. Picking the current value per predicate happens in Python
  // (most recent observation wins, ties broken by seq) so it survives restarts.
  return world.events()
    .filter((e) => e.kind === "assertFact")
    .map((e) => {
      const f = e.payload as any;
      return { seq: e.seq, ...unkey(f.about), predicate: f.predicate, value: f.value, confidence: f.confidence, source: f.source, at: f.assertedAt };
    });
}

function pick(obj: Record<string, unknown>, keys: string[]) {
  return Object.fromEntries(keys.filter((k) => k in obj).map((k) => [k, obj[k]]));
}

function reset() {
  const file = path.join(here, ".world", `${NAMESPACE}.json`);
  if (fs.existsSync(file)) fs.rmSync(file);
  world = newWorld();
}

async function readBody(req: http.IncomingMessage): Promise<any> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  const text = Buffer.concat(chunks).toString("utf-8");
  return text ? JSON.parse(text) : {};
}

function send(res: http.ServerResponse, status: number, body: unknown) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url ?? "/", `http://${HOST}`);
  const route = `${req.method} ${url.pathname}`;
  try {
    if (route === "GET /health") return send(res, 200, { ok: true, engine: "meterless-world-model-reference", namespace: NAMESPACE, events: world.events().length });
    if (route === "GET /entities") return send(res, 200, entities());
    if (route === "GET /facts") return send(res, 200, facts());
    if (route === "GET /audit") return send(res, 200, world.audit());
    if (route === "POST /entities") return send(res, 200, await upsertEntities((await readBody(req)).entities ?? []));
    if (route === "POST /facts") return send(res, 200, await assertFact(await readBody(req)));
    if (route === "POST /reset") { reset(); return send(res, 200, { ok: true }); }
    return send(res, 404, { error: `no route ${route}` });
  } catch (err) {
    return send(res, 400, { error: (err as Error).message });
  }
});

server.listen(PORT, HOST, () => {
  console.log(`World Model service (Meterless reference) on http://${HOST}:${PORT} namespace=${NAMESPACE} events=${world.events().length}`);
});
