# Render a shot plan with your own video model

Songbrain does not render video through the API. It gives you the plan: what to show, when, and with which prompt. You render each scene with the image or video model you already use (Kling, Runway, Luma, Veo, models on fal, or anything else) and cut the clips on the seconds in the plan. The cuts already sit on beats.

This guide stays generic. Each vendor's parameter names change often, so check their docs for the exact request.

## 1. Get the plan

```python
from songbrain import Songbrain

sb = Songbrain()
song = sb.analyze("song.mp3")                      # or sb.example("old-truck-home") to try without a key
plan = song["shot_plan"]
assert plan["status"] == "ready"
clip = plan["clip"]
```

What you use from it:

| Field | Use |
|---|---|
| `clip.window_sec` | `[start, end]` of the clip in the song. Cut the audio to this window. |
| `clip.aspect_ratio` | `"9:16"`. Ask your model for vertical output. |
| `clip.scenes[].start_sec`, `end_sec` | Absolute seconds in the song. Where each shot starts and ends. |
| `clip.scenes[].start_in_clip`, `duration_sec` | The same, relative to the clip. Use these on your editing timeline. |
| `clip.scenes[].prompt` | A ready prompt with world, palette and style. Send it as is. |
| `clip.scenes[].visual` | The same prompt without the style tail, if you add your own style. |
| `clip.scenes[].motion`, `transition_in` | Camera move and how to cut in. Add the motion to video prompts. |
| `clip.scenes[].kind` | `strobe` scenes are about 4 frames. Use a still image for them. |
| `style.prompt_suffix` | Append to any prompt you write yourself to stay in the same look. |
| `full_song.sections[]` | The same idea for a full-length video: `prompt` and `cuts_sec[]` per section. |

## 2. Generate one shot per scene

Most video models produce clips of a fixed length (often 5 or 10 seconds). Scenes are shorter, often 0.5–2 s. So:

1. Generate each clip at the model's shortest length, at least as long as the scene.
2. Trim it to `duration_sec` when you edit.

A common route that keeps the look consistent: generate a still image per scene from `prompt` with an image model, then animate it with an image-to-video model and the `motion` text. Scenes that share the same `role` show the same picture, so you can generate one asset per role and reuse it.

```python
jobs = {}
for scene in clip["scenes"]:
    key = scene["role"]                      # same role = same picture
    if key in jobs:
        continue
    prompt = scene["prompt"]
    if scene["kind"] != "strobe":
        prompt = f"{prompt}. Camera: {scene['motion']}."
    jobs[key] = your_model.generate(          # your vendor's SDK or HTTP call
        prompt=prompt,
        aspect_ratio="9:16",                  # use the parameter name your vendor documents
        duration=5,                           # the shortest length the model offers
    )
```

`your_model.generate` is a placeholder. Replace it with your vendor's call and its documented parameter names.

## 3. Cut on the given seconds

Put each generated clip on the timeline at `start_in_clip` and trim it to `duration_sec`. Then lay the song audio from `window_sec[0]` to `window_sec[1]` under it.

With ffmpeg, per scene (here scene 3 of `old-truck-home`, `duration_sec` 1.226):

```bash
ffmpeg -y -i scene_03.mp4 -t 1.226 -an -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,fps=30" -c:v libx264 -pix_fmt yuv420p part_03.mp4
```

Then join the parts and add the audio window:

```bash
# parts.txt lists the parts in order: file 'part_01.mp4' ...
ffmpeg -y -f concat -safe 0 -i parts.txt -c copy video.mp4
ffmpeg -y -i video.mp4 -ss 94.83 -t 14.79 -i song.mp3 -map 0:v -map 1:a -c:v copy -c:a aac -shortest clip.mp4
```

Here `94.83` is `window_sec[0]` from the example `old-truck-home` and `14.79` is `window_sec[1] - window_sec[0]`. Use your song's values.

Small timing errors add up. Trim by frame count (`round(duration_sec * fps)` frames) rather than by seconds when you need sample-exact cuts, or build the timeline in an editor that accepts absolute times.

## 4. A full-length video

`shot_plan.full_song.sections[]` has one row per section of the song: `start_sec`, `end_sec`, `act`, a `prompt`, how often to cut (`cut_every_beats`) and the cut points (`cuts_sec[]`, on the song's own beats). Generate a few variations per section prompt and cycle them at each cut point. Use `story.element` and `story.story_beats` as the brief so the whole video tells one story.

## Tips

- Keep `style.prompt_suffix` on every prompt you write yourself. It holds the palette and look.
- `scene.sung` is the lyric under the shot. Use it for captions or karaoke.
- `best_moments[]` lists other strong windows. You can cut more than one short from a song.
- Check the license terms of the model you render with. Songbrain's results are yours; see https://www.songbrain.ai/terms#api.
