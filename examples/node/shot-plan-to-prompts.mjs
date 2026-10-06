// Analyse a song and print its shot plan, one scene per line.
//
//   npm install songbrain
//   export SONGBRAIN_API_KEY=sb_live_...
//
//   node shot-plan-to-prompts.mjs song.mp3
//   node shot-plan-to-prompts.mjs https://example.com/song.mp3
//   node shot-plan-to-prompts.mjs --example old-truck-home   # no key needed
//
// Output:
//
//   01:34.8–01:36.2 [setup] wide establishing shot of the empty space: ...

import { Songbrain, SongbrainError } from "songbrain";

const timecode = (sec) => {
  const m = Math.floor(sec / 60);
  const s = sec - m * 60;
  return `${String(m).padStart(2, "0")}:${s.toFixed(1).padStart(4, "0")}`;
};

async function main(args) {
  const exampleAt = args.indexOf("--example");
  const exampleId = exampleAt >= 0 ? args[exampleAt + 1] : undefined;
  const fullSong = args.includes("--full-song");
  const source = args.find((a, i) => !a.startsWith("--") && (exampleAt < 0 || i !== exampleAt + 1));

  if (!exampleId && !source) {
    console.error("Usage: node shot-plan-to-prompts.mjs <file | url> [--full-song]");
    console.error("       node shot-plan-to-prompts.mjs --example old-truck-home");
    return 2;
  }

  const sb = new Songbrain();
  let doc;
  try {
    if (exampleId) {
      doc = await sb.exampleShotPlan(exampleId);
    } else if (/^https?:\/\//.test(source)) {
      console.error("Analysing (typically 60-90 s)...");
      doc = await sb.analyze({ audioUrl: source });
    } else {
      console.error("Uploading and analysing (typically 60-90 s)...");
      doc = await sb.analyze({ file: source });
    }
  } catch (e) {
    if (e instanceof SongbrainError) {
      console.error(`Error: [${e.status}] ${e.code}: ${e.message}`);
      return 1;
    }
    throw e;
  }

  const plan = doc.shot_plan ?? {};
  if (plan.status !== "ready") {
    console.error(`No shot plan: ${plan.status} ${plan.reason ?? ""}`.trim());
    return 1;
  }

  if (fullSong) {
    for (const row of plan.full_song?.sections ?? []) {
      console.log(`${timecode(row.start_sec)}–${timecode(row.end_sec)} [${row.act}] cut every ${row.cut_every_beats} beats: ${row.prompt ?? ""}`);
    }
  } else {
    for (const scene of plan.clip.scenes) {
      console.log(`${timecode(scene.start_sec)}–${timecode(scene.end_sec)} [${scene.act}] ${scene.prompt ?? ""}`);
    }
  }
  return 0;
}

process.exitCode = await main(process.argv.slice(2));
