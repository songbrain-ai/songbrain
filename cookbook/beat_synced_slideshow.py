"""Cut a folder of images on a song's beat grid with ffmpeg. No AI keys needed.

    pip install "songbrain>=0.2" requests      # plus ffmpeg on PATH (or --ffmpeg)
    # plan only, no key and no ffmpeg needed:
    python cookbook/beat_synced_slideshow.py --example sugar-rush --images ./photos --dry-run
    # render the best-moment clip, cutting on the shot plan's scene cuts:
    python cookbook/beat_synced_slideshow.py --song song.mp3 --images ./photos
    # the whole song, one image per bar:
    python cookbook/beat_synced_slideshow.py --song song.mp3 --images ./photos --window full --cuts downbeats

Cut points (--cuts):
  scenes     the shot plan's scene starts (default; follows the song's build-up and payoff)
  beats      every Nth beat (--every N, default 2)
  downbeats  every Nth bar start (--every N, default 1)
  sections   the start of each section (verse, chorus, …)

Window (--window):
  clip       the shot plan's clip, the song's strongest ~15 s (default)
  full       the whole song

Images are used in name order and repeat if there are fewer images than cuts.
The audio comes from --song or --audio; with --example and no --audio the video is silent.
"""

import argparse
import glob
import os
import sys
from typing import Any, Dict, List, Tuple

from _common import add_song_args, audio_path, build_ffmpeg, clip_scenes, find_ffmpeg, load_song, run, show, size_for

IMAGE_EXT = (".jpg", ".jpeg", ".png", ".webp", ".bmp")


def window_of(song: Dict[str, Any], which: str) -> Tuple[float, float]:
    if which == "full":
        return 0.0, float(song["song"]["duration_sec"])
    clip = song["shot_plan"]["clip"]
    return float(clip["window_sec"][0]), float(clip["window_sec"][1])


def cut_times(song: Dict[str, Any], cuts: str, every: int, w0: float, w1: float) -> List[float]:
    """Absolute cut times in seconds inside [w0, w1), always starting at w0."""
    timeline = song.get("timeline") or {}
    if cuts == "scenes":
        if song.get("shot_plan", {}).get("status") != "ready":
            raise SystemExit("No shot plan for this song; use --cuts beats or downbeats.")
        times = [float(s["start_sec"]) for s in song["shot_plan"]["clip"]["scenes"]]
    elif cuts == "sections":
        times = [float(s["start_sec"]) for s in timeline.get("sections") or []]
    else:
        grid = timeline.get(cuts)
        if not isinstance(grid, list):  # view=summary replaces the arrays with a short string
            raise SystemExit(f"timeline.{cuts} is missing; fetch the song with view='full'.")
        inside = [float(t) for t in grid if w0 - 1e-3 <= float(t) < w1]
        times = inside[:: max(1, every)]
    times = sorted({round(t, 3) for t in times if w0 - 1e-3 <= t < w1})
    if not times or times[0] - w0 > 0.05:
        times.insert(0, w0)  # the first image starts with the window
    return times


def segments_from(times: List[float], w1: float, min_sec: float) -> List[float]:
    """Lengths between cuts; cuts closer than min_sec are merged into the previous segment."""
    lengths: List[float] = []
    edges = times + [w1]
    for a, b in zip(edges, edges[1:]):
        d = b - a
        if lengths and d < min_sec:
            lengths[-1] += d
        else:
            lengths.append(d)
    return [round(d, 3) for d in lengths if d > 0]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    add_song_args(ap)
    ap.add_argument("--images", required=True, help="folder with .jpg/.png/.webp images")
    ap.add_argument("--cuts", choices=["scenes", "beats", "downbeats", "sections"], default="scenes")
    ap.add_argument("--every", type=int, help="cut on every Nth beat or bar (default 2 beats, 1 bar)")
    ap.add_argument("--window", choices=["clip", "full"], default="clip")
    ap.add_argument("--min-sec", type=float, default=0.25, help="shortest shot; closer cuts are merged")
    ap.add_argument("--aspect", help="override the aspect ratio, e.g. 16:9 (default: the shot plan's, else 9:16)")
    ap.add_argument("--out", default="songbrain_slideshow.mp4")
    ap.add_argument("--ffmpeg", help="path to ffmpeg (default: $FFMPEG or ffmpeg on PATH)")
    ap.add_argument("--dry-run", action="store_true", help="print the cut list and the ffmpeg command only")
    args = ap.parse_args()

    images = sorted(p for p in glob.glob(os.path.join(args.images, "*")) if p.lower().endswith(IMAGE_EXT))
    if not images:
        raise SystemExit(f"No images in {args.images}")

    song = load_song(args)
    if args.cuts == "scenes" and args.window == "full":
        raise SystemExit("--cuts scenes only covers the clip; use --window clip, or beats/downbeats/sections.")
    w0, w1 = window_of(song, args.window)
    every = args.every or (2 if args.cuts == "beats" else 1)
    times = cut_times(song, args.cuts, every, w0, w1)
    lengths = segments_from(times, w1, args.min_sec)
    aspect = args.aspect or (clip_scenes(song)[2] if song.get("shot_plan", {}).get("status") == "ready" else "9:16")

    segments = [(images[i % len(images)], d) for i, d in enumerate(lengths)]
    title = (song.get("song") or {}).get("title")
    print(f"{title}: {w0:.2f}-{w1:.2f} s, {len(segments)} shots on {args.cuts}, {len(images)} images, {aspect}", file=sys.stderr)
    t = w0
    for path, d in segments:
        print(f"  {t:7.2f}s  +{d:5.2f}s  {os.path.basename(path)}", file=sys.stderr)
        t += d

    ffmpeg = find_ffmpeg(args.ffmpeg)
    cmd = build_ffmpeg(
        segments,
        args.out,
        size=size_for(aspect),
        audio=audio_path(args),
        audio_start=w0,
        still=True,
        ffmpeg=ffmpeg or "ffmpeg",
    )
    if args.dry_run:
        if not audio_path(args):
            print("# no --audio given: the video will be silent")
        print(show(cmd))
        return
    if not ffmpeg:
        raise SystemExit("ffmpeg not found. Install it or pass --ffmpeg /path/to/ffmpeg.")
    run(cmd)
    print(args.out)


if __name__ == "__main__":
    main()
