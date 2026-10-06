"""Song -> shot plan -> one AI video clip per scene on Replicate -> a finished, beat-cut video.

    pip install "songbrain>=0.2" requests
    # see the plan without any keys:
    python cookbook/song_to_clips_replicate.py --example sugar-rush --dry-run
    # render for real (costs Replicate credits; try --max-scenes 2 first):
    export REPLICATE_API_TOKEN=r8_...        # https://replicate.com/account/api-tokens
    export SONGBRAIN_API_KEY=sb_live_...    # not needed for --example
    python cookbook/song_to_clips_replicate.py --song song.mp3 --out video.mp4

The same recipe as song_to_clips_fal.py, on Replicate's HTTP API:
- POST https://api.replicate.com/v1/models/<owner>/<name>/predictions {"input": {...}}
  (or POST /v1/predictions {"version": ..., "input": ...} for "owner/name:version")
- poll the prediction's urls.get until status is "succeeded", then read `output`.

With --mode i2v a still is made first (flux-schnell by default) and passed to
the video model as --image-input (start_image for Kling). Input names differ
between models: --extra '{"key": "value"}' adds or overrides inputs.
"""

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Dict, Optional

import requests

from _common import (
    add_song_args,
    audio_path,
    build_ffmpeg,
    clip_scenes,
    download,
    find_ffmpeg,
    load_song,
    prompt_of,
    run,
    show,
    size_for,
)

API = "https://api.replicate.com/v1"
DEFAULT_VIDEO = "kwaivgi/kling-v1.6-standard"
DEFAULT_IMAGE = "black-forest-labs/flux-schnell"


def prediction_request(model: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    """URL and body for one prediction. "owner/name" uses the model's latest version."""
    if ":" in model:
        return {"url": f"{API}/predictions", "body": {"version": model.split(":", 1)[1], "input": payload}}
    return {"url": f"{API}/models/{model}/predictions", "body": {"input": payload}}


def replicate_run(model: str, payload: Dict[str, Any], token: str, poll_sec: float = 3.0, timeout_sec: float = 900) -> Any:
    """Create a prediction, wait for it and return its output."""
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    req = prediction_request(model, payload)
    r = requests.post(req["url"], json=req["body"], headers=headers, timeout=60)
    r.raise_for_status()
    pred = r.json()
    deadline = time.monotonic() + timeout_sec
    while pred.get("status") not in ("succeeded", "failed", "canceled"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"prediction {pred.get('id')} not done after {timeout_sec:.0f} s")
        time.sleep(poll_sec)
        g = requests.get(pred["urls"]["get"], headers=headers, timeout=60)
        g.raise_for_status()
        pred = g.json()
    if pred["status"] != "succeeded":
        raise RuntimeError(f"prediction {pred.get('id')} {pred['status']}: {pred.get('error')}")
    return pred["output"]


def first_url(output: Any) -> str:
    """Video and image models return a URL or a list of URLs."""
    if isinstance(output, list):
        output = output[0]
    if isinstance(output, dict):  # a few models wrap it
        output = output.get("url") or output.get("video") or next(iter(output.values()))
    return str(output)


def video_payload(
    scene: Dict[str, Any], aspect: str, extra: Dict[str, Any], image_key: str, image_url: Optional[str] = None
) -> Dict[str, Any]:
    # Kling-style inputs. Scenes are 1-3 s; ffmpeg trims every clip to its scene later.
    payload: Dict[str, Any] = {"prompt": prompt_of(scene), "duration": 5, "aspect_ratio": aspect}
    if image_url:
        payload[image_key] = image_url
    payload.update(extra)
    return payload


def image_payload(scene: Dict[str, Any], aspect: str) -> Dict[str, Any]:
    return {"prompt": prompt_of(scene), "aspect_ratio": aspect, "output_format": "png", "num_outputs": 1}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add_song_args(ap)
    ap.add_argument("--mode", choices=["t2v", "i2v"], default="t2v", help="text-to-video, or image first then image-to-video")
    ap.add_argument("--video-model", default=DEFAULT_VIDEO, help="owner/name or owner/name:version")
    ap.add_argument("--image-model", default=DEFAULT_IMAGE, help="image model for --mode i2v")
    ap.add_argument("--image-input", default="start_image", help="the video model's input name for the start image")
    ap.add_argument("--extra", default="{}", help="JSON merged into every video request")
    ap.add_argument("--max-scenes", type=int, help="only the first N scenes (cheap test runs)")
    ap.add_argument("--parallel", type=int, default=4, help="scenes rendered at the same time")
    ap.add_argument("--clips-dir", default="clips", help="where clips are downloaded (re-runs skip existing ones)")
    ap.add_argument("--out", default="songbrain_replicate.mp4")
    ap.add_argument("--ffmpeg", help="path to ffmpeg (default: $FFMPEG or ffmpeg on PATH)")
    ap.add_argument("--dry-run", action="store_true", help="print the planned Replicate calls and the ffmpeg command, call nothing")
    args = ap.parse_args()

    extra = json.loads(args.extra)
    song = load_song(args)
    w0, w1, aspect, scenes = clip_scenes(song)
    if args.max_scenes:
        scenes = scenes[: args.max_scenes]
    title = (song.get("song") or {}).get("title")
    print(f"{title}: clip {w0:.2f}-{w1:.2f} s, {len(scenes)} scenes, {aspect}", file=sys.stderr)

    clip_paths = [os.path.join(args.clips_dir, f"scene_{s['index']:02d}.mp4") for s in scenes]
    segments = [(p, s["length_sec"]) for p, s in zip(clip_paths, scenes)]
    total = sum(d for _, d in segments)
    ffmpeg_cmd = build_ffmpeg(
        segments,
        args.out,
        size=size_for(aspect),
        audio=audio_path(args),
        audio_start=w0,
        ffmpeg=find_ffmpeg(args.ffmpeg) or "ffmpeg",
    )

    if args.dry_run:
        for s, path in zip(scenes, clip_paths):
            print(f"\n# scene {s['index']:02d}  {s['cut_sec']:6.2f}s +{s['length_sec']:.2f}s  [{s['act']}/{s['kind']}]")
            image_url = None
            if args.mode == "i2v":
                req = prediction_request(args.image_model, image_payload(s, aspect))
                print(f"POST {req['url']}")
                print(json.dumps(req["body"], indent=2))
                image_url = "<output[0] of the image prediction>"
            req = prediction_request(args.video_model, video_payload(s, aspect, extra, args.image_input, image_url))
            print(f"POST {req['url']}")
            print(json.dumps(req["body"], indent=2))
            print(f"-> poll urls.get, download output to {path}")
        print(f"\n# stitch ({total:.2f} s)")
        if not audio_path(args):
            print("# no --audio given: the video will be silent")
        print(show(ffmpeg_cmd))
        return

    token = os.environ.get("REPLICATE_API_TOKEN")
    if not token:
        raise SystemExit("Set REPLICATE_API_TOKEN (https://replicate.com/account/api-tokens), or use --dry-run.")
    ffmpeg = find_ffmpeg(args.ffmpeg)
    if not ffmpeg:
        raise SystemExit("ffmpeg not found. Install it or pass --ffmpeg /path/to/ffmpeg.")
    os.makedirs(args.clips_dir, exist_ok=True)

    def render(item: Any) -> str:
        scene, path = item
        if os.path.exists(path):
            return f"scene {scene['index']:02d}: kept {path}"
        image_url = None
        if args.mode == "i2v":
            image_url = first_url(replicate_run(args.image_model, image_payload(scene, aspect), token))
        output = replicate_run(args.video_model, video_payload(scene, aspect, extra, args.image_input, image_url), token)
        download(first_url(output), path)
        return f"scene {scene['index']:02d}: {path}"

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        for line in pool.map(render, zip(scenes, clip_paths)):
            print(line, file=sys.stderr)

    ffmpeg_cmd[0] = ffmpeg
    run(ffmpeg_cmd)
    print(args.out)


if __name__ == "__main__":
    main()
