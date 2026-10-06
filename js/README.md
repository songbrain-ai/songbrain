# songbrain

**Song in, video plan out.** The official TypeScript/JavaScript client for the [Songbrain API](https://www.songbrain.ai/docs/api), the music analysis API for AI video.

One call returns the song DNA (genre, tempo, key, mood, instruments, loudness), a beat grid, sections, the best moments with reasons, word-timed lyrics, the story, world and palette, and a beat-synced shot plan with a ready prompt for every scene.

```bash
npm install songbrain
```

Node 18+. No runtime dependencies. ESM and CommonJS, with types.

## Quickstart

Get a key at [app.songbrain.ai/developers](https://app.songbrain.ai/developers). 5 songs a month are free.

```ts
import { Songbrain } from "songbrain";

const sb = new Songbrain(); // reads SONGBRAIN_API_KEY

const song = await sb.analyze({ file: "song.mp3" }); // or { audioUrl: "https://…/song.mp3" }

console.log(song.song_dna?.genre, song.song_dna?.tempo_bpm, song.song_dna?.key);
for (const s of song.shot_plan?.clip?.scenes ?? []) {
  console.log(`${s.start_sec.toFixed(2)}-${s.end_sec.toFixed(2)} [${s.act}] ${s.prompt}`);
}
```

`analyze()` uploads the song, waits until the analysis is done (typically 60–90 s) and resolves to the full document.

CommonJS works too: `const { Songbrain } = require("songbrain");`

## Try it without a key

```ts
const sb = new Songbrain();
const { data } = await sb.examples();
const plan = await sb.exampleShotPlan("old-truck-home");
console.log(plan.shot_plan?.clip?.scenes[0]?.prompt);
```

## Methods

Every method resolves to the JSON body of the response. Field names are exactly the API's (snake_case). Types are exported: `Song`, `SongDNA`, `Timeline`, `BestMoment`, `Lyrics`, `Scores`, `Story`, `ShotPlan`, `Scene`, and more.

| Method | API call | Key |
|---|---|---|
| `analyze({ file?, audioUrl?, title?, artist?, webhookUrl?, externalRef?, filename?, wait = true, pollIntervalMs = 5000, timeoutMs = 300000 })` | `POST /songs`, then polls | yes |
| `waitFor(id, { pollIntervalMs?, timeoutMs? })` | polls `GET /songs/{id}` | yes |
| `getSong(id, { view?, include? })` | `GET /songs/{id}` | yes |
| `shotPlan(id)` | `GET /songs/{id}/shot-plan` | yes |
| `listSongs({ limit = 20 })` | `GET /songs` | yes |
| `deleteSong(id)` | `DELETE /songs/{id}` | yes |
| `account()` | `GET /account` | yes |
| `pricing()` | `GET /pricing` | no |
| `examples()` | `GET /examples` | no |
| `example(id, { view?, include? })` | `GET /examples/{id}` | no |
| `exampleShotPlan(id)` | `GET /examples/{id}/shot-plan` | no |

- `file` can be a path, a `Buffer`/`Uint8Array`, an `ArrayBuffer` or a `Blob`/`File`. MP3, WAV, FLAC, M4A, AAC, OGG or AIFF, up to 100 MB, 30 s to 10 min. The file name's extension has to match the audio; for bytes without a name the client detects the format or you pass `filename: "song.mp3"`.
- `wait: false` resolves to the 202 body right away: `{ id, status: "processing", eta_sec, billing }`.
- `view: "summary"` drops word timings and beat arrays (about 3x smaller). `include: ["song_dna", "shot_plan"]` returns only those sections.

```ts
new Songbrain({ apiKey: "sb_live_…", timeoutMs: 60_000, maxRetries: 3 });
```

Keep the key on your server. Never ship it in a browser or app bundle.

## Errors

API errors throw `SongbrainError` with `status`, `code` and `message`. Subclasses: `AuthenticationError` (401), `InsufficientCredits` (402), `NotFound` (404), `RateLimited` (429, with `retryAfter` in seconds), `AnalysisFailed` (the song failed; credits are refunded) and `WaitTimeout` (the song keeps processing).

The client retries 429 and 5xx responses up to 3 times with backoff and honours `Retry-After` (up to 60 s). Uploads are only retried when nothing can have been created (429, 502, 503).

```ts
import { Songbrain, InsufficientCredits, RateLimited } from "songbrain";

try {
  await new Songbrain().analyze({ audioUrl: "https://example.com/song.mp3" });
} catch (e) {
  if (e instanceof InsufficientCredits) console.log("Top up at https://app.songbrain.ai/developers/billing");
  else if (e instanceof RateLimited) console.log("Try again in", e.retryAfter, "s");
  else throw e;
}
```

## Webhooks

Pass `webhookUrl` and Songbrain POSTs `song.done` or `song.failed` (and `account.low_balance`). Verify the `Songbrain-Signature` header against the raw body:

```ts
import express from "express";
import { verifyWebhook } from "songbrain";

app.post("/songbrain", express.raw({ type: "application/json" }), (req, res) => {
  if (!verifyWebhook(req.body, req.get("Songbrain-Signature"), process.env.SONGBRAIN_WEBHOOK_SECRET!)) {
    return res.sendStatus(400);
  }
  const event = JSON.parse(req.body.toString("utf8"));
  // event.type: "song.done" | "song.failed" | "account.low_balance"
  res.sendStatus(200);
});
```

`verifyWebhook(rawBody, header, secret, toleranceSec = 300)` returns a boolean. `constructWebhookEvent()` verifies and parses in one step.

## Pricing

5 free songs per account per month. Then 25 credits per song (about $0.50). No subscription. Everything is included: analysis, story and shot plan. Results are yours, also in a paid or white-label product. See [Terms §17](https://www.songbrain.ai/terms#api).

## Links

- API docs: https://www.songbrain.ai/docs/api
- OpenAPI: https://api.songbrain.ai/v1/openapi.json
- MCP server: https://api.songbrain.ai/mcp
- Get a key: https://app.songbrain.ai/developers
- Source: https://github.com/songbrain-ai/songbrain

MIT License.
