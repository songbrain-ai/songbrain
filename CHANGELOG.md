# Changelog

All notable changes to the Songbrain SDKs in this repository. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and both packages use [Semantic Versioning](https://semver.org/).

The Python package (`songbrain` on PyPI, tags `py-v*`) and the npm package (`songbrain` on npm, tags `js-v*`) are released together when they share a version. Changes to the API itself are in the [API changelog](https://www.songbrain.ai/docs/api/changelog).

## [0.4.0] - 2026-10-20

For API 1.3. Backwards compatible with 0.3.x code: without `mode`, songs are `full` as before.

### Added

- **Two modes.** `analyze(..., mode="dna")` / `analyze({ ..., mode: "dna" })` returns the Song DNA only (`song_dna`, `timeline`, `best_moments`, `lyrics`, `scores`; no `story`, no `shot_plan`) for 10 credits (about $0.20). `mode="full"` is the API default: Song DNA + video direction, 25 credits (about $0.50). Without `mode` the SDK sends nothing and the API uses `full`. A free song covers either mode.
- **Add the video direction later.** `add_direction(song_id)` / `addDirection(songId)` calls `POST /v1/songs/{id}/direction` (15 credits, about $0.30, never a free song) and waits until the song is `done` again with `story` and `shot_plan` (about 30–40 s). `wait=False` / `{ wait: false }` returns the 202 body. If the direction fails, the API refunds the credits, the song stays `dna`, and the SDK raises `AnalysisFailed` with code `direction_failed`. API errors: 409 `direction_included`, `not_done`, `song_failed`, `direction_in_progress`; 402 `insufficient_credits`. Test-mode songs upgrade right away, for free.
- `example(id, mode="dna")` / `example(id, { mode: "dna" })` shows what a Song DNA-only song looks like. No key needed.
- **Types for API 1.3:** `Mode` (`"full" | "dna"`); `mode` and `direction` (`DirectionOffer`) on songs; `mode` on `SongCreated` and list items; `DirectionCreated` (the 202 body of the direction call); `prices` on `Account`; `modes`, `add_direction` and `free_songs_cover` on `Pricing`, with `Price`, `ModePrice` and `AddDirectionPrice`. `price_per_song_*` still means `full`.
- Webhook docs: every `song.*` event has `data.mode`; `shot_plan_url` is only set for `full` songs; after an upgrade a second `song.done` arrives with its own event id and `data.direction_added: true`.
- Postman: `mode` on the create requests and an **Add video direction** request.

### Changed

- `shot_plan()` / `shotPlan()` docs: a `dna` song answers 409 `no_direction`, and the error body's `direction` says how to add it.

## [0.3.3] - 2026-10-19

### Added

- User-Agent names the coding agent when the SDK runs inside one: `songbrain-python/0.3.3 (agent: claude-code)`. Read from the agents' own environment variables (`AI_AGENT`, `CLAUDECODE`, `CURSOR_AGENT`, `GEMINI_CLI`, `CODEX_SANDBOX`, `OPENCODE`, `AUGMENT_AGENT`); only the name is sent. Turn it off with `SONGBRAIN_NO_AGENT_HINT=1`.

## [0.3.2] - 2026-10-18

Metadata only. No code changes.

### Changed

- Package keywords on PyPI and npm now also name the video side: AI video API, video generation prompts, text-to-video and image-to-video, music video prompts.
- READMEs: a "Prompts for video models" section that explains how `best_moments` picks the window and `shot_plan` carries one ready prompt per scene, with links to the fal and Replicate recipes.

## [0.3.1] - 2026-10-18

Metadata only. No code changes; 0.3.0 code keeps working.

### Changed

- Package keywords on PyPI and npm now name what the API measures (audio features, tempo, BPM and key detection, song sections, music information retrieval) and that it replaces Spotify's retired Audio Features / Audio Analysis endpoints for new apps.
- READMEs: a "Coming from Spotify Audio Features?" section with the field-by-field mapping and a link to the migration guide.

## [0.3.0] - 2026-10-07

For API 1.2. Backwards compatible with 0.2.x code.

### Added

- **Your own lyrics.** `analyze(..., lyrics="...")` / `analyze({ ..., lyrics })` sends the song's lyrics (plain text, up to 20,000 characters). The analysis uses your exact words on the transcription's timing; `lyrics.source` is then `"provided_lyrics"`.
- **Types for API 1.2:** `provenance` on the song (which fields are measured, transcribed, model estimates or generated), `basis` / `basis_note` on scores, `source` / `basis` / `note` / `alignment` on lyrics, `confidence` on lyric lines; new `Provenance` and `LyricsAlignment` types.


For API 1.1. Everything is backwards compatible with 0.1.x code.

### Added

- **Idempotency.** Every `analyze()` sends an `Idempotency-Key` (a random UUID) and reuses it across the client's own retries. Pass your own with `idempotency_key=` (Python) or `idempotencyKey` (JS).
- **Test mode.** `analyze(test=True)` / `analyze({ test: true })`: free, no audio needed, done right away, `livemode: false`.
- **Request ids.** Errors have `request_id` (Python) / `requestId` (JS), taken from the error body or the `Songbrain-Request-Id` header, and show it in the error text.
- **Rate-limit info.** `last_rate_limit` / `lastRateLimit` (`{limit, remaining, reset}` from the `X-RateLimit-*` headers) and `last_request_id` / `lastRequestId` on the client.
- **Pagination.** `list_songs(limit, starting_after)` / `listSongs({ limit, startingAfter })` return `has_more` and `next_cursor`; `iter_songs()` (generator) / `iterSongs()` (async iterator) walk all pages.
- **Webhooks.** `test_webhook(url)` / `testWebhook(url)` sends a signed `ping`; `webhook_deliveries(limit)` / `webhookDeliveries({ limit })` lists the last delivery attempts.
- **Types.** `livemode` on songs, list items and events; webhook event `id` and the `ping` type; `has_more` / `next_cursor` on lists; `RateLimitInfo`, `WebhookEvent` (Python), `WebhookTestResult`, `WebhookDelivery`, `WebhookDeliveryList`.
- Cookbook recipes (`cookbook/`), a Postman collection (`postman/`), CHANGELOG, SECURITY and CONTRIBUTING.

### Changed

- Song creation is now retried on network errors, 5xx, 429 and `409 idempotency_in_progress`, because the idempotency key makes a retry safe. Other POST requests are still only retried when nothing can have been created.
- Webhook docs: dedupe on the event `id`; deliveries are retried up to 10 times over about 3 days. Signature verification is unchanged.

## [0.1.2] (JS) / [0.1.1] (Python) - 2026-10-06

### Changed

- `best_moments` types follow the API cleanup: `reason` and `signals` replace `why`, `explanation` and `judge_note`; `platform_fit`, `caption_ideas` and `hashtags` are removed.

## 0.1.1 (JS) - 2026-10-06

- Release only: the first npm release through Trusted Publishing, with provenance. No code changes.

## [0.1.0] - 2026-10-06

### Added

- First release of the Python and TypeScript SDKs: `analyze` (file or URL, with waiting), `wait_for` / `waitFor`, `get_song`, `shot_plan`, `list_songs`, `delete_song`, `account`, `pricing`, the no-key example endpoints, webhook signature helpers, typed responses, retries with backoff and `Retry-After`.
- Examples and the MCP Registry entry (`io.github.songbrain-ai/songbrain`).

[0.2.0]: https://github.com/songbrain-ai/songbrain/compare/py-v0.1.1...HEAD
[0.1.2]: https://github.com/songbrain-ai/songbrain/releases/tag/js-v0.1.2
[0.1.1]: https://github.com/songbrain-ai/songbrain/releases/tag/py-v0.1.1
[0.1.0]: https://github.com/songbrain-ai/songbrain/releases/tag/py-v0.1.0
