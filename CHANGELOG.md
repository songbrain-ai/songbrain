# Changelog

All notable changes to the Songbrain SDKs in this repository. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and both packages use [Semantic Versioning](https://semver.org/).

The Python package (`songbrain` on PyPI, tags `py-v*`) and the npm package (`songbrain` on npm, tags `js-v*`) are released together when they share a version. Changes to the API itself are in the [API changelog](https://www.songbrain.ai/docs/api/changelog).

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
