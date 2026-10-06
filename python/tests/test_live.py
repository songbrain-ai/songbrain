"""Live tests against the public, no-key example endpoints.

Skip them offline with ``pytest -m "not live"`` or ``SONGBRAIN_OFFLINE=1``.
"""

import pytest

from songbrain import NotFound, Songbrain

pytestmark = pytest.mark.live

EXAMPLE = "old-truck-home"


@pytest.fixture(scope="module")
def sb():
    with Songbrain(api_key="") as client:  # examples need no key
        yield client


def test_examples_list(sb):
    out = sb.examples()
    assert out["object"] == "list"
    assert EXAMPLE in [e["id"] for e in out["data"]]


def test_example_full_document(sb):
    doc = sb.example(EXAMPLE)
    assert doc["object"] == "song"
    assert doc["schema"] == "songbrain.song/1"
    assert doc["status"] == "done"
    assert doc["song_dna"]["tempo_bpm"] > 0
    assert isinstance(doc["timeline"]["beats"], list) and doc["timeline"]["beats"]
    assert doc["best_moments"][0]["rank"] == 1
    assert doc["lyrics"]["lines"][0]["words"]
    assert 0 <= doc["scores"]["virality"]["score"] <= 100
    assert doc["story"]["story_beats"]["setup"]
    scenes = doc["shot_plan"]["clip"]["scenes"]
    assert scenes and all(s["end_sec"] > s["start_sec"] for s in scenes)


def test_example_summary_and_include(sb):
    doc = sb.example(EXAMPLE, view="summary", include=["song_dna", "shot_plan"])
    assert "song_dna" in doc and "shot_plan" in doc
    assert "lyrics" not in doc


def test_example_shot_plan(sb):
    out = sb.example_shot_plan(EXAMPLE)
    assert out["id"] == EXAMPLE
    scene = out["shot_plan"]["clip"]["scenes"][0]
    for key in ("start_sec", "end_sec", "act", "kind", "prompt"):
        assert key in scene


def test_pricing(sb):
    assert sb.pricing()["free_songs_per_month"] >= 0


def test_unknown_example_is_not_found(sb):
    with pytest.raises(NotFound) as ei:
        sb.example("does-not-exist")
    assert ei.value.code == "not_found"
