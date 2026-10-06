"""Shared helpers for the cookbook recipes.

Kept in one small file so every recipe stays short. Copy it next to a recipe
if you lift that recipe into your own project.

- add_song_args() / load_song(): where the analysis comes from
  (--example, --test, --song, --audio-url).
- clip_scenes(): the shot plan's clip as a list of timed scenes.
- build_ffmpeg(): one ffmpeg command that cuts video or image segments to
  exact lengths, scales/crops them to the clip's aspect ratio, concatenates
  them and lays the song audio (trimmed to the clip window) underneath.
"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional, Sequence, Tuple

import requests

from songbrain import Songbrain

SIZES = {"9:16": (1080, 1920), "16:9": (1920, 1080), "1:1": (1080, 1080), "4:5": (1080, 1350)}


# ── where the song comes from ─────────────────────────────────────────────────


def add_song_args(parser: argparse.ArgumentParser) -> None:
    src = parser.add_mutually_exclusive_group(required=True)
    src.add_argument("--example", metavar="ID", help="use a public example analysis, no key needed (e.g. sugar-rush)")
    src.add_argument("--test", action="store_true", help="test mode: free, needs SONGBRAIN_API_KEY, no audio")
    src.add_argument("--song", metavar="PATH", help="analyse a local audio file (needs SONGBRAIN_API_KEY)")
    src.add_argument("--audio-url", metavar="URL", help="analyse a public audio URL (needs SONGBRAIN_API_KEY)")
    parser.add_argument("--audio", metavar="PATH", help="audio for the final video (defaults to --song)")


def load_song(args: argparse.Namespace) -> Dict[str, Any]:
    """Return a full song document (schema songbrain.song/1)."""
    sb = Songbrain()  # SONGBRAIN_API_KEY from the environment; examples work without it
    if args.example:
        return dict(sb.example(args.example))
    if args.test:
        # Free and done right away: the Sugar Rush analysis with livemode = false.
        return dict(sb.analyze(test=True, title="cookbook test"))
    if args.song:
        print(f"Analysing {args.song} (60-90 s) …", file=sys.stderr)
        return dict(sb.analyze(args.song))
    print(f"Analysing {args.audio_url} (60-90 s) …", file=sys.stderr)
    return dict(sb.analyze(audio_url=args.audio_url))


def audio_path(args: argparse.Namespace) -> Optional[str]:
    return args.audio or args.song or None


# ── the shot plan as timed scenes ────────────────────────────────────────────


def clip_scenes(song: Dict[str, Any]) -> Tuple[float, float, str, List[Dict[str, Any]]]:
    """Return (window_start, window_end, aspect_ratio, scenes).

    Every scene gets `cut_sec` (its start inside the clip) and `length_sec`
    (until the next scene starts, or the window ends). Using start times instead
    of each scene's own duration keeps the cuts exactly on the planned beats.
    """
    plan = song.get("shot_plan") or {}
    if plan.get("status") != "ready":
        raise SystemExit(f"Shot plan is not ready: {plan.get('status')} {plan.get('reason', '')}")
    clip = plan["clip"]
    w0, w1 = float(clip["window_sec"][0]), float(clip["window_sec"][1])
    scenes = sorted(clip["scenes"], key=lambda s: s["start_sec"])
    out = []
    for i, s in enumerate(scenes):
        start = float(s["start_sec"]) - w0
        end = (float(scenes[i + 1]["start_sec"]) - w0) if i + 1 < len(scenes) else (w1 - w0)
        out.append({**s, "cut_sec": round(start, 3), "length_sec": round(max(0.05, end - start), 3)})
    return w0, w1, clip.get("aspect_ratio") or "9:16", out


def prompt_of(scene: Dict[str, Any]) -> str:
    """The ready prompt (world, palette, style tail included); falls back to the readable visual."""
    return scene.get("prompt") or scene.get("visual") or scene.get("story_beat") or "cinematic shot"


def size_for(aspect_ratio: str) -> Tuple[int, int]:
    return SIZES.get(aspect_ratio, SIZES["9:16"])


# ── ffmpeg ───────────────────────────────────────────────────────────────────


def find_ffmpeg(explicit: Optional[str] = None) -> Optional[str]:
    return explicit or os.environ.get("FFMPEG") or shutil.which("ffmpeg")


def build_ffmpeg(
    segments: Sequence[Tuple[str, float]],
    out: str,
    *,
    size: Tuple[int, int],
    audio: Optional[str] = None,
    audio_start: float = 0.0,
    still: bool = False,
    fps: int = 30,
    ffmpeg: str = "ffmpeg",
) -> List[str]:
    """One ffmpeg command for a list of (file, seconds) segments.

    Each segment is held/padded to its length, cut to exactly that length,
    scaled to cover the frame and centre-cropped. With `still=True` the inputs
    are images that are looped. The audio (if any) starts at `audio_start`
    seconds and runs for the total length, with short fades.
    """
    w, h = size
    total = round(sum(d for _, d in segments), 3)
    cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for path, dur in segments:
        if still:
            cmd += ["-loop", "1", "-t", f"{dur + 0.1:.3f}"]
        cmd += ["-i", path]
    chains = []
    for i, (_, dur) in enumerate(segments):
        chains.append(
            f"[{i}:v]tpad=stop_mode=clone:stop_duration={dur:.3f},trim=duration={dur:.3f},setpts=PTS-STARTPTS,"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},fps={fps},setsar=1,format=yuv420p[v{i}]"
        )
    joined = "".join(f"[v{i}]" for i in range(len(segments)))
    chains.append(f"{joined}concat=n={len(segments)}:v=1:a=0[v]")
    maps = ["-map", "[v]"]
    if audio:
        cmd += ["-ss", f"{audio_start:.3f}", "-t", f"{total:.3f}", "-i", audio]
        fade = min(0.4, total / 4)
        chains.append(f"[{len(segments)}:a]afade=t=in:d=0.05,afade=t=out:st={total - fade:.3f}:d={fade:.3f}[a]")
        maps += ["-map", "[a]", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-filter_complex", ";".join(chains), *maps]
    cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-t", f"{total:.3f}", "-movflags", "+faststart", out]
    return cmd


def show(cmd: Sequence[str]) -> str:
    return " ".join(shlex.quote(c) for c in cmd)


def run(cmd: Sequence[str]) -> None:
    subprocess.run(list(cmd), check=True)


def download(url: str, path: str) -> None:
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        tmp = path + ".part"
        with open(tmp, "wb") as fh:
            for chunk in r.iter_content(1 << 16):
                fh.write(chunk)
        os.replace(tmp, path)
