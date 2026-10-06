"""Analyse a song and print its shot plan, one scene per line.

    pip install songbrain
    export SONGBRAIN_API_KEY=sb_live_...

    python shot_plan_to_prompts.py song.mp3
    python shot_plan_to_prompts.py https://example.com/song.mp3
    python shot_plan_to_prompts.py --example old-truck-home   # no key needed

Output:

    01:34.8–01:36.2 [setup] wide establishing shot of the empty space: ...
"""

import argparse
import sys

from songbrain import Songbrain, SongbrainError


def timecode(sec: float) -> str:
    minutes, seconds = divmod(sec, 60)
    return f"{int(minutes):02d}:{seconds:04.1f}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Print a Songbrain shot plan as timed prompts.")
    parser.add_argument("source", nargs="?", help="a local audio file or a public http(s) URL")
    parser.add_argument("--example", metavar="ID", help="use a no-key example instead, e.g. old-truck-home")
    parser.add_argument("--full-song", action="store_true", help="print the section-level plan for the whole song")
    args = parser.parse_args()
    if not args.source and not args.example:
        parser.error("pass a file, a URL or --example ID")

    sb = Songbrain()
    try:
        if args.example:
            doc = sb.example_shot_plan(args.example)
        elif args.source.startswith(("http://", "https://")):
            print("Analysing (typically 60-90 s)...", file=sys.stderr)
            doc = sb.analyze(audio_url=args.source)
        else:
            print("Uploading and analysing (typically 60-90 s)...", file=sys.stderr)
            doc = sb.analyze(args.source)
    except SongbrainError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

    plan = doc.get("shot_plan") or {}
    if plan.get("status") != "ready":
        print(f"No shot plan: {plan.get('status')} {plan.get('reason', '')}".strip(), file=sys.stderr)
        return 1

    if args.full_song:
        for row in (plan.get("full_song") or {}).get("sections", []):
            print(f"{timecode(row['start_sec'])}–{timecode(row['end_sec'])} [{row['act']}] "
                  f"cut every {row['cut_every_beats']} beats: {row.get('prompt') or ''}")
        return 0

    for scene in plan["clip"]["scenes"]:
        print(f"{timecode(scene['start_sec'])}–{timecode(scene['end_sec'])} [{scene['act']}] {scene.get('prompt') or ''}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
