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

test("5xx is retried for GET, 500 is not retried for POST", async () => {
  let c = client([json(500, { error: { code: "x", message: "y" } }), json(200, { ok: true })]);
  assert.deepEqual(await c.sb.pricing(), { ok: true });
  c = client([json(500, { error: { code: "x", message: "y" } })]);
  await assert.rejects(c.sb.analyze({ audioUrl: "https://example.com/a.mp3", wait: false }), SongbrainError);
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
