"""Storage backends for the World Model client.

`HttpWorld` talks to world_service/ (the Meterless World Model reference, the
engine used in the demo). `MemoryWorld` mirrors the same primitives in-process
for unit tests and machines without Node; it is a development fallback only.
"""
from __future__ import annotations

import json
from typing import Protocol

import requests


class WorldError(RuntimeError):
    """The World Model service failed or is unreachable."""


class WorldBackend(Protocol):
    name: str

    def upsert_entities(self, entities: list[dict]) -> dict: ...
    def assert_fact(self, fact: dict) -> None: ...
    def entities(self) -> list[dict]: ...
    def facts(self) -> list[dict]: ...
    def audit(self) -> list[dict]: ...
    def reset(self) -> None: ...


class HttpWorld:
    name = "meterless-world-model"

    def __init__(self, url: str, timeout_s: float = 10.0):
        self.url = url.rstrip("/")
        self.timeout_s = timeout_s

    def _call(self, method: str, path: str, body: dict | None = None):
        try:
            response = requests.request(method, self.url + path, json=body, timeout=self.timeout_s)
        except requests.RequestException as error:
            raise WorldError(f"World Model service unreachable at {self.url}: {type(error).__name__}. "
                             "Start it with `npm start` in world_service/") from error
        if response.status_code != 200:
            raise WorldError(f"World Model {method} {path} -> HTTP {response.status_code}: {response.text[:200]}")
        return response.json()

    def health(self) -> dict:
        return self._call("GET", "/health")

    def upsert_entities(self, entities: list[dict]) -> dict:
        return self._call("POST", "/entities", {"entities": entities})

    def assert_fact(self, fact: dict) -> None:
        self._call("POST", "/facts", fact)

    def entities(self) -> list[dict]:
        return self._call("GET", "/entities")

    def facts(self) -> list[dict]:
        return self._call("GET", "/facts")

    def audit(self) -> list[dict]:
        return self._call("GET", "/audit")

    def reset(self) -> None:
        self._call("POST", "/reset")


class MemoryWorld:
    name = "in-memory-fallback"

    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self._entities: dict[tuple[str, str], dict] = {}
        self._facts: list[dict] = []
        self._audit: list[dict] = []
        self._seq = 0

    def _log(self, kind: str, actor: str, summary: str, at: str) -> None:
        self._audit.append({"seq": len(self._audit) + 1, "at": at, "kind": kind, "actor": actor, "summary": summary})

    def upsert_entities(self, entities: list[dict]) -> dict:
        written = 0
        for item in entities:
            key = (item["type"], item["id"])
            current = self._entities.get(key)
            if current and all(current["attrs"].get(k) == v for k, v in item["attrs"].items()):
                continue
            merged = {**(current["attrs"] if current else {}), **item["attrs"]}
            self._entities[key] = {"type": item["type"], "id": item["id"], "attrs": merged, "updatedAt": item["at"]}
            self._seq += 1
            written += 1
            self._log("upsertEntity", item.get("by", "loader"), f"{item['type']}:resq:{item['id']}", item["at"])
        return {"written": written, "skipped": len(entities) - written}

    def assert_fact(self, fact: dict) -> None:
        if not fact.get("source", {}).get("kind") or not fact.get("source", {}).get("at"):
            raise WorldError("every write carries provenance (kind + at)")
        signature = json.dumps([fact["about_type"], fact["about_id"], fact["predicate"], fact["value"],
                                fact["source"]["at"], fact["source"]["kind"]], sort_keys=True, default=str)
        if any(f["_signature"] == signature for f in self._facts):
            return  # content-addressed no-op, like the reference implementation
        self._seq += 1
        self._facts.append({
            "seq": self._seq, "type": fact["about_type"], "id": fact["about_id"],
            "predicate": fact["predicate"], "value": fact["value"], "confidence": fact.get("confidence", 0.5),
            "source": fact["source"], "at": fact["source"]["at"], "_signature": signature,
        })
        self._log("assertFact", fact["source"].get("by") or fact["source"]["kind"],
                  f"{fact['about_type']}:resq:{fact['about_id']}.{fact['predicate']}", fact["source"]["at"])

    def entities(self) -> list[dict]:
        return [dict(e) for e in self._entities.values()]

    def facts(self) -> list[dict]:
        return [{k: v for k, v in f.items() if k != "_signature"} for f in self._facts]

    def audit(self) -> list[dict]:
        return [dict(entry) for entry in self._audit]
