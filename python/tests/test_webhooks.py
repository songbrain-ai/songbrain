import hashlib
import hmac
import json

import pytest

from songbrain import webhooks
from songbrain.webhooks import WebhookVerificationError, construct_event, sign, verify

SECRET = "whsec_test_123"
BODY = json.dumps(
    {"type": "song.done", "created": 1791200000, "data": {"id": "8f0c", "status": "done", "external_ref": "abc"}}
).encode()
NOW = 1791200000


def _header(body: bytes = BODY, ts: int = NOW, secret: str = SECRET) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={ts},v1={mac}"


def test_valid_signature():
    assert verify(BODY, _header(), SECRET, now=NOW)


def test_matches_documented_reference_implementation():
    # The verify() snippet from https://www.songbrain.ai/docs/api#webhooks
    def reference(raw_body, header, secret):
        parts = dict(p.split("=", 1) for p in header.split(","))
        mac = hmac.new(secret.encode(), f"{parts['t']}.".encode() + raw_body, hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, parts["v1"])

    header = sign(BODY, SECRET, timestamp=NOW)
    assert reference(BODY, header, SECRET)
    assert header == _header()


def test_str_body_is_accepted():
    assert verify(BODY.decode(), _header(), SECRET, now=NOW)


def test_tampered_body_fails():
    assert not verify(BODY.replace(b"done", b"fail"), _header(), SECRET, now=NOW)


def test_wrong_secret_fails():
    assert not verify(BODY, _header(), "other", now=NOW)


def test_old_signature_fails_and_tolerance_can_be_disabled():
    assert not verify(BODY, _header(), SECRET, tolerance=300, now=NOW + 301)
    assert verify(BODY, _header(), SECRET, tolerance=300, now=NOW + 299)
    assert verify(BODY, _header(), SECRET, tolerance=None, now=NOW + 10_000)


def test_future_signature_outside_tolerance_fails():
    assert not verify(BODY, _header(), SECRET, now=NOW - 301)


@pytest.mark.parametrize("header", ["", "garbage", "t=abc,v1=00", f"t={NOW}", "v1=00", None])
def test_malformed_headers_fail(header):
    assert not verify(BODY, header, SECRET, now=NOW)


def test_spaces_and_multiple_v1_values():
    good = _header().split("v1=")[1]
    assert verify(BODY, f"t={NOW}, v1=deadbeef, v1={good}", SECRET, now=NOW)


def test_construct_event(monkeypatch):
    monkeypatch.setattr(webhooks.time, "time", lambda: NOW)
    event = construct_event(BODY, _header(), SECRET)
    assert event["type"] == "song.done"
    assert event["data"]["id"] == "8f0c"
    with pytest.raises(WebhookVerificationError):
        construct_event(BODY, _header(secret="nope"), SECRET)
