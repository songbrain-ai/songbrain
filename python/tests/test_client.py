"""Offline unit tests for the client, with a fake HTTP session."""

import io
import json
import pathlib
import re

import pytest
import requests

import songbrain
from songbrain import (
    AnalysisFailed,
    AuthenticationError,
    InsufficientCredits,
    NotFound,
    RateLimited,
    Songbrain,
    SongbrainError,
    WaitTimeout,
)


def _resp(status=200, body=None, headers=None):
    r = requests.Response()
    r.status_code = status
    r._content = b"" if body is None else json.dumps(body).encode()
    r.headers.update(headers or {})
    r.headers.setdefault("Content-Type", "application/json")
    return r


def _limited(code="rate_limited", retry_after="1"):
    return _resp(429, {"error": {"code": code, "message": "slow down"}}, {"Retry-After": retry_after})


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def request(self, method, url, **kw):
        files = kw.get("files")
        if files:
            kw["uploaded"] = {k: (v[0], v[1].read()) for k, v in files.items()}
        self.calls.append((method, url, kw))
        nxt = self.responses.pop(0)
        if isinstance(nxt, Exception):
            raise nxt
        return nxt

    def close(self):
        pass


def _client(responses, **kw):
    sess = FakeSession(responses)
    sb = Songbrain("sb_live_test", session=sess, **kw)
    sb._sleep = lambda s: sess.calls.append(("sleep", s, {}))
    return sb, sess


def test_version_matches_pyproject():
    text = (pathlib.Path(__file__).parents[1] / "pyproject.toml").read_text()
    assert re.search(r'^version = "([^"]+)"', text, re.M).group(1) == songbrain.__version__


def test_reads_key_from_env(monkeypatch):
    monkeypatch.setenv("SONGBRAIN_API_KEY", "sb_live_env")
    assert Songbrain().api_key == "sb_live_env"
    assert Songbrain("explicit").api_key == "explicit"


def test_auth_header_and_params():
    sb, sess = _client([_resp(body={"id": "x", "status": "done"})])
    sb.get_song("x", view="summary", include=["song_dna", "shot_plan"])
    method, url, kw = sess.calls[0]
    assert method == "GET" and url == "https://api.songbrain.ai/v1/songs/x"
    assert kw["headers"]["Authorization"] == "Bearer sb_live_test"
    assert kw["params"] == {"view": "summary", "include": "song_dna,shot_plan"}


def test_no_key_sends_no_auth_header(monkeypatch):
    monkeypatch.delenv("SONGBRAIN_API_KEY", raising=False)
    sess = FakeSession([_resp(body={"object": "list", "data": []})])
    Songbrain(session=sess).examples()
    assert "Authorization" not in sess.calls[0][2]["headers"]


@pytest.mark.parametrize(
    "status,cls",
    [(401, AuthenticationError), (402, InsufficientCredits), (404, NotFound), (400, SongbrainError), (409, SongbrainError)],
)
def test_error_mapping(status, cls):
    sb, _ = _client([_resp(status, {"error": {"code": "some_code", "message": "Some message"}})])
    with pytest.raises(cls) as ei:
        sb.account()
    assert ei.value.status == status
    assert ei.value.code == "some_code"
    assert ei.value.message == "Some message"


def test_rate_limit_retries_with_retry_after():
    sb, sess = _client([_limited(retry_after="2"), _resp(body={"credits": 5})])
    assert sb.account() == {"credits": 5}
    assert ("sleep", 2.0, {}) in sess.calls


def test_rate_limit_gives_up_after_max_retries():
    sb, sess = _client([_limited() for _ in range(4)])
    with pytest.raises(RateLimited) as ei:
        sb.account()
    assert ei.value.retry_after == 1.0
    assert len([c for c in sess.calls if c[0] == "GET"]) == 4  # 1 + 3 retries


def test_long_retry_after_is_not_slept():
    sb, sess = _client([_limited(code="daily_cap", retry_after="3600")])
    with pytest.raises(RateLimited) as ei:
        sb.account()
    assert ei.value.code == "daily_cap" and ei.value.retry_after == 3600
    assert not [c for c in sess.calls if c[0] == "sleep"]


def test_5xx_retried_for_get_and_for_create_but_not_for_other_posts():
    sb, _ = _client([_resp(500, {"error": {"code": "x", "message": "y"}}), _resp(body={"ok": True})])
    assert sb.pricing() == {"ok": True}
    # POST /songs carries an Idempotency-Key, so a 500 is safe to retry.
    sb, sess = _client([_resp(500, {"error": {"code": "x", "message": "y"}}), _resp(202, {"id": "s1"})])
    assert sb.analyze(audio_url="https://example.com/a.mp3", wait=False)["id"] == "s1"
    posts = [c for c in sess.calls if c[0] == "POST"]
    assert len(posts) == 2
    # Other POSTs have no key and are not retried on a 500.
    sb, sess = _client([_resp(500, {"error": {"code": "x", "message": "y"}})])
    with pytest.raises(SongbrainError):
        sb.test_webhook("https://example.com/hook")
    assert len(sess.calls) == 1


def test_non_json_error_body():
    r = requests.Response()
    r.status_code = 502
    r._content = b"<html>Bad gateway</html>"
    sb, _ = _client([r], max_retries=0)
    with pytest.raises(SongbrainError) as ei:
        sb.pricing()
    assert ei.value.status == 502 and ei.value.code == "http_502"


def test_analyze_url_no_wait():
    body = {"object": "song", "id": "s1", "status": "processing", "eta_sec": 75, "billing": {"type": "free", "credits": 0}}
    sb, sess = _client([_resp(202, body)])
    out = sb.analyze(audio_url="https://example.com/a.mp3", title="T", external_ref="r1", wait=False)
    assert out["id"] == "s1"
    method, url, kw = sess.calls[0]
    assert method == "POST" and url.endswith("/songs")
    assert kw["json"] == {"audio_url": "https://example.com/a.mp3", "title": "T", "external_ref": "r1"}


def test_analyze_upload_and_wait(tmp_path):
    f = tmp_path / "my song.mp3"
    f.write_bytes(b"ID3" + b"\x00" * 64)
    sb, sess = _client(
        [
            _resp(202, {"id": "s2", "status": "processing"}),
            _resp(body={"id": "s2", "status": "processing", "progress": 0.5}),
            _resp(body={"id": "s2", "status": "done", "shot_plan": {"status": "ready"}}),
        ]
    )
    doc = sb.analyze(str(f), artist="A", poll_interval=1)
    assert doc["status"] == "done"
    _, _, kw = sess.calls[0]
    assert kw["uploaded"]["file"][0] == "my song.mp3"
    assert kw["data"] == {"artist": "A"}


def test_upload_retry_resends_whole_file():
    data = io.BytesIO(b"RIFF\x00\x00\x00\x00WAVE" + b"\x01" * 32)
    sb, sess = _client([_limited(code="too_many_in_flight", retry_after="0"), _resp(202, {"id": "s3"})])
    sb.analyze(data, wait=False)
    posts = [c for c in sess.calls if c[0] == "POST"]
    assert len(posts) == 2
    assert posts[0][2]["uploaded"] == posts[1][2]["uploaded"]
    assert posts[1][2]["uploaded"]["file"][0] == "song.wav"


def test_bytes_without_known_format_need_filename():
    sb, _ = _client([])
    with pytest.raises(ValueError):
        sb.analyze(b"not audio", wait=False)


def test_exactly_one_source():
    sb, _ = _client([])
    with pytest.raises(ValueError):
        sb.analyze()
    with pytest.raises(ValueError):
        sb.analyze(b"x", audio_url="https://x")


def test_wait_raises_analysis_failed():
    sb, _ = _client([_resp(body={"id": "s4", "status": "failed", "error": {"code": "decode_failed", "message": "bad"}})])
    with pytest.raises(AnalysisFailed) as ei:
        sb.wait_for("s4")
    assert ei.value.song_id == "s4" and ei.value.code == "decode_failed"


def test_wait_timeout():
    sb, _ = _client([_resp(body={"id": "s5", "status": "processing"})])
    with pytest.raises(WaitTimeout) as ei:
        sb.wait_for("s5", timeout=0)
    assert ei.value.song_id == "s5"


def test_ids_are_url_quoted():
    sb, sess = _client([_resp(body={})])
    sb.example_shot_plan("a/b")
    assert sess.calls[0][1].endswith("/examples/a%2Fb/shot-plan")


# -- idempotency --------------------------------------------------------------


def _key(call):
    return call[2]["headers"].get("Idempotency-Key")


def test_create_sends_uuid_idempotency_key_reused_across_retries():
    sb, sess = _client(
        [
            requests.ConnectionError("reset"),
            _resp(502, {"error": {"code": "bad_gateway", "message": "x"}}),
            _resp(202, {"id": "s1"}),
        ]
    )
    sb.analyze(audio_url="https://example.com/a.mp3", wait=False)
    posts = [c for c in sess.calls if c[0] == "POST"]
    assert len(posts) == 3
    keys = {_key(c) for c in posts}
    assert len(keys) == 1
    assert re.fullmatch(r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}", keys.pop())


def test_each_create_gets_a_new_key_and_caller_can_override():
    sb, sess = _client([_resp(202, {"id": "a"}), _resp(202, {"id": "b"}), _resp(202, {"id": "c"})])
    sb.analyze(audio_url="https://x/a.mp3", wait=False)
    sb.analyze(audio_url="https://x/a.mp3", wait=False)
    sb.analyze(audio_url="https://x/a.mp3", wait=False, idempotency_key="job-42")
    k1, k2, k3 = (_key(c) for c in sess.calls)
    assert k1 != k2 and k3 == "job-42"


def test_upload_sends_idempotency_key_too():
    sb, sess = _client([_resp(202, {"id": "s"})])
    sb.analyze(b"ID3" + bytes(32), wait=False, idempotency_key="k1")
    assert _key(sess.calls[0]) == "k1"


def test_network_error_on_post_without_key_is_not_retried():
    sb, sess = _client([requests.ConnectionError("reset")])
    with pytest.raises(SongbrainError) as ei:
        sb.test_webhook("https://example.com/hook")
    assert ei.value.code == "connection_error"
    assert len(sess.calls) == 1


def test_idempotency_in_progress_is_retried_after_a_second():
    busy = _resp(409, {"error": {"code": "idempotency_in_progress", "message": "x"}})
    sb, sess = _client([busy, _resp(202, {"id": "s"})])
    sb.analyze(audio_url="https://x/a.mp3", wait=False)
    sleeps = [c[1] for c in sess.calls if c[0] == "sleep"]
    assert len(sleeps) == 1 and sleeps[0] >= 1.0


def test_idempotency_key_reused_is_raised():
    sb, sess = _client([_resp(409, {"error": {"code": "idempotency_key_reused", "message": "x"}})])
    with pytest.raises(SongbrainError) as ei:
        sb.analyze(audio_url="https://x/a.mp3", wait=False, idempotency_key="same")
    assert ei.value.status == 409 and ei.value.code == "idempotency_key_reused"
    assert len(sess.calls) == 1


def test_get_requests_have_no_idempotency_key():
    sb, sess = _client([_resp(body={})])
    sb.account()
    assert "Idempotency-Key" not in sess.calls[0][2]["headers"]


# -- test mode ----------------------------------------------------------------


def test_test_mode_needs_no_audio_and_sends_test_true():
    created = {"id": "test_abc", "status": "processing", "livemode": False, "billing": {"type": "test", "credits": 0}}
    done = {"id": "test_abc", "status": "done", "livemode": False, "shot_plan": {"status": "ready"}}
    sb, sess = _client([_resp(202, created), _resp(body=done)])
    doc = sb.analyze(test=True, title="CI", external_ref="build-1")
    assert doc["livemode"] is False
    method, url, kw = sess.calls[0]
    assert method == "POST" and kw["json"] == {"title": "CI", "external_ref": "build-1", "test": True}
    assert _key(sess.calls[0])


def test_test_mode_with_url_and_with_upload():
    sb, sess = _client([_resp(202, {"id": "test_1"}), _resp(202, {"id": "test_2"})])
    sb.analyze(audio_url="https://x/a.mp3", test=True, wait=False)
    assert sess.calls[0][2]["json"] == {"audio_url": "https://x/a.mp3", "test": True}
    sb.analyze(b"ID3" + bytes(32), test=True, wait=False)
    assert sess.calls[1][2]["data"] == {"test": "true"}


def test_no_test_flag_by_default():
    sb, sess = _client([_resp(202, {"id": "s"})])
    sb.analyze(audio_url="https://x/a.mp3", wait=False)
    assert "test" not in sess.calls[0][2]["json"]


# -- request ids and rate limits ----------------------------------------------


def test_error_carries_request_id_from_body():
    body = {"error": {"code": "invalid_url", "message": "Bad URL", "request_id": "req_body"}}
    sb, _ = _client([_resp(400, body, {"Songbrain-Request-Id": "req_header"})])
    with pytest.raises(SongbrainError) as ei:
        sb.account()
    assert ei.value.request_id == "req_body"
    assert ei.value.message == "Bad URL"
    assert "req_body" in str(ei.value)
    assert "req_body" in repr(ei.value)


def test_error_request_id_falls_back_to_header():
    sb, _ = _client([_resp(404, {"error": {"code": "not_found", "message": "x"}}, {"Songbrain-Request-Id": "req_h"})])
    with pytest.raises(NotFound) as ei:
        sb.get_song("nope")
    assert ei.value.request_id == "req_h"
    assert str(ei.value) == "[404] not_found: x (request_id: req_h)"


def test_rate_limited_has_request_id():
    r = _resp(
        429,
        {"error": {"code": "rate_limited", "message": "x", "request_id": "req_429"}},
        {"Retry-After": "3600"},
    )
    sb, _ = _client([r])
    with pytest.raises(RateLimited) as ei:
        sb.account()
    assert ei.value.request_id == "req_429" and ei.value.retry_after == 3600


def test_error_without_request_id():
    sb, _ = _client([_resp(400, {"error": {"code": "c", "message": "m"}})])
    with pytest.raises(SongbrainError) as ei:
        sb.account()
    assert ei.value.request_id is None and str(ei.value) == "[400] c: m"


def test_validation_error_envelope():
    body = {
        "error": {
            "code": "invalid_request",
            "message": "limit: must be <= 100",
            "request_id": "req_v",
            "errors": [{"field": "limit", "message": "must be <= 100"}],
        }
    }
    sb, _ = _client([_resp(400, body)])
    with pytest.raises(SongbrainError) as ei:
        sb.list_songs(limit=500)
    assert ei.value.code == "invalid_request"
    assert ei.value.body["error"]["errors"][0]["field"] == "limit"


def test_last_rate_limit_and_request_id():
    headers = {
        "X-RateLimit-Limit": "120",
        "X-RateLimit-Remaining": "119",
        "X-RateLimit-Reset": "60",
        "Songbrain-Request-Id": "req_1",
    }
    sb, _ = _client([_resp(body={}, headers=headers), _resp(body={})])
    assert sb.last_rate_limit is None and sb.last_request_id is None
    sb.account()
    assert sb.last_rate_limit == {"limit": 120, "remaining": 119, "reset": 60}
    assert sb.last_request_id == "req_1"
    sb.pricing()  # a no-key endpoint has no rate-limit headers: the last value stays
    assert sb.last_rate_limit == {"limit": 120, "remaining": 119, "reset": 60}
    assert sb.last_request_id is None


def test_last_rate_limit_updates_on_errors():
    headers = {"Retry-After": "3600", "X-RateLimit-Limit": "120", "X-RateLimit-Remaining": "0", "X-RateLimit-Reset": "12"}
    sb, _ = _client([_resp(429, {"error": {"code": "rate_limited", "message": "x"}}, headers)])
    with pytest.raises(RateLimited):
        sb.account()
    assert sb.last_rate_limit == {"limit": 120, "remaining": 0, "reset": 12}


# -- pagination ---------------------------------------------------------------


def test_list_songs_with_cursor():
    page = {"object": "list", "data": [{"id": "s9", "livemode": True}], "has_more": True, "next_cursor": "s9"}
    sb, sess = _client([_resp(body=page)])
    out = sb.list_songs(limit=1, starting_after="s10")
    assert out["has_more"] is True and out["next_cursor"] == "s9"
    assert sess.calls[0][2]["params"] == {"limit": 1, "starting_after": "s10"}


def test_list_songs_without_cursor_sends_no_starting_after():
    sb, sess = _client([_resp(body={"object": "list", "data": [], "has_more": False, "next_cursor": None})])
    sb.list_songs()
    assert sess.calls[0][2]["params"] == {"limit": 20}


def test_iter_songs_follows_cursors():
    pages = [
        {"object": "list", "data": [{"id": "s5"}, {"id": "s4"}], "has_more": True, "next_cursor": "s4"},
        {"object": "list", "data": [{"id": "s3"}, {"id": "s2"}], "has_more": True, "next_cursor": "s2"},
        {"object": "list", "data": [{"id": "s1"}], "has_more": False, "next_cursor": None},
    ]
    sb, sess = _client([_resp(body=p) for p in pages])
    ids = [s["id"] for s in sb.iter_songs(page_size=2)]
    assert ids == ["s5", "s4", "s3", "s2", "s1"]
    params = [c[2]["params"] for c in sess.calls]
    assert params == [{"limit": 2}, {"limit": 2, "starting_after": "s4"}, {"limit": 2, "starting_after": "s2"}]


def test_iter_songs_is_lazy_and_handles_empty():
    sb, sess = _client([_resp(body={"object": "list", "data": [], "has_more": False, "next_cursor": None})])
    it = sb.iter_songs()
    assert sess.calls == []
    assert list(it) == []
    assert len(sess.calls) == 1


# -- webhooks -----------------------------------------------------------------


def test_test_webhook():
    result = {"delivered": True, "status_code": 200, "latency_ms": 85, "event_id": "evt_1"}
    sb, sess = _client([_resp(body=result)])
    assert sb.test_webhook("https://example.com/hook") == result
    method, url, kw = sess.calls[0]
    assert method == "POST" and url.endswith("/webhooks/test")
    assert kw["json"] == {"url": "https://example.com/hook"}


def test_webhook_deliveries():
    body = {"object": "list", "data": [{"event_id": "evt_1", "type": "ping", "delivered": True, "attempt": 1}]}
    sb, sess = _client([_resp(body=body)])
    assert sb.webhook_deliveries(limit=5)["data"][0]["event_id"] == "evt_1"
    method, url, kw = sess.calls[0]
    assert method == "GET" and url.endswith("/webhooks/deliveries") and kw["params"] == {"limit": 5}
