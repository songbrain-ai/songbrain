import io
import mimetypes
import os
import random
import time
from email.utils import parsedate_to_datetime
from typing import IO, Any, Callable, Dict, Literal, Mapping, Optional, Sequence, Tuple, Union, cast, overload
from urllib.parse import quote

import requests

from ._version import __version__
from .errors import (
    AnalysisFailed,
    AuthenticationError,
    InsufficientCredits,
    NotFound,
    RateLimited,
    SongbrainError,
    WaitTimeout,
)
from .types import (
    Account,
    DeleteResult,
    ExampleList,
    Pricing,
    Song,
    SongCreated,
    SongList,
    SongShotPlan,
)

__all__ = ["Songbrain", "DEFAULT_BASE_URL", "SECTIONS", "FileInput", "Include"]

DEFAULT_BASE_URL = "https://api.songbrain.ai/v1"

#: A local path, raw bytes or an open binary file.
FileInput = Union[str, "os.PathLike[str]", bytes, bytearray, IO[bytes]]
#: Sections to return: "song_dna,shot_plan" or ["song_dna", "shot_plan"].
Include = Union[str, Sequence[str]]

#: The sections a song document has (values for `include`).
SECTIONS: Tuple[str, ...] = ("song_dna", "timeline", "best_moments", "lyrics", "scores", "story", "shot_plan")
_MAX_RETRY_WAIT = 60.0  # never sleep longer than this for one retry
_ERROR_CLASSES = {401: AuthenticationError, 402: InsufficientCredits, 404: NotFound}


def _sniff_extension(head: bytes) -> Optional[str]:
    """Guess the audio format from the first bytes (the API checks the extension against the contents)."""
    if head[:3] == b"ID3":
        return "mp3"
    if head[:4] == b"RIFF" and head[8:12] == b"WAVE":
        return "wav"
    if head[:4] == b"fLaC":
        return "flac"
    if head[:4] == b"OggS":
        return "ogg"
    if head[:4] == b"FORM" and head[8:12] in (b"AIFF", b"AIFC"):
        return "aiff"
    if head[4:8] == b"ftyp":
        return "m4a"
    if len(head) >= 2 and head[0] == 0xFF and (head[1] & 0xE0) == 0xE0:
        # MPEG sync word: layer bits 00 = AAC (ADTS), otherwise MP3.
        return "aac" if (head[1] & 0x06) == 0 else "mp3"
    return None


def _retry_after_seconds(value: Optional[str]) -> Optional[float]:
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = parsedate_to_datetime(value)
        return max(0.0, when.timestamp() - time.time())
    except (TypeError, ValueError, IndexError):
        return None


def _join_include(include: Optional[Include]) -> Optional[str]:
    if include is None:
        return None
    if isinstance(include, str):
        return include
    return ",".join(include)


class Songbrain:
    """Client for the Songbrain API (https://api.songbrain.ai/v1).

    Args:
        api_key: Your key (``sb_live_…``). Defaults to the ``SONGBRAIN_API_KEY`` environment variable.
            The example endpoints work without a key.
        base_url: API base URL. Defaults to ``SONGBRAIN_BASE_URL`` or ``https://api.songbrain.ai/v1``.
        timeout: Timeout in seconds for each HTTP request (uploads included).
        max_retries: How often to retry 429 and 5xx responses, with backoff (default 3).
        session: An optional ``requests.Session`` to reuse.

    Every method returns the JSON body of the response as a ``dict``.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        *,
        base_url: Optional[str] = None,
        timeout: float = 60.0,
        max_retries: int = 3,
        session: Optional[requests.Session] = None,
    ) -> None:
        self.api_key: Optional[str] = api_key if api_key is not None else (os.environ.get("SONGBRAIN_API_KEY") or None)
        self.base_url: str = (base_url or os.environ.get("SONGBRAIN_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")
        self.timeout = timeout
        self.max_retries = max(0, int(max_retries))
        self._session = session or requests.Session()
        self._own_session = session is None
        self._sleep: Callable[[float], None] = time.sleep

    # ── lifecycle ──────────────────────────────────────────────────────────
    def close(self) -> None:
        """Close the underlying HTTP session (only if the client created it)."""
        if self._own_session:
            self._session.close()

    def __enter__(self) -> "Songbrain":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    def __repr__(self) -> str:
        return f"Songbrain(base_url={self.base_url!r}, api_key={'set' if self.api_key else 'not set'})"

    # ── songs ──────────────────────────────────────────────────────────────
    @overload
    def analyze(
        self,
        file: Optional[FileInput] = ...,
        *,
        audio_url: Optional[str] = ...,
        title: Optional[str] = ...,
        artist: Optional[str] = ...,
        webhook_url: Optional[str] = ...,
        external_ref: Optional[str] = ...,
        filename: Optional[str] = ...,
        wait: Literal[True] = ...,
        poll_interval: float = ...,
        timeout: float = ...,
    ) -> Song: ...

    @overload
    def analyze(
        self,
        file: Optional[FileInput] = ...,
        *,
        audio_url: Optional[str] = ...,
        title: Optional[str] = ...,
        artist: Optional[str] = ...,
        webhook_url: Optional[str] = ...,
        external_ref: Optional[str] = ...,
        filename: Optional[str] = ...,
        wait: Literal[False],
        poll_interval: float = ...,
        timeout: float = ...,
    ) -> SongCreated: ...

    def analyze(
        self,
        file: Optional[FileInput] = None,
        *,
        audio_url: Optional[str] = None,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        webhook_url: Optional[str] = None,
        external_ref: Optional[str] = None,
        filename: Optional[str] = None,
        wait: bool = True,
        poll_interval: float = 5.0,
        timeout: float = 300.0,
    ) -> Union[Song, SongCreated]:
        """Analyse a song from a local file or a public URL.

        Pass exactly one of ``file`` (a path, bytes or an open binary file) or ``audio_url``.
        The analysis typically takes 60-90 seconds.

        Args:
            file: Path, bytes or binary file object. MP3, WAV, FLAC, M4A, AAC, OGG or AIFF, up to 100 MB, 30 s to 10 min.
            audio_url: Public http(s) URL of the audio file.
            title: Optional title. Defaults to a cleaned file name.
            artist: Optional artist name.
            webhook_url: Optional public URL that receives ``song.done`` / ``song.failed``.
            external_ref: Optional id of your own, echoed back in responses and webhooks.
            filename: File name sent with an upload. The extension must match the audio format.
                Taken from the path when ``file`` is a path; guessed from the bytes otherwise.
            wait: If ``True`` (default), poll until the song is done and return the full document.
                If ``False``, return the 202 body (``{id, status: "processing", eta_sec, billing}``) right away.
            poll_interval: Seconds between status checks while waiting.
            timeout: Seconds to wait in total before raising :class:`~songbrain.WaitTimeout`.

        Raises:
            AnalysisFailed: The analysis failed (paid credits are refunded automatically).
            WaitTimeout: The song was not done within ``timeout``. It keeps processing on the server.
            InsufficientCredits, RateLimited, SongbrainError: The API rejected the request.
        """
        if (file is None) == (audio_url is None):
            raise ValueError("Pass exactly one of `file` or `audio_url`.")

        fields: Dict[str, str] = {}
        for key, value in (("title", title), ("artist", artist), ("webhook_url", webhook_url), ("external_ref", external_ref)):
            if value is not None:
                fields[key] = value

        if audio_url is not None:
            created = self._request("POST", "/songs", json={"audio_url": audio_url, **fields})
        else:
            fh, name, close_after = self._open_upload(cast(FileInput, file), filename)
            try:
                mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
                created = self._request("POST", "/songs", data=fields, files={"file": (name, fh, mime)})
            finally:
                if close_after:
                    fh.close()

        if not wait:
            return cast(SongCreated, created)
        return self.wait_for(created["id"], poll_interval=poll_interval, timeout=timeout)

    def wait_for(self, song_id: str, *, poll_interval: float = 5.0, timeout: float = 300.0) -> Song:
        """Poll ``GET /songs/{id}`` until the song is done and return the full document.

        Raises:
            AnalysisFailed: The analysis failed.
            WaitTimeout: Not done within ``timeout`` seconds.
        """
        deadline = time.monotonic() + timeout
        interval = max(0.5, float(poll_interval))
        while True:
            doc = self.get_song(song_id)
            status = doc.get("status")
            if status == "done":
                return doc
            if status == "failed":
                err = doc.get("error") or {}
                raise AnalysisFailed(
                    song_id,
                    err.get("code") or "analysis_failed",
                    err.get("message") or "The analysis failed. Paid credits were refunded automatically.",
                    cast(Dict[str, Any], doc),
                )
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise WaitTimeout(song_id, timeout)
            self._sleep(min(interval, remaining))

    def get_song(self, song_id: str, view: Optional[str] = None, include: Optional[Include] = None) -> Song:
        """Get a song. While processing: ``{status: "processing", progress, eta_sec}``. Then the full document.

        Args:
            view: ``"full"`` (default) or ``"summary"`` (drops word timings and beat arrays, about 3x smaller).
            include: Only these sections, e.g. ``["song_dna", "shot_plan"]``. Sections: song_dna, timeline,
                best_moments, lyrics, scores, story, shot_plan.
        """
        params = {"view": view, "include": _join_include(include)}
        return cast(Song, self._request("GET", f"/songs/{quote(song_id, safe='')}", params=params))

    def shot_plan(self, song_id: str) -> SongShotPlan:
        """Get only the story and the shot plan of a song: ``{id, status, song, story, shot_plan}``."""
        return cast(SongShotPlan, self._request("GET", f"/songs/{quote(song_id, safe='')}/shot-plan"))

    def list_songs(self, limit: int = 20) -> SongList:
        """List your songs, newest first: ``{object: "list", data: [...]}``. ``limit`` is 1-100."""
        return cast(SongList, self._request("GET", "/songs", params={"limit": limit}))

    def delete_song(self, song_id: str) -> DeleteResult:
        """Delete a song's audio and analysis now. Raises a 409 ``still_processing`` error while it runs."""
        return cast(DeleteResult, self._request("DELETE", f"/songs/{quote(song_id, safe='')}"))

    # ── account ────────────────────────────────────────────────────────────
    def account(self) -> Account:
        """Free songs left this month, credit balance and price per song."""
        return cast(Account, self._request("GET", "/account"))

    def pricing(self) -> Pricing:
        """Prices and limits. No key needed."""
        return cast(Pricing, self._request("GET", "/pricing"))

    # ── examples (no key) ──────────────────────────────────────────────────
    def examples(self) -> ExampleList:
        """List the example analyses (Songbrain's own songs). No key needed."""
        return cast(ExampleList, self._request("GET", "/examples"))

    def example(self, example_id: str, view: Optional[str] = None, include: Optional[Include] = None) -> Song:
        """A full example document, in exactly the format of :meth:`get_song`. No key needed."""
        params = {"view": view, "include": _join_include(include)}
        return cast(Song, self._request("GET", f"/examples/{quote(example_id, safe='')}", params=params))

    def example_shot_plan(self, example_id: str) -> SongShotPlan:
        """An example story and shot plan, in exactly the format of :meth:`shot_plan`. No key needed."""
        return cast(SongShotPlan, self._request("GET", f"/examples/{quote(example_id, safe='')}/shot-plan"))

    # ── internals ──────────────────────────────────────────────────────────
    @staticmethod
    def _open_upload(file: FileInput, filename: Optional[str]) -> Tuple[IO[bytes], str, bool]:
        close_after = False
        if isinstance(file, (bytes, bytearray)):
            fh: IO[bytes] = io.BytesIO(bytes(file))
            source_name = None
        elif isinstance(file, (str, os.PathLike)):
            path = os.fspath(file)
            fh = open(path, "rb")
            close_after = True
            source_name = os.path.basename(path)
        elif hasattr(file, "read"):
            fh = file
            raw_name = getattr(file, "name", None)
            source_name = os.path.basename(raw_name) if isinstance(raw_name, str) else None
        else:
            raise TypeError("`file` must be a path, bytes or a binary file object.")

        name = filename or source_name
        if not name or not os.path.splitext(name)[1]:
            try:
                pos = fh.tell()
                head = fh.read(16)
                fh.seek(pos)
            except (OSError, AttributeError, io.UnsupportedOperation):
                head = b""
            ext = _sniff_extension(head)
            if not ext:
                if close_after:
                    fh.close()
                raise ValueError(
                    "Could not tell the audio format. Pass `filename` with an extension, e.g. filename='song.mp3'."
                )
            name = f"{os.path.splitext(name or 'song')[0]}.{ext}"
        return fh, name, close_after

    def _headers(self) -> Dict[str, str]:
        headers = {"Accept": "application/json", "User-Agent": f"songbrain-python/{__version__}"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    def _backoff(self, attempt: int) -> float:
        return min(0.5 * 2.0**attempt, 8.0) + random.uniform(0.0, 0.25)

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Mapping[str, Any]] = None,
        json: Optional[Any] = None,
        data: Optional[Mapping[str, str]] = None,
        files: Optional[Dict[str, Tuple[str, IO[bytes], str]]] = None,
    ) -> Dict[str, Any]:
        url = self.base_url + path
        clean_params = {k: v for k, v in (params or {}).items() if v is not None} or None
        idempotent = method in ("GET", "HEAD", "DELETE")
        # Remember where each upload starts, so a retry sends the whole file again.
        starts: Dict[str, int] = {}
        for key, (_, fh, _) in (files or {}).items():
            try:
                starts[key] = fh.tell()
            except (OSError, AttributeError, io.UnsupportedOperation):
                pass

        attempt = 0
        while True:
            for key, pos in starts.items():
                files[key][1].seek(pos)  # type: ignore[index]
            try:
                resp = self._session.request(
                    method,
                    url,
                    params=clean_params,
                    json=json,
                    data=data,
                    files=files,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
            except (requests.ConnectionError, requests.Timeout) as exc:
                # Only safe to resend if the request cannot have created anything.
                if (idempotent or isinstance(exc, requests.ConnectTimeout)) and attempt < self.max_retries:
                    self._sleep(self._backoff(attempt))
                    attempt += 1
                    continue
                raise SongbrainError(0, "connection_error", str(exc)) from exc

            if resp.status_code < 400:
                if not resp.content:
                    return {}
                try:
                    return cast(Dict[str, Any], resp.json())
                except ValueError as exc:
                    raise SongbrainError(resp.status_code, "invalid_response", "Response is not JSON.") from exc

            error = self._error_from(resp)
            status = resp.status_code
            # 429 never started any work. For POST, only retry 5xx that come from the
            # gateway before the request reached the API (502/503).
            retryable = status == 429 or (status >= 500 and (idempotent or status in (502, 503)))
            if retryable and attempt < self.max_retries:
                wait = error.retry_after if isinstance(error, RateLimited) and error.retry_after is not None else None
                delay = self._backoff(attempt) if wait is None else wait
                if delay <= _MAX_RETRY_WAIT:
                    self._sleep(delay)
                    attempt += 1
                    continue
            raise error

    @staticmethod
    def _error_from(resp: requests.Response) -> SongbrainError:
        status = resp.status_code
        body: Optional[Dict[str, Any]] = None
        code = f"http_{status}"
        message = (resp.text or resp.reason or "").strip()[:500] or f"HTTP {status}"
        try:
            parsed = resp.json()
        except ValueError:
            parsed = None
        if isinstance(parsed, dict):
            body = parsed
            err = parsed.get("error")
            if isinstance(err, dict):
                code = str(err.get("code") or code)
                message = str(err.get("message") or message)
            elif "detail" in parsed:  # request validation (422)
                code = "validation_error"
                message = str(parsed["detail"])
        if status == 429:
            return RateLimited(status, code, message, body, _retry_after_seconds(resp.headers.get("Retry-After")))
        cls = _ERROR_CLASSES.get(status, SongbrainError)
        return cls(status, code, message, body)
