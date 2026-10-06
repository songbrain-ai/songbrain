/**
 * Response types of the Songbrain API, schema `songbrain.song/1`.
 *
 * Based on a real response from https://api.songbrain.ai/v1/examples/old-truck-home.
 * New fields can appear at any time; existing fields don't change meaning.
 * All times are seconds from the start of the song unless the name says
 * otherwise (`start_in_clip`).
 */

export type SongStatus = "processing" | "done" | "failed";

/** One of the sections a song document has. Use with `include`. */
export type SectionName =
  | "song_dna"
  | "timeline"
  | "best_moments"
  | "lyrics"
  | "scores"
  | "story"
  | "shot_plan";

export interface Billing {
  /** "free" or "credits". */
  type: "free" | "credits" | (string & {});
  credits: number;
}

export interface SongInfo {
  title: string | null;
  artist: string | null;
  duration_sec: number | null;
  language: string | null;
  has_vocals: boolean | null;
}

export interface KeyChange {
  at_sec: number;
  to: string;
}

export interface Instrument {
  name: string;
  confidence: number;
}

export interface LoudnessCheck {
  loudness_ok: boolean;
  delta_lufs: number;
}

export interface SoundsLike {
  artist: string;
  track: string;
}

export interface SongDNA {
  genre: string;
  /** One of 37 subgenres. */
  subgenre: string;
  genre_confidence: number;
  style?: string | null;
  tempo_bpm: number;
  tempo_confidence: number;
  /** e.g. "C minor". */
  key: string;
  key_confidence: number;
  key_changes: KeyChange[];
  /** e.g. ["epic", "powerful", "melancholic"]. */
  mood: string[];
  /** Vocal style, or "instrumental". */
  vocals: string;
  /** Instruments with confidence >= 0.25. */
  instruments: Instrument[];
  /** 0-1. */
  energy: number;
  /** 0-1. */
  brightness: number;
  /** Integrated loudness (EBU R128). */
  loudness_lufs: number;
  true_peak_dbfs: number;
  /** Per platform: spotify, youtube, apple. */
  streaming_loudness: Record<string, LoudnessCheck>;
  tagline?: string | null;
  description?: string | null;
  sounds_like?: SoundsLike[];
}

export interface Section {
  start_sec: number;
  end_sec: number;
  /** Same letter = same music, e.g. A, B, A. */
  label: string;
  /** 0-1, relative to the song's loudest part. */
  energy: number;
}

export interface VocalChange {
  at_sec: number;
  label: string;
}

export interface LyricHook {
  at_sec: number;
  line: string;
  role: string;
  strength: number;
}

export interface Timeline {
  /** Every beat in seconds. In view=summary this is a short placeholder string. */
  beats: number[] | string;
  /** First beat of each bar. In view=summary this is a short placeholder string. */
  downbeats: number[] | string;
  time_signature: string;
  sections: Section[];
  vocal_timeline: VocalChange[];
  lyric_hooks: LyricHook[] | null;
}

export interface PlatformFit {
  tiktok: number;
  instagram_reels: number;
  youtube_shorts: number;
}

export interface CaptionIdeas {
  curiosity?: string;
  hype?: string;
  storytelling?: string;
}

export interface BestMoment {
  /** 1 = strongest. */
  rank: number;
  start_sec: number;
  peak_sec: number;
  end_sec: number;
  duration_sec: number;
  kind: string;
  /** 0-100. */
  score: number;
  why: string;
  explanation: string;
  judge_note: string;
  /** The words sung inside the window. */
  sung: string | null;
  platform_fit: PlatformFit;
  /** Beats inside the window. Omitted in view=summary. */
  beat_grid_sec?: number[];
  caption_ideas: CaptionIdeas | null;
  hashtags: string[] | null;
}

export interface Word {
  w: string;
  start: number;
  end: number;
}

export interface LyricLine {
  start: number;
  end: number;
  text: string;
  /** Omitted in view=summary. */
  words?: Word[];
}

export interface Lyrics {
  language?: string | null;
  lines?: LyricLine[];
  /** true for recognised commercial recordings; then `lines` is absent. */
  hidden?: boolean;
  reason?: string;
}

export interface ScoreBlock {
  /** 0-100. */
  score: number;
  breakdown: Record<string, number>;
  note?: string;
}

export interface WhatWorks {
  title: string;
  detail: string;
}

export interface WhatToFix {
  title: string;
  problem: string;
  fix: string;
}

export interface Scores {
  /** Song strength for short-form video. Not a view prediction. */
  virality: ScoreBlock;
  quality: ScoreBlock;
  lyrics: ScoreBlock;
  summary: string;
  what_works: WhatWorks[];
  what_to_fix: WhatToFix[];
  audience: string[];
}

export interface StoryElement {
  /** The one object the video is about. */
  thing: string;
  before: string;
  event: string;
  after: string;
}

export interface StoryBeats {
  setup: string;
  turn: string;
  payoff: string;
}

export interface Story {
  meaning: string;
  why_these_visuals: string;
  confidence: number;
  /** One place for every shot. */
  world: string;
  protagonist: string | null;
  carrier: string;
  recurring_presence: string | null;
  props: string[];
  lyric_evidence: string[];
  /** Three colours for every shot. */
  palette: string[];
  element: StoryElement;
  story_beats: StoryBeats;
}

export interface ShotStyle {
  palette: string[] | null;
  /** Append to your own prompts to stay in the look. */
  prompt_suffix: string | null;
  world: string | null;
}

export interface Phases {
  tease_end?: number;
  payoff_start?: number;
  payoff_end?: number;
  outro_start?: number;
}

export type SceneKind = "tease" | "build" | "cutaway" | "burst" | "strobe" | "hero" | "outro" | (string & {});
export type Act = "setup" | "turn" | "payoff" | (string & {});

export interface Scene {
  index: number;
  /** tease, build, cutaway, burst, strobe (about 4 frames), hero, outro. */
  kind: SceneKind;
  act: Act;
  role: string;
  /** Absolute seconds in the song. Cuts sit on beats. */
  start_sec: number;
  end_sec: number;
  /** Relative to clip.window_sec[0]. */
  start_in_clip: number;
  duration_sec: number;
  beats_in_scene: number;
  transition_in: string;
  motion: string;
  /** A ready image/video prompt with world, palette and style. */
  prompt: string | null;
  /** The readable part of the prompt, without the style tail. */
  visual: string | null;
  framing: string | null;
  emotion: string | null;
  symbol: string | null;
  story_beat: string | null;
  /** The words sung during the scene. */
  sung: string | null;
}

export interface Clip {
  /** [start, end] of the clip in the song. */
  window_sec: [number, number];
  aspect_ratio: string;
  /** Tempo of the cut grid; can run at double time. */
  grid_bpm: number | null;
  /** Beats inside the window. Omitted in view=summary. */
  beats_sec?: number[];
  /** The repeated sung line the payoff lands on. */
  hook_line: string | null;
  phases_sec: Phases;
  scenes: Scene[];
}

export interface FullSongSection {
  start_sec: number;
  end_sec: number;
  section: string;
  energy: number;
  energy_rank: number;
  act: Act;
  cut_every_beats: number;
  /** Cut points on the song's own beats. Omitted in view=summary. */
  cuts_sec?: number[] | null;
  role: string;
  visual: string | null;
  prompt?: string | null;
  sung: string | null;
}

export interface FullSong {
  note: string;
  sections: FullSongSection[];
}

export interface ShotPlan {
  status: "ready" | "pending" | "unavailable" | (string & {});
  /** Set when status is "unavailable". */
  reason?: string;
  engine?: string;
  style?: ShotStyle;
  /** A beat-synced edit of the best moment (about 15 s, 9:16). */
  clip?: Clip;
  /** Section-level plan for a full-length video. */
  full_song?: FullSong | null;
}

export interface ErrorInfo {
  code: string;
  message: string;
}

/**
 * The song document. While processing, only `id`, `status`, `progress` and
 * `eta_sec` are set. With `include`, only the named sections are present.
 */
export interface Song {
  object: "song";
  schema?: string;
  id: string;
  status: SongStatus;
  progress?: number;
  eta_sec?: number;
  /** Set when status is "failed". */
  error?: ErrorInfo;
  song?: SongInfo;
  song_dna?: SongDNA;
  timeline?: Timeline;
  best_moments?: BestMoment[];
  lyrics?: Lyrics;
  scores?: Scores;
  story?: Story;
  shot_plan?: ShotPlan;
  created_at?: string | null;
  external_ref?: string | null;
  billing?: Billing;
}

/** The 202 body of POST /songs. */
export interface SongCreated {
  object: "song";
  id: string;
  status: "processing";
  eta_sec: number;
  billing: Billing;
  external_ref?: string | null;
  url: string;
}

/** GET /songs/{id}/shot-plan and GET /examples/{id}/shot-plan. */
export interface SongShotPlan {
  id: string;
  status?: SongStatus;
  song?: SongInfo;
  story?: Story;
  shot_plan?: ShotPlan;
}

export interface SongListItem {
  id: string;
  status: string;
  external_ref: string | null;
  created_at: string | null;
  billing: Billing;
}

export interface SongList {
  object: "list";
  data: SongListItem[];
}

export interface DeleteResult {
  id: string;
  deleted: boolean;
}

export interface ExampleSummary {
  id: string;
  title: string;
  artist: string;
  genre: string;
  subgenre: string;
  tempo_bpm: number;
  key: string;
  duration_sec: number;
  has_vocals: boolean;
  about: string;
  scenes: number;
  url: string;
  shot_plan_url: string;
}

export interface ExampleList {
  object: "list";
  data: ExampleSummary[];
}

export interface Account {
  credits: number;
  free_songs_per_month: number;
  free_songs_used: number;
  free_songs_left: number;
  price_per_song_credits: number;
  price_per_song_usd: number;
  songs_this_month: number;
  buy_credits_url: string;
  songs_left_from_credits?: number;
  low_balance?: boolean;
  low_balance_threshold_songs?: number;
  key?: { id: string; name: string | null };
}

export interface Pricing {
  free_songs_per_month: number;
  price_per_song_credits: number;
  price_per_song_usd: number;
  credit_packs: { credits: number; usd: number }[];
  included_per_song: string[];
  volume: string;
  limits: Record<string, number>;
  examples_are_free: boolean;
}

/** A webhook event body. */
export interface WebhookEvent<T = Record<string, unknown>> {
  type: "song.done" | "song.failed" | "account.low_balance" | (string & {});
  /** Unix seconds. */
  created: number;
  data: T;
}
