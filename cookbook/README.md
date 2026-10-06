# Cookbook

Runnable recipes that turn a Songbrain analysis into something finished. Every recipe works with `--example sugar-rush` (a public example, no key), and the video recipes have a `--dry-run` that prints every planned call and the exact ffmpeg command without any keys.

```bash
pip install -r cookbook/requirements.txt     # songbrain, requests (+ fastapi/uvicorn for the webhook recipe)
# ffmpeg on PATH for the video recipes (or pass --ffmpeg /path/to/ffmpeg)
```

Where the song comes from (all video recipes):

| Flag | Needs | What you get |
|---|---|---|
| `--example sugar-rush` | nothing | a real analysis of one of Songbrain's own songs (`GET /v1/examples`) |
| `--test` | `SONGBRAIN_API_KEY` | a free test song (`livemode: false`), done right away |
| `--song song.mp3` | `SONGBRAIN_API_KEY` | your song, analysed (60-90 s); its audio is used for the video |
| `--audio-url https://…` | `SONGBRAIN_API_KEY` | the same from a public URL; pass `--audio` for the soundtrack |

`--audio PATH` sets the soundtrack for any source. Without audio the video is silent.

Shared code (song loading, scene timing, the ffmpeg command) is in [`_common.py`](_common.py). Copy it along if you lift a recipe into your project.

## song_to_clips_fal.py

Analysis → one AI clip per shot-plan scene on [fal.ai](https://fal.ai) → a finished 9:16 video cut on the beat, with the song underneath.

```bash
python cookbook/song_to_clips_fal.py --example sugar-rush --dry-run
FAL_KEY=… python cookbook/song_to_clips_fal.py --song song.mp3 --max-scenes 3   # cheap first run
FAL_KEY=… python cookbook/song_to_clips_fal.py --song song.mp3 --mode i2v       # image first, then animate
```

- Uses fal's queue REST API (`POST https://queue.fal.run/<model>`, poll `status_url`, read `response_url`). No fal SDK needed.
- Default models: Kling 1.6 text-to-video, or flux-schnell + Kling image-to-video with `--mode i2v`. Any fal model id works with `--video-model` / `--image-model`; `--extra '{"seed": 7}'` adds inputs.
- Each scene's prompt already carries the world, palette, framing and "9:16, no text". Each clip is cut to the time until the next scene starts, so cuts land on the planned beats.
- Clips are saved in `--clips-dir` and reused on re-runs, so a failed scene does not re-bill the others.

## song_to_clips_replicate.py

The same on [Replicate](https://replicate.com) (`REPLICATE_API_TOKEN`).

```bash
python cookbook/song_to_clips_replicate.py --example sugar-rush --dry-run
REPLICATE_API_TOKEN=… python cookbook/song_to_clips_replicate.py --song song.mp3 --max-scenes 3
```

- `POST /v1/models/<owner>/<name>/predictions`, then polls `urls.get`. Pin a version with `owner/name:version`.
- Default: `kwaivgi/kling-v1.6-standard`; `--mode i2v` makes a still with `black-forest-labs/flux-schnell` first and passes it as `--image-input` (`start_image`).

## beat_synced_slideshow.py

No AI at all: cut a folder of photos (artwork, tour pictures, frames) on the song's grid.

```bash
python cookbook/beat_synced_slideshow.py --example sugar-rush --images ./photos --dry-run
python cookbook/beat_synced_slideshow.py --song song.mp3 --images ./photos                       # best ~15 s, scene cuts
python cookbook/beat_synced_slideshow.py --song song.mp3 --images ./photos --cuts beats --every 2
python cookbook/beat_synced_slideshow.py --song song.mp3 --images ./photos --window full --cuts downbeats
```

- `--cuts scenes | beats | downbeats | sections`, `--every N`, `--window clip | full`, `--aspect 16:9`.
- Images are used in name order and repeat when there are more cuts than images.

## webhook_receiver_fastapi.py

A receiver that gets the details right: verifies the signature on the raw body, dedupes on the event `id`, answers 2xx fast and does slow work in the background, handles `ping`, `song.done`, `song.failed` and `account.low_balance`.

```bash
export SONGBRAIN_WEBHOOK_SECRET=…
cd cookbook && uvicorn webhook_receiver_fastapi:app --port 8080
python cookbook/webhook_receiver_fastapi.py --self-test      # signs events locally, checks dedupe
```

Songbrain retries a failed delivery up to 10 times over about 3 days (immediately, then +1 min, +5 min, +30 min, +2 h, +6 h, +12 h, +24 h, +48 h, +72 h), always with the same event id. Send a signed `ping` to your public URL with `Songbrain().test_webhook(url)` and look at past attempts with `webhook_deliveries()`.

## ci_test_mode.py

pytest tests for CI that use test mode: free, no audio, done right away, `livemode: false`. They check the fields you read, idempotency, request ids and rate-limit headers, plus a signed webhook event checked offline.

```bash
SONGBRAIN_API_KEY=… pytest cookbook/ci_test_mode.py -v
```

Without a key, the API tests are skipped and the webhook test still runs.
