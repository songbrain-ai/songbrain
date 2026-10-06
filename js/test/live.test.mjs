// Live tests against the public, no-key example endpoints.
// Skip them offline with SONGBRAIN_OFFLINE=1.
import { test } from "node:test";
import assert from "node:assert/strict";
import { Songbrain, NotFound } from "../dist/index.js";

const skip = !!process.env.SONGBRAIN_OFFLINE && process.env.SONGBRAIN_OFFLINE !== "0" ? "SONGBRAIN_OFFLINE is set" : false;
const sb = new Songbrain({ apiKey: "" });
const EXAMPLE = "old-truck-home";

test("live: list examples", { skip }, async () => {
  const out = await sb.examples();
  assert.equal(out.object, "list");
  assert.ok(out.data.some((e) => e.id === EXAMPLE));
});

test("live: full example document", { skip }, async () => {
  const doc = await sb.example(EXAMPLE);
  assert.equal(doc.schema, "songbrain.song/1");
  assert.equal(doc.status, "done");
  assert.ok(doc.song_dna.tempo_bpm > 0);
  assert.ok(Array.isArray(doc.timeline.beats) && doc.timeline.beats.length > 0);
  assert.equal(doc.best_moments[0].rank, 1);
  assert.ok(doc.lyrics.lines[0].words.length > 0);
  assert.ok(doc.story.story_beats.setup);
  const scenes = doc.shot_plan.clip.scenes;
  assert.ok(scenes.length > 0 && scenes.every((s) => s.end_sec > s.start_sec));
});

test("live: summary view with include", { skip }, async () => {
  const doc = await sb.example(EXAMPLE, { view: "summary", include: ["song_dna", "shot_plan"] });
  assert.ok(doc.song_dna && doc.shot_plan);
  assert.equal(doc.lyrics, undefined);
});

test("live: example shot plan", { skip }, async () => {
  const out = await sb.exampleShotPlan(EXAMPLE);
  const scene = out.shot_plan.clip.scenes[0];
  for (const k of ["start_sec", "end_sec", "act", "kind", "prompt"]) assert.ok(k in scene, k);
});

test("live: pricing", { skip }, async () => {
  assert.ok((await sb.pricing()).free_songs_per_month >= 0);
});

test("live: unknown example is NotFound", { skip }, async () => {
  await assert.rejects(sb.example("does-not-exist"), (e) => e instanceof NotFound && e.code === "not_found");
});
