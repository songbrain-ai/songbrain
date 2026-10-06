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
| `analyze(file=None, *, audio_url=None, title=None, artist=None, webhook_url=None, external_ref=None, filename=None, wait=True, poll_interval=5, timeout=300)` | `POST /songs`, then polls `GET /songs/{id}` | yes |
| `wait_for(song_id, *, poll_interval=5, timeout=300)` | polls `GET /songs/{id}` | yes |
| `get_song(id, view=None, include=None)` | `GET /songs/{id}` | yes |
| `shot_plan(id)` | `GET /songs/{id}/shot-plan` | yes |
| `list_songs(limit=20)` | `GET /songs` | yes |
| `delete_song(id)` | `DELETE /songs/{id}` | yes |
| `account()` | `GET /account` | yes |
| `pricing()` | `GET /pricing` | no |
| `examples()` | `GET /examples` | no |
| `example(id, view=None, include=None)` | `GET /examples/{id}` | no |
| `example_shot_plan(id)` | `GET /examples/{id}/shot-plan` | no |

- `file` can be a path, `bytes` or an open binary file. MP3, WAV, FLAC, M4A, AAC, OGG or AIFF, up to 100 MB, 30 s to 10 min. The file name's extension has to match the audio; for bytes without a name the client detects the format or you pass `filename="song.mp3"`.
- `wait=False` returns the 202 body right away: `{"id", "status": "processing", "eta_sec", "billing"}`. Use `wait_for(id)` or a webhook later.
- `view="summary"` drops word timings and beat arrays (about 3x smaller). `include=["song_dna", "shot_plan"]` returns only those sections.

```python
sb = Songbrain(api_key="sb_live_…", timeout=60, max_retries=3)
```

## Errors

API errors raise `SongbrainError` with `.status`, `.code` and `.message`. Subclasses:

| Exception | When |
|---|---|
| `AuthenticationError` | 401 `missing_api_key`, `invalid_api_key` |
| `InsufficientCredits` | 402: free songs used up and fewer than 25 credits |
| `NotFound` | 404: unknown id, or not yours |
| `RateLimited` | 429, with `.retry_after` in seconds |
| `AnalysisFailed` | the song was accepted but failed (credits are refunded) |
| `WaitTimeout` | `analyze(wait=True)` gave up; the song keeps processing |

The client retries 429 and 5xx responses up to 3 times with backoff and honours `Retry-After` (up to 60 s). Uploads are only retried when nothing can have been created (429, 502, 503).

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

Pass `webhook_url` and Songbrain POSTs `song.done` or `song.failed` (and `account.low_balance`). Verify the `Songbrain-Signature` header against the raw body:

```python
from songbrain import webhooks

ok = webhooks.verify(raw_body, request.headers["Songbrain-Signature"], secret)  # bool
event = webhooks.construct_event(raw_body, header, secret)  # verified dict, or raises
```

The default tolerance is 300 s. A full Flask receiver is in [examples/python/webhook_server.py](https://github.com/songbrain-ai/songbrain/blob/main/examples/python/webhook_server.py).

## Pricing

5 free songs per account per month. Then 25 credits per song (about $0.50). No subscription. Everything is included: analysis, story and shot plan. Results are yours, also in a paid or white-label product. See [Terms §17](https://www.songbrain.ai/terms#api).

## Links

- API docs: https://www.songbrain.ai/docs/api
- OpenAPI: https://api.songbrain.ai/v1/openapi.json
- MCP server: https://api.songbrain.ai/mcp
- Get a key: https://app.songbrain.ai/developers
- Source: https://github.com/songbrain-ai/songbrain

MIT License.
