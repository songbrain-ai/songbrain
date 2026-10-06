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


def test_5xx_retried_for_get_but_500_not_for_post():
    sb, _ = _client([_resp(500, {"error": {"code": "x", "message": "y"}}), _resp(body={"ok": True})])
    assert sb.pricing() == {"ok": True}
    sb, sess = _client([_resp(500, {"error": {"code": "x", "message": "y"}})])
    with pytest.raises(SongbrainError):
        sb.analyze(audio_url="https://example.com/a.mp3", wait=False)
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
