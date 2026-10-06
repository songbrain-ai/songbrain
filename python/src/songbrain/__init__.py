"""Songbrain: song in, video plan out.

The official Python client for the Songbrain API (https://www.songbrain.ai/docs/api).

    from songbrain import Songbrain

    sb = Songbrain()  # reads SONGBRAIN_API_KEY
    song = sb.analyze("song.mp3")
    for scene in song["shot_plan"]["clip"]["scenes"]:
        print(scene["start_sec"], scene["end_sec"], scene["prompt"])
"""

from . import types, webhooks
from ._client import DEFAULT_BASE_URL, SECTIONS, FileInput, Include, Songbrain
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

__all__ = [
    "Songbrain",
    "DEFAULT_BASE_URL",
    "SECTIONS",
    "FileInput",
    "Include",
    "SongbrainError",
    "AuthenticationError",
    "InsufficientCredits",
    "NotFound",
    "RateLimited",
    "AnalysisFailed",
    "WaitTimeout",
    "types",
    "webhooks",
    "__version__",
]
