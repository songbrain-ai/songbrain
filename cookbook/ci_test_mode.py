"""Test your Songbrain integration in CI with test mode: free, fast, no audio.

    pip install "songbrain>=0.2" pytest
    export SONGBRAIN_API_KEY=sb_live_...      # a CI secret; test songs never cost anything
    pytest cookbook/ci_test_mode.py -v

`analyze(test=True)` returns at once with a song that is already done. The body
is the Sugar Rush example analysis with your title and external_ref,
`livemode: false` and `billing: {"type": "test", "credits": 0}`. It does not use
your free songs. Test songs are rate-limited like real ones and count toward the
daily cap, so keep CI to a handful per run.

Copy the tests that match what your code relies on: the fields you read, the
webhook handler and your error handling. Without SONGBRAIN_API_KEY the API
tests are skipped; the webhook test always runs (it needs no network).

GitHub Actions:

    - run: pip install "songbrain>=0.2" pytest && pytest cookbook/ci_test_mode.py
      env:
        SONGBRAIN_API_KEY: ${{ secrets.SONGBRAIN_API_KEY }}
"""

import json
import os
import time
import uuid

import pytest

from songbrain import Songbrain, SongbrainError, webhooks

needs_key = pytest.mark.skipif(not os.environ.get("SONGBRAIN_API_KEY"), reason="SONGBRAIN_API_KEY not set")


@pytest.fixture(scope="module")
def sb():
    with Songbrain() as client:
        yield client


@needs_key
def test_test_song_has_the_fields_we_use(sb):
    ref = f"ci-{uuid.uuid4().hex[:8]}"
    song = sb.analyze(test=True, title="CI smoke test", external_ref=ref, poll_interval=1, timeout=60)

    assert song["status"] == "done"
    assert song["livemode"] is False  # never mix test songs into production data
    assert song["billing"]["type"] == "test" and song["billing"]["credits"] == 0
    assert song["external_ref"] == ref
    assert song["id"].startswith("test_")

    # The fields this integration reads. Same schema as real songs.
    assert song["song_dna"]["tempo_bpm"] > 0
    scenes = song["shot_plan"]["clip"]["scenes"]
    assert scenes and all(s["end_sec"] > s["start_sec"] for s in scenes)
    assert all(s.get("prompt") for s in scenes)


@needs_key
def test_retrying_with_the_same_idempotency_key_returns_the_same_song(sb):
    key = f"ci-{uuid.uuid4()}"
    first = sb.analyze(test=True, idempotency_key=key, wait=False)
    again = sb.analyze(test=True, idempotency_key=key, wait=False)
    assert first["id"] == again["id"]


@needs_key
def test_errors_carry_a_request_id(sb):
    with pytest.raises(SongbrainError) as ei:
        sb.get_song("does-not-exist")
    assert ei.value.status == 404
    assert ei.value.request_id and ei.value.request_id.startswith("req_")


@needs_key
def test_rate_limit_headers_are_exposed(sb):
    sb.account()
    assert sb.last_rate_limit is not None and sb.last_rate_limit["limit"] > 0


def test_webhook_handler_accepts_a_signed_song_done():
    """Exercise your own handler with a locally signed event (no network)."""
    secret = "whsec_ci"
    body = json.dumps(
        {
            "id": "evt_ci_0001",
            "type": "song.done",
            "created": int(time.time()),
            "livemode": False,
            "data": {"id": "test_ci", "status": "done", "external_ref": "ci"},
        }
    ).encode()
    header = webhooks.sign(body, secret)

    event = webhooks.construct_event(body, header, secret)  # what your handler should do first
    assert event["id"] == "evt_ci_0001" and event["type"] == "song.done"
    with pytest.raises(webhooks.WebhookVerificationError):
        webhooks.construct_event(body.replace(b"done", b"fail"), header, secret)
