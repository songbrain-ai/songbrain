# Songbrain

[![CI](https://github.com/songbrain-ai/songbrain/actions/workflows/ci.yml/badge.svg)](https://github.com/songbrain-ai/songbrain/actions/workflows/ci.yml)
[![PyPI](https://img.shields.io/pypi/v/songbrain?label=pypi)](https://pypi.org/project/songbrain/)
[![npm](https://img.shields.io/npm/v/songbrain)](https://www.npmjs.com/package/songbrain)
[![MCP Registry](https://img.shields.io/badge/MCP%20Registry-io.github.songbrain--ai%2Fsongbrain-6e56cf)](https://registry.modelcontextprotocol.io/v0/servers?search=io.github.songbrain-ai/songbrain)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

**Song in, video plan out — the music analysis API for AI video.**

Send a song. Get back JSON that a video model can use directly: what the song is, where the beats and sections are, which part to use, what the words are and when they are sung, what the video should show, and a shot list with a prompt for every scene that cuts on the beat.

This repository holds the official SDKs for Python and JavaScript/TypeScript, examples, and the MCP server entry.

- API docs: https://www.songbrain.ai/docs/api
- OpenAPI: https://api.songbrain.ai/v1/openapi.json
- Get a key (5 free songs a month): https://app.songbrain.ai/developers
- Changelog: [SDKs](CHANGELOG.md) · [API](https://www.songbrain.ai/docs/api/changelog)

## Try it now, no key

```bash
curl https://api.songbrain.ai/v1/examples/old-truck-home/shot-plan
```

This returns the story and shot plan of a real song in exactly the format your songs get. `GET /v1/examples` lists all examples.

## What one call returns

One document per song (schema `songbrain.song/1`). Times are seconds from the start of the song.

| Section | What is in it |
|---|---|
| `song_dna` | Genre and subgenre (37 subgenres), tempo, key and key changes, mood, vocal style, instruments, energy, loudness (LUFS, true peak, per-platform check), a tagline and similar tracks |
| `timeline` | Every beat, every downbeat, time signature, sections with repeat letters (A, B, A) and energy, vocal changes, lyric hooks |
| `best_moments` | Ranked windows with start, peak and end, a score, the reason they work and the measured signals behind it, the beats inside, the words sung |
| `lyrics` | Lines with start and end, and every word with its own start and end |
| `scores` | Virality, quality and lyrics scores with breakdowns, what works, what to fix, audience |
| `story` | What the song means, one world, a three-colour palette, the one element the video is about (before, event, after), setup / turn / payoff |
| `shot_plan` | A beat-synced edit of the best moment (about 15 s, 9:16): every scene with absolute start and end seconds, act, kind, camera motion, transition, framing and a ready image/video prompt. Plus a section-level plan for the full song with cut points on the beat |

One scene from the shot plan:

```json
{
  "index": 1,
  "kind": "tease",
  "act": "setup",
  "start_sec": 94.83,
  "end_sec": 96.246,
  "duration_sec": 1.416,
  "beats_in_scene": 4,
  "transition_in": "cold open, hold",
  "motion": "slow push-in on a still world",
  "prompt": "wide establishing shot of the empty space: A distant, warm yellow light source pulses faintly in the deep blue night ...",
  "sung": null
}
```

A song takes 60–90 seconds to analyse (up to about 2 minutes when busy).

## Install

```bash
pip install songbrain     # Python 3.9+, one dependency (requests)
npm install songbrain     # Node 18+, no runtime dependencies, ESM + CJS + types
```

Packages: [PyPI](https://pypi.org/project/songbrain/) · [npm](https://www.npmjs.com/package/songbrain).

## Quickstart: Python

```python
from songbrain import Songbrain

sb = Songbrain()                                   # reads SONGBRAIN_API_KEY
song = sb.analyze("song.mp3")                      # or analyze(audio_url="https://…")

dna = song["song_dna"]
print(dna["genre"], dna["tempo_bpm"], dna["key"])
for s in song["shot_plan"]["clip"]["scenes"]:
    print(f'{s["start_sec"]:.2f}-{s["end_sec"]:.2f} [{s["act"]}] {s["prompt"]}')
```

## Quickstart: TypeScript / JavaScript

```ts
import { Songbrain } from "songbrain";

const sb = new Songbrain();                        // reads SONGBRAIN_API_KEY
const song = await sb.analyze({ file: "song.mp3" }); // or { audioUrl: "https://…" }

const dna = song.song_dna!;
console.log(dna.genre, dna.tempo_bpm, dna.key);
for (const s of song.shot_plan?.clip?.scenes ?? []) {
  console.log(`${s.start_sec.toFixed(2)}-${s.end_sec.toFixed(2)} [${s.act}] ${s.prompt}`);
}
```

`analyze()` uploads, waits until the song is done and returns the full document. Pass `wait=False` (Python) or `wait: false` (JS) to get the id right away, then use a webhook or `get_song` / `getSong` later.

## SDK methods

Python uses snake_case and JS uses camelCase method names. Response fields are the API's own names in both.

| Python | JavaScript | API | Key |
|---|---|---|---|
| `analyze(file \| audio_url=…, test=False, idempotency_key=None, wait=True)` | `analyze({ file \| audioUrl, test, idempotencyKey, wait })` | `POST /v1/songs` + polling | yes |
| `get_song(id, view, include)` | `getSong(id, { view, include })` | `GET /v1/songs/{id}` | yes |
| `shot_plan(id)` | `shotPlan(id)` | `GET /v1/songs/{id}/shot-plan` | yes |
| `list_songs(limit, starting_after)` | `listSongs({ limit, startingAfter })` | `GET /v1/songs` | yes |
| `iter_songs(page_size)` | `iterSongs({ pageSize })` | `GET /v1/songs`, every page | yes |
| `delete_song(id)` | `deleteSong(id)` | `DELETE /v1/songs/{id}` | yes |
| `account()` | `account()` | `GET /v1/account` | yes |
| `test_webhook(url)` | `testWebhook(url)` | `POST /v1/webhooks/test` | yes |
| `webhook_deliveries(limit)` | `webhookDeliveries({ limit })` | `GET /v1/webhooks/deliveries` | yes |
| `pricing()` | `pricing()` | `GET /v1/pricing` | no |
| `examples()` | `examples()` | `GET /v1/examples` | no |
| `example(id, view, include)` | `example(id, { view, include })` | `GET /v1/examples/{id}` | no |
| `example_shot_plan(id)` | `exampleShotPlan(id)` | `GET /v1/examples/{id}/shot-plan` | no |
| `webhooks.verify(body, header, secret)` | `verifyWebhook(body, header, secret)` | `Songbrain-Signature` header | – |

Both SDKs:

- send the key as `Authorization: Bearer sb_live_…`,
- raise `SongbrainError` (`status`, `code`, `message`, `request_id` / `requestId`) and the subclasses `AuthenticationError`, `InsufficientCredits`, `NotFound`, `RateLimited` (with `retry_after` / `retryAfter`), `AnalysisFailed` and `WaitTimeout`,
- send an `Idempotency-Key` with every new song and retry network errors, 429 and 5xx up to 3 times with backoff, honouring `Retry-After`,
- keep the last rate-limit headers in `last_rate_limit` / `lastRateLimit`.

Package docs: [python/README.md](python/README.md) · [js/README.md](js/README.md)

## Without an SDK

```bash
# 1. send a file (or JSON {"audio_url": "https://…"})
curl -X POST https://api.songbrain.ai/v1/songs \
  -H "Authorization: Bearer $SONGBRAIN_API_KEY" \
  -F "file=@song.mp3" -F "title=My Song"
# → 202 {"id": "…", "status": "processing", "eta_sec": 75, "billing": {…}}

# 2. poll until status is "done"
curl https://api.songbrain.ai/v1/songs/$ID -H "Authorization: Bearer $SONGBRAIN_API_KEY"
```

Options on document endpoints: `?view=summary` drops word timings and beat arrays (about 3x smaller). `?include=song_dna,shot_plan` returns only the named sections.

Errors always look like `{"error": {"code": "…", "message": "…", "request_id": "req_…"}}` with HTTP 400, 401, 402, 404, 409, 413, 415 or 429. A 429 carries a `Retry-After` header.

## Test mode

Send `"test": true` (or `test=True` / `test: true` in the SDKs) and the song is free, needs no audio and is done right away. You get the Sugar Rush example analysis with your `title` and `external_ref`, `"livemode": false` and `billing.type = "test"`. A `webhook_url` still gets a signed `song.done` within seconds. It is made for CI and for building your integration before you spend a song.

```python
song = sb.analyze(test=True, external_ref="ci-123")   # done right away, costs nothing
assert song["livemode"] is False
```

Test songs never use your free songs, but they are rate-limited and count toward the daily cap. A pytest example: [cookbook/ci_test_mode.py](cookbook/ci_test_mode.py).

## Idempotency

`POST /v1/songs` accepts an `Idempotency-Key` header (1–255 printable characters). The same key on the same account within 24 hours returns the first answer again (same song id, no second charge) with `Idempotent-Replayed: true`. The same key with a different request is a 409 `idempotency_key_reused`; a key whose first request is still running is a 409 `idempotency_in_progress` (retry after a second). Failed first requests are not stored, so the key can be retried.

Both SDKs send a random key with every `analyze()` and reuse it across their own retries, so a timeout during an upload never creates two songs. Pass your own key (`idempotency_key=` / `idempotencyKey`), e.g. your job id, to make retries across processes safe too.

## Pagination

`GET /v1/songs?limit=20&starting_after=<song id>` returns the newest songs first with `has_more` and `next_cursor`. Pass `next_cursor` as `starting_after` for the next page, or let the SDK do it:

```python
for item in sb.iter_songs():           # Python
    print(item["id"], item["status"], item["livemode"])
```

```ts
for await (const item of sb.iterSongs()) console.log(item.id, item.status); // JS
```

## Request ids and rate limits

Every response has a `Songbrain-Request-Id: req_…` header, and every error body repeats it as `error.request_id`. The SDKs put it on the error (`request_id` / `requestId`) and in its message. Quote it when you contact support.

Requests with a key return `X-RateLimit-Limit` (requests per minute, currently 120), `X-RateLimit-Remaining` and `X-RateLimit-Reset` (seconds until the window has room again). The SDKs keep the last values in `sb.last_rate_limit` / `sb.lastRateLimit`.

## Webhooks

Pass `webhook_url` when you create a song. Songbrain POSTs `song.done` or `song.failed`, and `account.low_balance` when you run low:

```json
{"id": "evt_…", "type": "song.done", "created": 1791200000, "livemode": true, "data": {"id": "…", "status": "done", "external_ref": "…"}}
```

- **Signature.** Every webhook has the header `Songbrain-Signature: t=<unix>,v1=<hex>`. `v1` is the HMAC-SHA256 of `"<t>.<raw body>"` with your key's webhook secret. Both SDKs verify it for you (`webhooks.verify` / `verifyWebhook`).
- **Dedupe on the event id.** `id` (also in the `Songbrain-Event-Id` header) stays the same when an event is retried. Store the ids you have handled and answer 2xx to repeats.
- **Retries.** Anything but a 2xx is retried, up to 10 attempts over about 3 days: right away, then 1 min, 5 min, 30 min, 2 h, 6 h, 12 h, 24 h, 48 h and 72 h after the first attempt. Redirects are not followed.
- **Test ping.** `POST /v1/webhooks/test {"url": "…"}` (`test_webhook` / `testWebhook`) sends a signed `ping` right now and tells you whether it was delivered. `GET /v1/webhooks/deliveries` (`webhook_deliveries` / `webhookDeliveries`) lists the last attempts with status codes.

Receivers: [cookbook/webhook_receiver_fastapi.py](cookbook/webhook_receiver_fastapi.py) (FastAPI, with dedupe) and [examples/python/webhook_server.py](examples/python/webhook_server.py) (Flask).

## MCP

Songbrain runs a remote MCP server at `https://api.songbrain.ai/mcp` (streamable HTTP). It works in Claude Code, Claude Desktop, Cursor and other MCP clients. Without a key you get the example tools. With a key you can analyse songs from a URL.

```bash
claude mcp add --transport http songbrain https://api.songbrain.ai/mcp \
  --header "Authorization: Bearer sb_live_…"
```

Setup for each client: [examples/mcp.md](examples/mcp.md). Registry name: `io.github.songbrain-ai/songbrain` ([server.json](server.json)).

## Examples

| File | What it does |
|---|---|
| [examples/python/shot_plan_to_prompts.py](examples/python/shot_plan_to_prompts.py) | Analyse a file or URL and print each scene as `01:34.8–01:36.2 [setup] prompt…` |
| [examples/node/shot-plan-to-prompts.mjs](examples/node/shot-plan-to-prompts.mjs) | The same in Node |
| [examples/python/webhook_server.py](examples/python/webhook_server.py) | A Flask receiver that verifies the signature |
| [examples/render-with-your-model.md](examples/render-with-your-model.md) | Feed the scene prompts to Kling, Runway, Luma, Veo or fal and cut on the given seconds |
| [examples/mcp.md](examples/mcp.md) | MCP setup for Claude Code, Claude Desktop and Cursor |

Run either script with `--example old-truck-home` to try it without a key.

## Cookbook

Runnable recipes in [cookbook/](cookbook/README.md). All work with `--example sugar-rush` (no key), and the video ones have a `--dry-run` that prints every call and the ffmpeg command.

| Recipe | What it does |
|---|---|
| [song_to_clips_fal.py](cookbook/song_to_clips_fal.py) | One fal.ai video clip per shot-plan scene, stitched on the beat with the song underneath |
| [song_to_clips_replicate.py](cookbook/song_to_clips_replicate.py) | The same on Replicate |
| [beat_synced_slideshow.py](cookbook/beat_synced_slideshow.py) | A folder of images cut on scenes, beats, bars or sections with ffmpeg. No AI keys |
| [webhook_receiver_fastapi.py](cookbook/webhook_receiver_fastapi.py) | Signature check, dedupe by event id, ping / song.done / song.failed |
| [ci_test_mode.py](cookbook/ci_test_mode.py) | pytest tests for CI with test mode |

## Postman

Import [postman/Songbrain.postman_collection.json](postman/Songbrain.postman_collection.json) into Postman, Insomnia or Bruno. Set `apiKey`, then run **Songs → Create song (test mode)**. Every endpoint is in it, with cursor pagination and an `Idempotency-Key` on creates.

## Pricing

- 5 free songs per account per month.
- Then 25 credits per song, about $0.50. Credits come in packs (500 credits = $10, 150 credits = $4.99).
- No subscription. Everything is included in that price: analysis, story and shot plan.
- Limits: files up to 100 MB, 30 s to 10 min; 3 songs in parallel; 200 songs per 24 h; 120 requests per minute per key.
- Over 1,000 songs a month, an invoice, a DPA or an SLA: support@songbrain.ai.

Live prices: `GET https://api.songbrain.ai/v1/pricing`.

## Commercial use

The short version of [Terms §17](https://www.songbrain.ai/terms#api):

- You can use the API in a paid SaaS, including products that make images or videos for your customers.
- You can pass results to your users, changed or unchanged.
- White-label is fine. No attribution to Songbrain is required.
- The results for your songs are yours. You can keep them after you delete a song or close the account.
- You can train your own models on results, except a model built to reproduce the Songbrain API for others.
- Reselling raw API access or bulk datasets needs written consent.

Audio is used only for the analysis and never for training. Uploads are deleted within 24 hours.

## Repository layout

```
python/      PyPI package "songbrain"
js/          npm package "songbrain"
examples/    scripts and guides
cookbook/    runnable recipes (AI clips, slideshow, webhooks, CI)
postman/     Postman collection
server.json  MCP Registry entry
.github/     CI and publish workflows (tags py-v*, js-v*, mcp-v*)
```

## Links

- Product: https://www.songbrain.ai/api-access
- API reference: https://www.songbrain.ai/docs/api
- Interactive docs: https://api.songbrain.ai/v1/docs
- OpenAPI 3.1: https://api.songbrain.ai/v1/openapi.json
- Developer console: https://app.songbrain.ai/developers
- Changelog: [SDKs](CHANGELOG.md) · [API](https://www.songbrain.ai/docs/api/changelog)
- Support: support@songbrain.ai · Security: [SECURITY.md](SECURITY.md) · Contributing: [CONTRIBUTING.md](CONTRIBUTING.md)

## License

MIT © 2026 Songbrain. See [LICENSE](LICENSE). The license covers the SDK code; use of the API is governed by the [Terms](https://www.songbrain.ai/terms#api).
