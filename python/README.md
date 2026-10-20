# songbrain

**Song in, video plan out.** The official Python client for the [Songbrain API](https://www.songbrain.ai/docs/api), the music analysis API for AI video.

One call returns the song DNA (genre, tempo, key, mood, instruments, loudness), a beat grid, sections, the best moments with reasons, word-timed lyrics, the story, world and palette, and a beat-synced shot plan with a ready prompt for every scene.

```bash
pip install songbrain
```

Python 3.9+. One dependency: `requests`.

## Quickstart

Get a key at [app.songbrain.ai/developers](https://app.songbrain.ai/developers). 5 songs a month are free.

```python
from songbrain import Songbrain

sb = Songbrain()  # reads SONGBRAIN_API_KEY

song = sb.analyze("song.mp3")  # or analyze(audio_url="https://…/song.mp3")

print(song["song_dna"]["genre"], song["song_dna"]["tempo_bpm"], song["song_dna"]["key"])
for scene in song["shot_plan"]["clip"]["scenes"]:
    print(f'{scene["start_sec"]:.2f}-{scene["end_sec"]:.2f} [{scene["act"]}] {scene["prompt"]}')
```

`analyze()` uploads the song, waits until the analysis is done (typically 60–90 s) and returns the full document.

## Two modes

Every song is analysed in one of two modes. Use `dna` when you only need the data, or to sort many songs first. Then add the video direction to the ones you pick. `dna` plus the direction costs the same as `full`.

| Mode | What you get | Price |
|---|---|---|
| `dna` | Song DNA: `song_dna`, `timeline`, `best_moments`, `lyrics`, `scores`. No story, no shot plan | 10 credits, about $0.20 |
| `full` (default) | Song DNA + video direction: `story` and a beat-synced `shot_plan` with a prompt per scene | 25 credits, about $0.50 |
| Add direction later | `story` + `shot_plan` for a finished `dna` song. No new upload | 15 credits, about $0.30 |

```python
song = sb.analyze("song.mp3", mode="dna")       # 10 credits: no story, no shot plan
if song["scores"]["virality"]["score"] >= 80:
    song = sb.add_direction(song["id"])         # +15 credits, waits about 30-40 s
    print(song["shot_plan"]["clip"]["scenes"][0]["prompt"])
```

The 5 free songs a month cover either mode. Adding the direction never uses a free song. If it fails, the 15 credits are refunded and the song stays `dna`. `GET /v1/songs/{id}/shot-plan` on a `dna` song answers 409 `no_direction`.

`add_direction(id, wait=False)` returns the 202 body right away. `sb.example("sugar-rush", mode="dna")` shows a `dna` document without a key.

## Try it without a key

The example endpoints return real analyses of Songbrain's own songs, in exactly the format your songs get.

```python
from songbrain import Songbrain

sb = Songbrain()
print([e["id"] for e in sb.examples()["data"]])
plan = sb.example_shot_plan("old-truck-home")
print(plan["shot_plan"]["clip"]["scenes"][0]["prompt"])
```

## Methods

Every method returns the JSON body of the response as a `dict`. Types for editors live in `songbrain.types` (`Song`, `SongDNA`, `Timeline`, `BestMoment`, `Lyrics`, `Scores`, `Story`, `ShotPlan`, `Scene`, …).

| Method | API call | Key |
|---|---|---|
| `analyze(file=None, *, audio_url=None, title=None, artist=None, webhook_url=None, external_ref=None, filename=None, lyrics=None, mode=None, test=False, idempotency_key=None, wait=True, poll_interval=5, timeout=300)` | `POST /songs`, then polls `GET /songs/{id}` | yes |
| `add_direction(song_id, *, wait=True, poll_interval=5, timeout=300)` | `POST /songs/{id}/direction`, then polls `GET /songs/{id}` | yes |
| `wait_for(song_id, *, poll_interval=5, timeout=300)` | polls `GET /songs/{id}` | yes |
| `get_song(id, view=None, include=None)` | `GET /songs/{id}` | yes |
| `shot_plan(id)` | `GET /songs/{id}/shot-plan` | yes |
| `list_songs(limit=20, starting_after=None)` | `GET /songs` (one page) | yes |
| `iter_songs(page_size=100, starting_after=None)` | `GET /songs`, all pages | yes |
| `delete_song(id)` | `DELETE /songs/{id}` | yes |
| `account()` | `GET /account` | yes |
| `test_webhook(url)` | `POST /webhooks/test` | yes |
| `webhook_deliveries(limit=20)` | `GET /webhooks/deliveries` | yes |
| `pricing()` | `GET /pricing` | no |
| `examples()` | `GET /examples` | no |
| `example(id, view=None, include=None, mode=None)` | `GET /examples/{id}` | no |
| `example_shot_plan(id)` | `GET /examples/{id}/shot-plan` | no |

- `file` can be a path, `bytes` or an open binary file. MP3, WAV, FLAC, M4A, AAC, OGG or AIFF, up to 100 MB, 30 s to 10 min. The file name's extension has to match the audio; for bytes without a name the client detects the format or you pass `filename="song.mp3"`.
- `wait=False` returns the 202 body right away: `{"id", "status": "processing", "eta_sec", "billing"}`. Use `wait_for(id)` or a webhook later.
- `view="summary"` drops word timings and beat arrays (about 3x smaller). `include=["song_dna", "shot_plan"]` returns only those sections.

```python
sb = Songbrain(api_key="sb_live_…", timeout=60, max_retries=3)
```

## Test mode

`analyze(test=True)` is free, needs no audio and is done right away. It returns the Sugar Rush example analysis with your `title` and `external_ref`, `"livemode": False` and `billing.type == "test"`. A `webhook_url` still gets a signed `song.done`. Use it in CI:

```python
song = sb.analyze(test=True, title="CI smoke test", external_ref="build-123")
assert song["status"] == "done" and song["livemode"] is False
```

## Idempotency

Every `analyze()` sends an `Idempotency-Key` (a uuid4) and reuses it when the client retries. So network errors, 5xx and 429 are retried for uploads too, and a retry never creates or charges a second song. Pass your own key to make retries across processes safe (same key within 24 h = same song):

```python
sb.analyze(audio_url=url, idempotency_key=f"order-{order_id}", wait=False)
```

The same key with a different request raises a 409 `idempotency_key_reused`.

## Pagination

```python
page = sb.list_songs(limit=50)                       # {"data", "has_more", "next_cursor"}
page = sb.list_songs(limit=50, starting_after=page["next_cursor"])

for item in sb.iter_songs():                         # all songs, newest first
    print(item["id"], item["status"], item["livemode"])
```

## Rate limits and request ids

```python
sb.account()
print(sb.last_rate_limit)   # {"limit": 120, "remaining": 119, "reset": 0}
print(sb.last_request_id)   # "req_…"
```

## User-Agent and coding agents

The SDK sends `User-Agent: songbrain-python/<version>`. When it runs inside a coding agent's shell (Claude Code, Cursor, Gemini CLI, Codex, opencode, Augment), it appends the agent's name, for example `songbrain-python/0.4.0 (agent: claude-code)`. The name comes from environment variables those tools set themselves (`AI_AGENT`, `CLAUDECODE`, `CURSOR_AGENT` …). Nothing else from your environment is sent. It tells us which agents developers build with. Set `SONGBRAIN_NO_AGENT_HINT=1` to turn it off.

## Errors

API errors raise `SongbrainError` with `.status`, `.code`, `.message` and `.request_id` (`req_…`, also in `str(error)`; quote it when you write to support). Subclasses:

| Exception | When |
|---|---|
| `AuthenticationError` | 401 `missing_api_key`, `invalid_api_key` |
| `InsufficientCredits` | 402: free songs used up and too few credits (25 for `full`, 10 for `dna`, 15 to add the direction) |
| `NotFound` | 404: unknown id, or not yours |
| `RateLimited` | 429, with `.retry_after` in seconds |
| `AnalysisFailed` | the song was accepted but failed (credits are refunded); code `direction_failed` from `add_direction` |
| `WaitTimeout` | `analyze(wait=True)` gave up; the song keeps processing |

The client retries network errors, 429 and 5xx responses up to 3 times with backoff and honours `Retry-After` (up to 60 s). Song creation is retried too, because it carries an `Idempotency-Key`.

```python
from songbrain import Songbrain, InsufficientCredits, RateLimited

try:
    song = Songbrain().analyze(audio_url="https://example.com/song.mp3")
except InsufficientCredits:
    print("Top up at https://app.songbrain.ai/developers/billing")
except RateLimited as e:
    print("Try again in", e.retry_after, "s")
```

## Webhooks

Pass `webhook_url` and Songbrain POSTs `song.done` or `song.failed` (and `account.low_balance`). `data.mode` says `full` or `dna`. After `add_direction` a second `song.done` arrives with its own event id and `data.direction_added: True`. Verify the `Songbrain-Signature` header against the raw body:

```python
from songbrain import webhooks

ok = webhooks.verify(raw_body, request.headers["Songbrain-Signature"], secret)  # bool
event = webhooks.construct_event(raw_body, header, secret)  # verified dict, or raises
```

The default tolerance is 300 s.

Every event has an `id` (`evt_…`) that stays the same when Songbrain retries it (up to 10 attempts over about 3 days). Store the ids you have handled and skip repeats. Check your receiver with a signed `ping`:

```python
sb.test_webhook("https://example.com/songbrain")   # {"delivered", "status_code", "latency_ms", "event_id"}
sb.webhook_deliveries(limit=20)                    # the last delivery attempts
```

A full FastAPI receiver with dedupe is in [cookbook/webhook_receiver_fastapi.py](https://github.com/songbrain-ai/songbrain/blob/main/cookbook/webhook_receiver_fastapi.py), a Flask one in [examples/python/webhook_server.py](https://github.com/songbrain-ai/songbrain/blob/main/examples/python/webhook_server.py).

## Prompts for video models

`best_moments` ranks the strongest windows of the song with the reason each one works. `shot_plan.clip` turns the top moment into a beat-cut edit of about 15 seconds, and every scene carries a ready prompt for an image or video model (Kling, Runway, Luma, Veo, fal, Replicate), written from one story, world and palette so the scenes belong together. `shot_plan.full_song` gives the cut points for a complete video.

## Coming from Spotify Audio Features?

New Spotify apps have had no access to `/audio-features` and `/audio-analysis` since November 27, 2024. `song_dna` carries tempo (`tempo_bpm`), key, energy and loudness (LUFS), `timeline` carries every beat, downbeat and section, for any audio file. Field-by-field mapping and a migration example: https://www.songbrain.ai/guides/spotify-audio-features-alternative

## Pricing

5 free songs per account per month, in either mode. Then 25 credits per `full` song (about $0.50) or 10 per `dna` song (about $0.20); adding the direction later costs 15 credits (about $0.30). No subscription. A `full` song includes everything: analysis, story and shot plan. Results are yours, also in a paid or white-label product. See [Terms §17](https://www.songbrain.ai/terms#api).

## Links

- API docs: https://www.songbrain.ai/docs/api
- OpenAPI: https://api.songbrain.ai/v1/openapi.json
- MCP server: https://api.songbrain.ai/v1/mcp
- Get a key: https://app.songbrain.ai/developers
- Source: https://github.com/songbrain-ai/songbrain

MIT License.
