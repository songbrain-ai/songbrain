// Offline unit tests for the client, with a fake fetch.
import { test } from "node:test";
import assert from "node:assert/strict";
import { createRequire } from "node:module";
import { mkdtempSync, writeFileSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  Songbrain,
  SongbrainError,
  AuthenticationError,
  InsufficientCredits,
  NotFound,
  RateLimited,
  AnalysisFailed,
  WaitTimeout,
  VERSION,
} from "../dist/index.js";

const json = (status, body, headers = {}) =>
  new Response(body === undefined ? "" : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json", ...headers },
  });

function client(responses, opts = {}) {
  const calls = [];
  const sleeps = [];
  const fetch = async (url, init) => {
    let upload;
    if (init.body instanceof FormData) {
      const f = init.body.get("file");
      upload = { name: f?.name, bytes: f ? Buffer.from(await f.arrayBuffer()) : undefined, fields: {} };
      for (const [k, v] of init.body.entries()) if (k !== "file") upload.fields[k] = v;
    }
    calls.push({ url: String(url), method: init.method, headers: init.headers, body: init.body, upload });
    const next = responses.shift();
    if (next instanceof Error) throw next;
    return next;
  };
  const sb = new Songbrain({ apiKey: "sb_live_test", fetch, ...opts });
  sb._sleep = async (ms) => void sleeps.push(ms);
  return { sb, calls, sleeps };
}

test("version matches package.json", () => {
  const pkg = JSON.parse(readFileSync(new URL("../package.json", import.meta.url)));
  assert.equal(VERSION, pkg.version);
});

test("CJS build exports the same API", () => {
  const require = createRequire(import.meta.url);
  const cjs = require("../dist/index.cjs");
  for (const name of ["Songbrain", "verifyWebhook", "SongbrainError", "RateLimited", "InsufficientCredits"]) {
    assert.equal(typeof cjs[name], "function", name);
  }
});

test("reads SONGBRAIN_API_KEY from the environment", () => {
  const before = process.env.SONGBRAIN_API_KEY;
  process.env.SONGBRAIN_API_KEY = "sb_live_env";
  try {
    assert.equal(new Songbrain().apiKey, "sb_live_env");
    assert.equal(new Songbrain({ apiKey: "explicit" }).apiKey, "explicit");
    assert.equal(new Songbrain({ apiKey: "" }).apiKey, undefined);
  } finally {
    if (before === undefined) delete process.env.SONGBRAIN_API_KEY;
    else process.env.SONGBRAIN_API_KEY = before;
  }
});

test("auth header, URL and query", async () => {
  const { sb, calls } = client([json(200, { id: "x", status: "done" })]);
  await sb.getSong("x", { view: "summary", include: ["song_dna", "shot_plan"] });
  const u = new URL(calls[0].url);
  assert.equal(u.origin + u.pathname, "https://api.songbrain.ai/v1/songs/x");
  assert.equal(u.searchParams.get("view"), "summary");
  assert.equal(u.searchParams.get("include"), "song_dna,shot_plan");
  assert.equal(calls[0].headers.Authorization, "Bearer sb_live_test");
});

test("no key, no Authorization header", async () => {
  const { sb, calls } = client([json(200, { object: "list", data: [] })], { apiKey: "" });
  await sb.examples();
  assert.equal(calls[0].headers.Authorization, undefined);
});

for (const [status, cls] of [
  [401, AuthenticationError],
  [402, InsufficientCredits],
  [404, NotFound],
  [400, SongbrainError],
  [409, SongbrainError],
]) {
  test(`HTTP ${status} maps to ${cls.name}`, async () => {
    const { sb } = client([json(status, { error: { code: "some_code", message: "Some message" } })]);
    await assert.rejects(sb.account(), (e) => {
      assert.ok(e instanceof cls);
      assert.ok(e instanceof SongbrainError);
      assert.equal(e.status, status);
      assert.equal(e.code, "some_code");
      assert.equal(e.message, "Some message");
      return true;
    });
  });
}

test("429 is retried after Retry-After", async () => {
  const limited = json(429, { error: { code: "rate_limited", message: "x" } }, { "Retry-After": "2" });
  const { sb, sleeps } = client([limited, json(200, { credits: 5 })]);
  assert.deepEqual(await sb.account(), { credits: 5 });
  assert.deepEqual(sleeps, [2000]);
});

test("429 gives up after 3 retries with retryAfter set", async () => {
  const r = () => json(429, { error: { code: "rate_limited", message: "x" } }, { "Retry-After": "1" });
  const { sb, calls } = client([r(), r(), r(), r()]);
  await assert.rejects(sb.account(), (e) => e instanceof RateLimited && e.retryAfter === 1);
  assert.equal(calls.length, 4);
});

test("a long Retry-After is not slept", async () => {
  const r = json(429, { error: { code: "daily_cap", message: "x" } }, { "Retry-After": "3600" });
  const { sb, sleeps } = client([r]);
  await assert.rejects(sb.account(), (e) => e instanceof RateLimited && e.code === "daily_cap");
  assert.deepEqual(sleeps, []);
});

test("5xx is retried for GET and for song creation, not for other POSTs", async () => {
  let c = client([json(500, { error: { code: "x", message: "y" } }), json(200, { ok: true })]);
  assert.deepEqual(await c.sb.pricing(), { ok: true });
  // POST /songs carries an Idempotency-Key, so a 500 is safe to retry.
  c = client([json(500, { error: { code: "x", message: "y" } }), json(202, { id: "s1", status: "processing" })]);
  assert.equal((await c.sb.analyze({ audioUrl: "https://example.com/a.mp3", wait: false })).id, "s1");
  assert.equal(c.calls.length, 2);
  // Other POSTs have no key and are not retried.
  c = client([json(500, { error: { code: "x", message: "y" } })]);
  await assert.rejects(c.sb.testWebhook("https://example.com/hook"), SongbrainError);
  assert.equal(c.calls.length, 1);
});

test("network errors on GET are retried", async () => {
  const { sb } = client([new TypeError("fetch failed"), json(200, { ok: 1 })]);
  assert.deepEqual(await sb.pricing(), { ok: 1 });
});

test("analyze with audioUrl and wait: false", async () => {
  const created = { object: "song", id: "s1", status: "processing", eta_sec: 75, billing: { type: "free", credits: 0 } };
  const { sb, calls } = client([json(202, created)]);
  const out = await sb.analyze({ audioUrl: "https://example.com/a.mp3", title: "T", externalRef: "r1", wait: false });
  assert.equal(out.id, "s1");
  assert.equal(calls[0].method, "POST");
  assert.deepEqual(JSON.parse(calls[0].body), { audio_url: "https://example.com/a.mp3", title: "T", external_ref: "r1" });
});

test("analyze uploads a file path and waits", async () => {
  const dir = mkdtempSync(join(tmpdir(), "sb-"));
  const path = join(dir, "my song.mp3");
  writeFileSync(path, Buffer.concat([Buffer.from("ID3"), Buffer.alloc(64)]));
  const { sb, calls } = client([
    json(202, { id: "s2", status: "processing" }),
    json(200, { id: "s2", status: "processing", progress: 0.5 }),
    json(200, { id: "s2", status: "done", shot_plan: { status: "ready" } }),
  ]);
  const doc = await sb.analyze({ file: path, artist: "A", pollIntervalMs: 500 });
  assert.equal(doc.status, "done");
  assert.equal(calls[0].upload.name, "my song.mp3");
  assert.deepEqual(calls[0].upload.fields, { artist: "A" });
});

test("a retried upload sends the whole file again, bytes get a sniffed name", async () => {
  const wav = Buffer.concat([Buffer.from("RIFF\0\0\0\0WAVE"), Buffer.alloc(32, 1)]);
  const busy = json(429, { error: { code: "too_many_in_flight", message: "x" } }, { "Retry-After": "0" });
  const { sb, calls } = client([busy, json(202, { id: "s3", status: "processing" })]);
  await sb.analyze({ file: wav, wait: false });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].upload.name, "song.wav");
  assert.deepEqual(calls[0].upload.bytes, calls[1].upload.bytes);
  assert.deepEqual(calls[1].upload.bytes, wav);
});

test("unknown bytes need a filename; exactly one source", async () => {
  const { sb } = client([]);
  await assert.rejects(sb.analyze({ file: Buffer.from("not audio"), wait: false }), TypeError);
  await assert.rejects(sb.analyze({}), TypeError);
  await assert.rejects(sb.analyze({ file: Buffer.from("x"), audioUrl: "https://x" }), TypeError);
});

test("waitFor throws AnalysisFailed and WaitTimeout", async () => {
  let c = client([json(200, { id: "s4", status: "failed", error: { code: "decode_failed", message: "bad" } })]);
  await assert.rejects(c.sb.waitFor("s4"), (e) => e instanceof AnalysisFailed && e.songId === "s4" && e.code === "decode_failed");
  c = client([json(200, { id: "s5", status: "processing" })]);
  await assert.rejects(c.sb.waitFor("s5", { timeoutMs: 0 }), (e) => e instanceof WaitTimeout && e.songId === "s5");
});

test("ids are URL-encoded", async () => {
  const { sb, calls } = client([json(200, {})]);
  await sb.exampleShotPlan("a/b");
  assert.ok(calls[0].url.endsWith("/examples/a%2Fb/shot-plan"));
});

// ── idempotency ─────────────────────────────────────────────────────────────

const UUID4 = /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;

test("song creation sends a UUID Idempotency-Key, reused across retries", async () => {
  const { sb, calls } = client([
    new TypeError("fetch failed"),
    json(502, { error: { code: "bad_gateway", message: "x" } }),
    json(202, { id: "s1", status: "processing" }),
  ]);
  await sb.analyze({ audioUrl: "https://example.com/a.mp3", wait: false });
  assert.equal(calls.length, 3);
  const keys = new Set(calls.map((c) => c.headers["Idempotency-Key"]));
  assert.equal(keys.size, 1);
  assert.match([...keys][0], UUID4);
});

test("each create gets a new key; idempotencyKey overrides it; uploads send it too", async () => {
  const ok = () => json(202, { id: "s", status: "processing" });
  const { sb, calls } = client([ok(), ok(), ok(), ok()]);
  await sb.analyze({ audioUrl: "https://x/a.mp3", wait: false });
  await sb.analyze({ audioUrl: "https://x/a.mp3", wait: false });
  await sb.analyze({ audioUrl: "https://x/a.mp3", wait: false, idempotencyKey: "job-42" });
  await sb.analyze({ file: Buffer.concat([Buffer.from("ID3"), Buffer.alloc(32)]), wait: false, idempotencyKey: "k1" });
  const keys = calls.map((c) => c.headers["Idempotency-Key"]);
  assert.notEqual(keys[0], keys[1]);
  assert.equal(keys[2], "job-42");
  assert.equal(keys[3], "k1");
});

test("network errors on a POST without key are not retried", async () => {
  const { sb, calls } = client([new TypeError("fetch failed")]);
  await assert.rejects(sb.testWebhook("https://example.com/hook"), (e) => e.code === "connection_error");
  assert.equal(calls.length, 1);
});

test("409 idempotency_in_progress is retried after at least a second; key_reused is thrown", async () => {
  let c = client([
    json(409, { error: { code: "idempotency_in_progress", message: "x" } }),
    json(202, { id: "s", status: "processing" }),
  ]);
  await c.sb.analyze({ audioUrl: "https://x/a.mp3", wait: false });
  assert.equal(c.sleeps.length, 1);
  assert.ok(c.sleeps[0] >= 1000);
  c = client([json(409, { error: { code: "idempotency_key_reused", message: "x" } })]);
  await assert.rejects(
    c.sb.analyze({ audioUrl: "https://x/a.mp3", wait: false, idempotencyKey: "same" }),
    (e) => e.status === 409 && e.code === "idempotency_key_reused",
  );
  assert.equal(c.calls.length, 1);
});

test("GET requests carry no Idempotency-Key", async () => {
  const { sb, calls } = client([json(200, {})]);
  await sb.account();
  assert.equal(calls[0].headers["Idempotency-Key"], undefined);
});

// ── test mode ───────────────────────────────────────────────────────────────

test("test mode needs no audio and sends test: true", async () => {
  const { sb, calls } = client([
    json(202, { id: "test_abc", status: "processing", livemode: false, billing: { type: "test", credits: 0 } }),
    json(200, { id: "test_abc", status: "done", livemode: false }),
  ]);
  const doc = await sb.analyze({ test: true, title: "CI", externalRef: "build-1" });
  assert.equal(doc.livemode, false);
  assert.deepEqual(JSON.parse(calls[0].body), { title: "CI", external_ref: "build-1", test: true });
  assert.match(calls[0].headers["Idempotency-Key"], UUID4);
});

test("test mode with a URL and with an upload; no test flag by default", async () => {
  const ok = () => json(202, { id: "test_1", status: "processing" });
  const { sb, calls } = client([ok(), ok(), ok()]);
  await sb.analyze({ audioUrl: "https://x/a.mp3", test: true, wait: false });
  assert.deepEqual(JSON.parse(calls[0].body), { audio_url: "https://x/a.mp3", test: true });
  await sb.analyze({ file: Buffer.concat([Buffer.from("ID3"), Buffer.alloc(32)]), test: true, wait: false });
  assert.deepEqual(calls[1].upload.fields, { test: "true" });
  await sb.analyze({ audioUrl: "https://x/a.mp3", wait: false });
  assert.equal(JSON.parse(calls[2].body).test, undefined);
});

test("lyrics are sent with a URL and with an upload", async () => {
  const ok = () => json(202, { id: "s", status: "processing" });
  const { sb, calls } = client([ok(), ok()]);
  const lyrics = "[Verse]\nI name the fear that held me frozen";
  await sb.analyze({ audioUrl: "https://x/a.mp3", lyrics, wait: false });
  assert.deepEqual(JSON.parse(calls[0].body), { audio_url: "https://x/a.mp3", lyrics });
  await sb.analyze({ file: Buffer.concat([Buffer.from("ID3"), Buffer.alloc(32)]), lyrics, wait: false });
  assert.deepEqual(calls[1].upload.fields, { lyrics });
});

// ── request ids and rate limits ─────────────────────────────────────────────

test("errors carry the request id from the body, else from the header", async () => {
  let c = client([
    json(400, { error: { code: "invalid_url", message: "Bad URL", request_id: "req_body" } }, { "Songbrain-Request-Id": "req_h" }),
  ]);
  await assert.rejects(c.sb.account(), (e) => {
    assert.equal(e.requestId, "req_body");
    assert.equal(e.message, "Bad URL (request_id: req_body)");
    return true;
  });
  c = client([json(404, { error: { code: "not_found", message: "x" } }, { "Songbrain-Request-Id": "req_h" })]);
  await assert.rejects(c.sb.getSong("nope"), (e) => e instanceof NotFound && e.requestId === "req_h");
  c = client([json(429, { error: { code: "daily_cap", message: "x", request_id: "req_429" } }, { "Retry-After": "3600" })]);
  await assert.rejects(c.sb.account(), (e) => e instanceof RateLimited && e.requestId === "req_429" && e.retryAfter === 3600);
  c = client([json(400, { error: { code: "c", message: "m" } })]);
  await assert.rejects(c.sb.account(), (e) => e.requestId === null && e.message === "m");
});

test("the invalid_request envelope keeps the field errors in body", async () => {
  const body = {
    error: {
      code: "invalid_request",
      message: "limit: must be <= 100",
      request_id: "req_v",
      errors: [{ field: "limit", message: "must be <= 100" }],
    },
  };
  const { sb } = client([json(400, body)]);
  await assert.rejects(sb.listSongs({ limit: 500 }), (e) => e.code === "invalid_request" && e.body.error.errors[0].field === "limit");
});

test("lastRateLimit and lastRequestId", async () => {
  const headers = {
    "X-RateLimit-Limit": "120",
    "X-RateLimit-Remaining": "119",
    "X-RateLimit-Reset": "60",
    "Songbrain-Request-Id": "req_1",
  };
  const limited = json(429, { error: { code: "rate_limited", message: "x" } }, {
    "Retry-After": "3600",
    "X-RateLimit-Limit": "120",
    "X-RateLimit-Remaining": "0",
    "X-RateLimit-Reset": "12",
  });
  const { sb } = client([json(200, {}, headers), json(200, {}), limited]);
  assert.equal(sb.lastRateLimit, null);
  assert.equal(sb.lastRequestId, null);
  await sb.account();
  assert.deepEqual(sb.lastRateLimit, { limit: 120, remaining: 119, reset: 60 });
  assert.equal(sb.lastRequestId, "req_1");
  await sb.pricing(); // no rate-limit headers: the last value stays
  assert.deepEqual(sb.lastRateLimit, { limit: 120, remaining: 119, reset: 60 });
  assert.equal(sb.lastRequestId, null);
  await assert.rejects(sb.account(), RateLimited);
  assert.deepEqual(sb.lastRateLimit, { limit: 120, remaining: 0, reset: 12 });
});

// ── pagination ──────────────────────────────────────────────────────────────

test("listSongs passes limit and startingAfter", async () => {
  const page = { object: "list", data: [{ id: "s9", livemode: true }], has_more: true, next_cursor: "s9" };
  const { sb, calls } = client([json(200, page), json(200, { object: "list", data: [], has_more: false, next_cursor: null })]);
  const out = await sb.listSongs({ limit: 1, startingAfter: "s10" });
  assert.equal(out.has_more, true);
  assert.equal(out.next_cursor, "s9");
  let u = new URL(calls[0].url);
  assert.equal(u.searchParams.get("limit"), "1");
  assert.equal(u.searchParams.get("starting_after"), "s10");
  await sb.listSongs();
  u = new URL(calls[1].url);
  assert.equal(u.searchParams.get("limit"), "20");
  assert.equal(u.searchParams.has("starting_after"), false);
});

test("iterSongs follows the cursors", async () => {
  const { sb, calls } = client([
    json(200, { object: "list", data: [{ id: "s5" }, { id: "s4" }], has_more: true, next_cursor: "s4" }),
    json(200, { object: "list", data: [{ id: "s3" }, { id: "s2" }], has_more: true, next_cursor: "s2" }),
    json(200, { object: "list", data: [{ id: "s1" }], has_more: false, next_cursor: null }),
  ]);
  const ids = [];
  for await (const item of sb.iterSongs({ pageSize: 2 })) ids.push(item.id);
  assert.deepEqual(ids, ["s5", "s4", "s3", "s2", "s1"]);
  const cursors = calls.map((c) => new URL(c.url).searchParams.get("starting_after"));
  assert.deepEqual(cursors, [null, "s4", "s2"]);
  assert.ok(calls.every((c) => new URL(c.url).searchParams.get("limit") === "2"));
});

test("iterSongs is lazy and handles an empty account", async () => {
  const { sb, calls } = client([json(200, { object: "list", data: [], has_more: false, next_cursor: null })]);
  const it = sb.iterSongs();
  assert.equal(calls.length, 0);
  const all = [];
  for await (const item of it) all.push(item);
  assert.deepEqual(all, []);
  assert.equal(calls.length, 1);
});

// ── webhooks ────────────────────────────────────────────────────────────────

test("testWebhook and webhookDeliveries", async () => {
  const result = { delivered: true, status_code: 200, latency_ms: 85, event_id: "evt_1" };
  const list = { object: "list", data: [{ event_id: "evt_1", type: "ping", delivered: true, attempt: 1 }] };
  const { sb, calls } = client([json(200, result), json(200, list)]);
  assert.deepEqual(await sb.testWebhook("https://example.com/hook"), result);
  assert.equal(calls[0].method, "POST");
  assert.ok(calls[0].url.endsWith("/webhooks/test"));
  assert.deepEqual(JSON.parse(calls[0].body), { url: "https://example.com/hook" });
  assert.equal((await sb.webhookDeliveries({ limit: 5 })).data[0].event_id, "evt_1");
  const u = new URL(calls[1].url);
  assert.equal(calls[1].method, "GET");
  assert.ok(u.pathname.endsWith("/webhooks/deliveries"));
  assert.equal(u.searchParams.get("limit"), "5");
});
