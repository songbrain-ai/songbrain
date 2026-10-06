"""Song -> shot plan -> one AI video clip per scene on fal.ai -> a finished, beat-cut video.

    pip install "songbrain>=0.2" requests
    # see the plan without any keys:
    python cookbook/song_to_clips_fal.py --example sugar-rush --dry-run
    # render for real (costs fal credits; try --max-scenes 2 first):
    export FAL_KEY=...                      # https://fal.ai/dashboard/keys
    export SONGBRAIN_API_KEY=sb_live_...    # not needed for --example
    python cookbook/song_to_clips_fal.py --song song.mp3 --out video.mp4

What it does:
1. Gets the analysis (an example, a free test song, or your own song).
2. Takes shot_plan.clip.scenes: every scene has absolute start/end seconds on
   the beat and a ready prompt (world, palette, framing, "9:16, no text").
3. Sends every prompt to a fal.ai video model through fal's queue REST API:
   POST https://queue.fal.run/<model>, then polls status_url and reads response_url.
   With --mode i2v it first makes a still with an image model and animates it.
4. Downloads the clips and lets ffmpeg cut each one to the time until the next
   scene starts, crop to the clip's aspect ratio and put the song audio
   (trimmed to the clip window) underneath.

Models change often. Pass any fal model id with --video-model / --image-model;
--extra '{"key": "value"}' adds model-specific inputs.
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

FAL_QUEUE = "https://queue.fal.run"
DEFAULT_T2V = "fal-ai/kling-video/v1.6/standard/text-to-video"
DEFAULT_I2V = "fal-ai/kling-video/v1.6/standard/image-to-video"
DEFAULT_IMAGE = "fal-ai/flux/schnell"
FAL_IMAGE_SIZES = {"9:16": "portrait_16_9", "16:9": "landscape_16_9", "1:1": "square_hd", "4:5": "portrait_4_3"}


def fal_run(model: str, payload: Dict[str, Any], key: str, poll_sec: float = 3.0, timeout_sec: float = 900) -> Dict[str, Any]:
    """Submit to fal's queue and wait for the result."""
    headers = {"Authorization": f"Key {key}", "Content-Type": "application/json"}
    r = requests.post(f"{FAL_QUEUE}/{model}", json=payload, headers=headers, timeout=60)
    r.raise_for_status()
    job = r.json()
    # Use the URLs fal returns: for nested model ids they point at the app root.
    status_url, response_url = job["status_url"], job["response_url"]
    deadline = time.monotonic() + timeout_sec
    while True:
        s = requests.get(status_url, headers=headers, timeout=60)
        s.raise_for_status()
        status = s.json().get("status")
        if status == "COMPLETED":
            break
        if status not in ("IN_QUEUE", "IN_PROGRESS"):
            raise RuntimeError(f"fal job {job.get('request_id')} ended with status {status}: {s.text[:300]}")
        if time.monotonic() > deadline:
            raise TimeoutError(f"fal job {job.get('request_id')} not done after {timeout_sec:.0f} s")
        time.sleep(poll_sec)
    res = requests.get(response_url, headers=headers, timeout=60)
    res.raise_for_status()
    return res.json()


def video_payload(scene: Dict[str, Any], aspect: str, extra: Dict[str, Any], image_url: Optional[str] = None) -> Dict[str, Any]:
    # Kling-style inputs. Scenes are 1-3 s, so the shortest clip length is plenty;
    # ffmpeg trims every clip to its scene later.
    payload: Dict[str, Any] = {"prompt": prompt_of(scene), "duration": "5", "aspect_ratio": aspect}
    if image_url:
        payload["image_url"] = image_url
    payload.update(extra)
    return payload


def image_payload(scene: Dict[str, Any], aspect: str) -> Dict[str, Any]:
    return {"prompt": prompt_of(scene), "image_size": FAL_IMAGE_SIZES.get(aspect, "portrait_16_9"), "num_images": 1}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add_song_args(ap)
    ap.add_argument("--mode", choices=["t2v", "i2v"], default="t2v", help="text-to-video, or image first then image-to-video")
    ap.add_argument("--video-model", help=f"fal model id (default {DEFAULT_T2V}, or {DEFAULT_I2V} with --mode i2v)")
    ap.add_argument("--image-model", default=DEFAULT_IMAGE, help="fal image model for --mode i2v")
    ap.add_argument("--extra", default="{}", help="JSON merged into every video request")
    ap.add_argument("--max-scenes", type=int, help="only the first N scenes (cheap test runs)")
    ap.add_argument("--parallel", type=int, default=4, help="scenes rendered at the same time")
    ap.add_argument("--clips-dir", default="clips", help="where clips are downloaded (re-runs skip existing ones)")
    ap.add_argument("--out", default="songbrain_fal.mp4")
    ap.add_argument("--ffmpeg", help="path to ffmpeg (default: $FFMPEG or ffmpeg on PATH)")
    ap.add_argument("--dry-run", action="store_true", help="print the planned fal calls and the ffmpeg command, call nothing")
    args = ap.parse_args()

    video_model = args.video_model or (DEFAULT_I2V if args.mode == "i2v" else DEFAULT_T2V)
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
            if args.mode == "i2v":
                print(f"POST {FAL_QUEUE}/{args.image_model}")
                print(json.dumps(image_payload(s, aspect), indent=2))
                print(f"POST {FAL_QUEUE}/{video_model}")
                print(json.dumps(video_payload(s, aspect, extra, image_url="<images[0].url from the image job>"), indent=2))
            else:
                print(f"POST {FAL_QUEUE}/{video_model}")
                print(json.dumps(video_payload(s, aspect, extra), indent=2))
            print(f"-> download video.url to {path}")
        print(f"\n# stitch ({total:.2f} s)")
        if not audio_path(args):
            print("# no --audio given: the video will be silent")
        print(show(ffmpeg_cmd))
        return

    key = os.environ.get("FAL_KEY")
    if not key:
        raise SystemExit("Set FAL_KEY (https://fal.ai/dashboard/keys), or use --dry-run.")
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
            image_url = fal_run(args.image_model, image_payload(scene, aspect), key)["images"][0]["url"]
        result = fal_run(video_model, video_payload(scene, aspect, extra, image_url), key)
        download(result["video"]["url"], path)
        return f"scene {scene['index']:02d}: {path}"

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        for line in pool.map(render, zip(scenes, clip_paths)):
            print(line, file=sys.stderr)

    ffmpeg_cmd[0] = ffmpeg
    run(ffmpeg_cmd)
    print(args.out)


if __name__ == "__main__":
    main()
