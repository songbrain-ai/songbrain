"""Exceptions raised by the Songbrain client.

Every API error has the shape
``{"error": {"code": "...", "message": "...", "request_id": "req_..."}}``.
The client turns it into a :class:`SongbrainError` (or a subclass) that
carries the HTTP status, the error code, the message and the request id.
Quote the request id when you contact support.
"""

from typing import Any, Dict, Optional

__all__ = [
    "SongbrainError",
    "AuthenticationError",
    "InsufficientCredits",
    "NotFound",
    "RateLimited",
    "AnalysisFailed",
    "WaitTimeout",
]


class SongbrainError(Exception):
    """An error returned by the Songbrain API, or raised by the client.

    Attributes:
        status: HTTP status code (``0`` when the error did not come from an HTTP response).
        code: Machine-readable error code, e.g. ``"invalid_url"`` or ``"rate_limited"``.
        message: Human-readable message.
        body: The parsed response body, when there was one.
        request_id: The ``Songbrain-Request-Id`` of the failed request (``req_…``), when there was one.
            ``str(error)`` includes it.
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        body: Optional[Dict[str, Any]] = None,
        *,
        request_id: Optional[str] = None,
    ) -> None:
        text = f"[{status}] {code}: {message}" if status else f"{code}: {message}"
        if request_id:
            text += f" (request_id: {request_id})"
        super().__init__(text)
        self.status = status
        self.code = code
        self.message = message
        self.body = body
        self.request_id = request_id

    def __repr__(self) -> str:
        return (
            f"{type(self).__name__}(status={self.status!r}, code={self.code!r}, "
            f"message={self.message!r}, request_id={self.request_id!r})"
        )


class AuthenticationError(SongbrainError):
    """401: the API key is missing, invalid or revoked."""


class InsufficientCredits(SongbrainError):
    """402: the free songs for this month are used up and the balance is below one song."""


class NotFound(SongbrainError):
    """404: unknown id, or the song belongs to another account."""


class RateLimited(SongbrainError):
    """429: too many requests, too many songs in flight, daily cap or busy pipeline.

    Attributes:
        retry_after: Seconds to wait before retrying, from the ``Retry-After`` header (``None`` if absent).
    """

    def __init__(
        self,
        status: int,
        code: str,
        message: str,
        body: Optional[Dict[str, Any]] = None,
        retry_after: Optional[float] = None,
        *,
        request_id: Optional[str] = None,
    ) -> None:
        super().__init__(status, code, message, body, request_id=request_id)
        self.retry_after = retry_after


class AnalysisFailed(SongbrainError):
    """The song was accepted but its analysis failed. Paid credits are refunded automatically.

    Attributes:
        song_id: The id of the failed song.
    """

    def __init__(self, song_id: str, code: str, message: str, body: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(0, code, message, body)
        self.song_id = song_id


class WaitTimeout(SongbrainError):
    """``analyze(wait=True)`` gave up before the song was done. The analysis keeps running on the server.

    Attributes:
        song_id: Use it with :meth:`Songbrain.get_song` to fetch the result later.
    """

    def __init__(self, song_id: str, timeout: float) -> None:
        super().__init__(
            0,
            "wait_timeout",
            f"Song {song_id} was not done after {timeout:g} s. It is still processing; "
            f"fetch it later with get_song({song_id!r}).",
        )
        self.song_id = song_id
