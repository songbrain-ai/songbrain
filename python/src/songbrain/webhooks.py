"""Verify Songbrain webhook signatures.

Songbrain signs every webhook with the header::

    Songbrain-Signature: t=<unix seconds>,v1=<hex>

where ``v1`` is the HMAC-SHA256 of ``"<t>.<raw body>"`` keyed with the
webhook secret of the API key that created the song (shown once when the key
is created). Always verify against the raw request body, before parsing JSON.

Every event has an ``id`` (``evt_…``, also sent as the ``Songbrain-Event-Id``
header) that stays the same across retries. Songbrain retries failed
deliveries up to 10 times over about 3 days, so the same event can arrive
more than once: store the ids you have handled and skip repeats.
"""

import hashlib
import hmac
import json
import time
from typing import Any, Dict, List, Optional, Tuple, Union

__all__ = ["SIGNATURE_HEADER", "verify", "construct_event", "sign", "WebhookVerificationError"]

SIGNATURE_HEADER = "Songbrain-Signature"


class WebhookVerificationError(ValueError):
    """The webhook signature is missing, malformed, wrong or too old."""


def _parse(header: str) -> Tuple[Optional[int], List[str]]:
    ts: Optional[int] = None
    sigs: List[str] = []
    for part in (header or "").split(","):
        key, sep, value = part.strip().partition("=")
        if not sep:
            continue
        key, value = key.strip(), value.strip()
        if key == "t":
            try:
                ts = int(value)
            except ValueError:
                return None, []
        elif key == "v1" and value:
            sigs.append(value)
    return ts, sigs


def _mac(raw_body: bytes, timestamp: int, secret: str) -> str:
    return hmac.new(secret.encode("utf-8"), f"{timestamp}.".encode("ascii") + raw_body, hashlib.sha256).hexdigest()


def verify(
    raw_body: Union[bytes, bytearray, str],
    header: Optional[str],
    secret: str,
    tolerance: Optional[float] = 300,
    *,
    now: Optional[float] = None,
) -> bool:
    """Return ``True`` if ``header`` is a valid Songbrain signature for ``raw_body``.

    Args:
        raw_body: The exact request body as received (bytes). A ``str`` is encoded as UTF-8.
        header: The value of the ``Songbrain-Signature`` header.
        secret: Your API key's webhook secret.
        tolerance: Maximum age of the signature in seconds (default 300). ``None`` or ``0`` disables the check.
        now: Override the current Unix time (for tests).

    Never raises for bad input; returns ``False`` instead.
    """
    if not header or not secret:
        return False
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    ts, sigs = _parse(header)
    if ts is None or not sigs:
        return False
    if tolerance:
        current = time.time() if now is None else now
        if abs(current - ts) > tolerance:
            return False
    expected = _mac(bytes(raw_body), ts, secret)
    return any(hmac.compare_digest(expected, s.lower()) for s in sigs)


def construct_event(
    raw_body: Union[bytes, bytearray, str],
    header: Optional[str],
    secret: str,
    tolerance: Optional[float] = 300,
) -> Dict[str, Any]:
    """Verify the signature and return the parsed event.

    The event looks like
    ``{"id": "evt_…", "type": "song.done", "created": 1791200000, "livemode": true, "data": {...}}``.
    Types: ``song.done``, ``song.failed``, ``account.low_balance`` and ``ping`` (from
    :meth:`songbrain.Songbrain.test_webhook`). Dedupe on ``event["id"]``: retries reuse it.

    Raises:
        WebhookVerificationError: if the signature is not valid.
    """
    if not verify(raw_body, header, secret, tolerance):
        raise WebhookVerificationError("Invalid Songbrain-Signature")
    if isinstance(raw_body, (bytes, bytearray)):
        raw_body = bytes(raw_body).decode("utf-8")
    event = json.loads(raw_body)
    if not isinstance(event, dict):
        raise WebhookVerificationError("Webhook body is not a JSON object")
    return event


def sign(raw_body: Union[bytes, bytearray, str], secret: str, timestamp: Optional[int] = None) -> str:
    """Build a ``Songbrain-Signature`` header value. Useful for testing your webhook handler."""
    if isinstance(raw_body, str):
        raw_body = raw_body.encode("utf-8")
    ts = int(time.time()) if timestamp is None else int(timestamp)
    return f"t={ts},v1={_mac(bytes(raw_body), ts, secret)}"
