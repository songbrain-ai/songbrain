"""Typed shapes of Songbrain API responses (schema ``songbrain.song/1``).

These are :class:`typing.TypedDict` definitions, so responses stay plain
``dict`` objects at runtime. They exist for editors and type checkers.
New fields can appear in the API at any time; existing fields don't change meaning.
All times are seconds from the start of the song unless the name says otherwise
(``start_in_clip``).
"""

from typing import Any, Dict, List, Optional, TypedDict, Union

__all__ = [
    "Billing",
    "SongInfo",
    "KeyChange",
    "Instrument",
    "LoudnessCheck",
    "SoundsLike",
    "SongDNA",
    "Section",
    "VocalChange",
    "LyricHook",
    "Timeline",
    "BestMoment",
    "Word",
    "LyricLine",
    "Lyrics",
    "ScoreBlock",
    "WhatWorks",
    "WhatToFix",
    "Scores",
    "StoryElement",
    "StoryBeats",
    "Story",
    "ShotStyle",
    "Phases",
    "Scene",
    "Clip",
    "FullSongSection",
    "FullSong",
    "ShotPlan",
    "ErrorInfo",
    "Song",
    "SongCreated",
    "SongShotPlan",
    "SongListItem",
    "SongList",
    "DeleteResult",
    "ExampleSummary",
    "ExampleList",
    "Account",
    "Pricing",
]


class Billing(TypedDict, total=False):
    type: str  # "free" or "credits"
    credits: int


class SongInfo(TypedDict, total=False):
    title: Optional[str]
    artist: Optional[str]
    duration_sec: Optional[float]
    language: Optional[str]
    has_vocals: Optional[bool]


class KeyChange(TypedDict, total=False):
    at_sec: float
    to: str


class Instrument(TypedDict, total=False):
    name: str
    confidence: float


class LoudnessCheck(TypedDict, total=False):
    loudness_ok: bool
    delta_lufs: float


class SoundsLike(TypedDict, total=False):
    artist: str
    track: str


class SongDNA(TypedDict, total=False):
    genre: str
    subgenre: str
    genre_confidence: float
    style: Optional[str]
    tempo_bpm: float
    tempo_confidence: float
    key: str
    key_confidence: float
    key_changes: List[KeyChange]
    mood: List[str]
    vocals: str
    instruments: List[Instrument]
    energy: float
    brightness: float
    loudness_lufs: float
    true_peak_dbfs: float
    streaming_loudness: Dict[str, LoudnessCheck]  # spotify, youtube, apple
    tagline: Optional[str]
    description: Optional[str]
    sounds_like: List[SoundsLike]


class Section(TypedDict, total=False):
    start_sec: float
    end_sec: float
    label: str  # same letter = same music, e.g. A, B, A
    energy: float  # 0-1, relative to the song's loudest part


class VocalChange(TypedDict, total=False):
    at_sec: float
    label: str


class LyricHook(TypedDict, total=False):
    at_sec: float
    line: str
    role: str
    strength: float


class Timeline(TypedDict, total=False):
    # In view=summary, beats and downbeats are replaced by a short string.
    beats: Union[List[float], str]
    downbeats: Union[List[float], str]
    time_signature: str
    sections: List[Section]
    vocal_timeline: List[VocalChange]
    lyric_hooks: Optional[List[LyricHook]]


class BestMoment(TypedDict, total=False):
    rank: int  # 1 = strongest
    start_sec: float
    peak_sec: float
    end_sec: float
    duration_sec: float
    kind: str
    score: int  # 0-100
    reason: Optional[str]  # one sentence: why this moment works
    signals: Optional[List[str]]  # measured audio signals behind the pick
    sung: Optional[str]
    beat_grid_sec: List[float]  # omitted in view=summary


class Word(TypedDict, total=False):
    w: str
    start: float
    end: float


class LyricLine(TypedDict, total=False):
    start: float
    end: float
    text: str
    words: List[Word]  # omitted in view=summary


class Lyrics(TypedDict, total=False):
    language: Optional[str]
    lines: List[LyricLine]
    hidden: bool  # true for recognised commercial recordings
    reason: str


class ScoreBlock(TypedDict, total=False):
    score: int  # 0-100
    breakdown: Dict[str, int]
    note: str


class WhatWorks(TypedDict, total=False):
    title: str
    detail: str


class WhatToFix(TypedDict, total=False):
    title: str
    problem: str
    fix: str


class Scores(TypedDict, total=False):
    virality: ScoreBlock  # song strength for short-form video, not a view prediction
    quality: ScoreBlock
    lyrics: ScoreBlock
    summary: str
    what_works: List[WhatWorks]
    what_to_fix: List[WhatToFix]
    audience: List[str]


class StoryElement(TypedDict, total=False):
    thing: str
    before: str
    event: str
    after: str


class StoryBeats(TypedDict, total=False):
    setup: str
    turn: str
    payoff: str


class Story(TypedDict, total=False):
    meaning: str
    why_these_visuals: str
    confidence: float
    world: str
    protagonist: Optional[str]
    carrier: str
    recurring_presence: Optional[str]
    props: List[str]
    lyric_evidence: List[str]
    palette: List[str]
    element: StoryElement
    story_beats: StoryBeats


class ShotStyle(TypedDict, total=False):
    palette: Optional[List[str]]
    prompt_suffix: Optional[str]
    world: Optional[str]


class Phases(TypedDict, total=False):
    tease_end: float
    payoff_start: float
    payoff_end: float
    outro_start: float


class Scene(TypedDict, total=False):
    index: int
    kind: str  # tease, build, cutaway, burst, strobe, hero, outro
    act: str  # setup, turn, payoff
    role: str
    start_sec: float  # absolute seconds in the song
    end_sec: float
    start_in_clip: float  # relative to clip.window_sec[0]
    duration_sec: float
    beats_in_scene: int
    transition_in: str
    motion: str
    prompt: Optional[str]  # ready-to-use image/video prompt incl. world, palette and style
    visual: Optional[str]  # the readable part of the prompt, without the style tail
    framing: Optional[str]
    emotion: Optional[str]
    symbol: Optional[str]
    story_beat: Optional[str]
    sung: Optional[str]


class Clip(TypedDict, total=False):
    window_sec: List[float]  # [start, end]
    aspect_ratio: str
    grid_bpm: Optional[float]
    beats_sec: List[float]  # omitted in view=summary
    hook_line: Optional[str]
    phases_sec: Phases
    scenes: List[Scene]


class FullSongSection(TypedDict, total=False):
    start_sec: float
    end_sec: float
    section: str
    energy: float
    energy_rank: float
    act: str
    cut_every_beats: int
    cuts_sec: Optional[List[float]]
    role: str
    visual: Optional[str]
    prompt: Optional[str]
    sung: Optional[str]


class FullSong(TypedDict, total=False):
    note: str
    sections: List[FullSongSection]


class ShotPlan(TypedDict, total=False):
    status: str  # "ready", "pending" or "unavailable"
    reason: str  # set when status is "unavailable"
    engine: str
    style: ShotStyle
    clip: Clip
    full_song: Optional[FullSong]


class ErrorInfo(TypedDict, total=False):
    code: str
    message: str


class Song(TypedDict, total=False):
    """The song document. While processing only id, status, progress and eta_sec are set."""

    object: str  # "song"
    schema: str  # "songbrain.song/1"
    id: str
    status: str  # "processing", "done" or "failed"
    progress: float
    eta_sec: int
    error: ErrorInfo  # set when status is "failed"
    song: SongInfo
    song_dna: SongDNA
    timeline: Timeline
    best_moments: List[BestMoment]
    lyrics: Lyrics
    scores: Scores
    story: Story
    shot_plan: ShotPlan
    created_at: Optional[str]
    external_ref: Optional[str]
    billing: Billing


class SongCreated(TypedDict, total=False):
    """The 202 body of POST /songs."""

    object: str
    id: str
    status: str  # "processing"
    eta_sec: int
    billing: Billing
    external_ref: Optional[str]
    url: str


class SongShotPlan(TypedDict, total=False):
    id: str
    status: str
    song: SongInfo
    story: Story
    shot_plan: ShotPlan


class SongListItem(TypedDict, total=False):
    id: str
    status: str
    external_ref: Optional[str]
    created_at: Optional[str]
    billing: Billing


class SongList(TypedDict, total=False):
    object: str  # "list"
    data: List[SongListItem]


class DeleteResult(TypedDict, total=False):
    id: str
    deleted: bool


class ExampleSummary(TypedDict, total=False):
    id: str
    title: str
    artist: str
    genre: str
    subgenre: str
    tempo_bpm: float
    key: str
    duration_sec: float
    has_vocals: bool
    about: str
    scenes: int
    url: str
    shot_plan_url: str


class ExampleList(TypedDict, total=False):
    object: str  # "list"
    data: List[ExampleSummary]


class Account(TypedDict, total=False):
    credits: int
    free_songs_per_month: int
    free_songs_used: int
    free_songs_left: int
    price_per_song_credits: int
    price_per_song_usd: float
    songs_this_month: int
    buy_credits_url: str
    songs_left_from_credits: int
    low_balance: bool
    low_balance_threshold_songs: int
    key: Dict[str, Any]


class Pricing(TypedDict, total=False):
    free_songs_per_month: int
    price_per_song_credits: int
    price_per_song_usd: float
    credit_packs: List[Dict[str, Any]]
    included_per_song: List[str]
    volume: str
    limits: Dict[str, Any]
    examples_are_free: bool
