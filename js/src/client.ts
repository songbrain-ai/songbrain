import {
  AnalysisFailed,
  AuthenticationError,
  InsufficientCredits,
  NotFound,
  RateLimited,
  SongbrainError,
  WaitTimeout,
} from "./errors.js";
import type {
  Account,
  DeleteResult,
  ExampleList,
  Pricing,
  SectionName,
  Song,
  SongCreated,
  SongList,
  SongShotPlan,
} from "./types.js";
import { VERSION } from "./version.js";

export const DEFAULT_BASE_URL = "https://api.songbrain.ai/v1";

/** A Blob/File, a Buffer or bytes, or a local file path (Node). */
export type FileInput = Blob | Uint8Array | ArrayBuffer | string;

export interface SongbrainOptions {
  /** Your key (`sb_live_…`). Defaults to `process.env.SONGBRAIN_API_KEY`. The example endpoints work without a key. */
  apiKey?: string;
  /** Defaults to `process.env.SONGBRAIN_BASE_URL` or https://api.songbrain.ai/v1. */
  baseUrl?: string;
  /** Timeout for each HTTP request in ms (uploads included). Default 60 000. */
  timeoutMs?: number;
  /** How often to retry 429 and 5xx responses, with backoff. Default 3. */
  maxRetries?: number;
  /** A custom fetch implementation. Defaults to the global fetch. */
  fetch?: typeof fetch;
}

export interface AnalyzeOptions {
  /** A Blob/File, a Buffer or bytes, or a local file path. Pass this or `audioUrl`. */
  file?: FileInput;
  /** A public http(s) URL of the audio file. Pass this or `file`. */
  audioUrl?: string;
  title?: string;
  artist?: string;
  /** Receives `song.done` / `song.failed`. */
  webhookUrl?: string;
  /** Your own id, echoed back in responses and webhooks. */
  externalRef?: string;
  /** File name for an upload. Its extension must match the audio format. Taken from the path or File name, or guessed from the bytes. */
  filename?: string;
  /** Wait until the song is done and return the full document (default true). */
  wait?: boolean;
  /** Time between status checks while waiting. Default 5 000. */
  pollIntervalMs?: number;
  /** Total time to wait before throwing `WaitTimeout`. Default 300 000. */
  timeoutMs?: number;
}

export interface WaitOptions {
  pollIntervalMs?: number;
  timeoutMs?: number;
}

export interface GetSongOptions {
  /** "summary" drops word timings and beat arrays (about 3x smaller). */
  view?: "full" | "summary";
  /** Only these sections, e.g. ["song_dna", "shot_plan"]. */
  include?: SectionName[] | string;
}

type Json = Record<string, unknown>;

const MAX_RETRY_WAIT_SEC = 60;
const MIME: Record<string, string> = {
  mp3: "audio/mpeg",
  wav: "audio/wav",
  flac: "audio/flac",
  ogg: "audio/ogg",
  m4a: "audio/mp4",
  aac: "audio/aac",
  aiff: "audio/aiff",
  aif: "audio/aiff",
};

function env(name: string): string | undefined {
  const p = (globalThis as { process?: { env?: Record<string, string | undefined> } }).process;
  return p?.env?.[name] || undefined;
}

/** Guess the audio format from the first bytes (the API checks the extension against the contents). */
export function sniffExtension(head: Uint8Array): string | null {
  const ascii = (from: number, to: number) => String.fromCharCode(...head.subarray(from, to));
  if (ascii(0, 3) === "ID3") return "mp3";
  if (ascii(0, 4) === "RIFF" && ascii(8, 12) === "WAVE") return "wav";
  if (ascii(0, 4) === "fLaC") return "flac";
  if (ascii(0, 4) === "OggS") return "ogg";
  if (ascii(0, 4) === "FORM" && ["AIFF", "AIFC"].includes(ascii(8, 12))) return "aiff";
  if (ascii(4, 8) === "ftyp") return "m4a";
  const b0 = head[0];
  const b1 = head[1];
  if (b0 === 0xff && b1 !== undefined && (b1 & 0xe0) === 0xe0) return (b1 & 0x06) === 0 ? "aac" : "mp3";
  return null;
}

function extOf(name: string): string {
  const base = name.split(/[\\/]/).pop() ?? "";
  const i = base.lastIndexOf(".");
  return i > 0 ? base.slice(i + 1).toLowerCase() : "";
}

function baseName(name: string): string {
  return name.split(/[\\/]/).pop() ?? name;
}

function retryAfterSeconds(value: string | null): number | null {
  if (!value) return null;
  const n = Number(value);
  if (Number.isFinite(n)) return Math.max(0, n);
  const when = Date.parse(value);
  return Number.isNaN(when) ? null : Math.max(0, (when - Date.now()) / 1000);
}

const sleep = (ms: number) => new Promise<void>((resolve) => setTimeout(resolve, ms));

/**
 * Client for the Songbrain API. Every method resolves to the JSON body of
 * the response.
 *
 * ```ts
 * const sb = new Songbrain(); // reads SONGBRAIN_API_KEY
 * const song = await sb.analyze({ file: "song.mp3" });
 * for (const s of song.shot_plan?.clip?.scenes ?? []) console.log(s.start_sec, s.prompt);
 * ```
 */
export class Songbrain {
  readonly apiKey: string | undefined;
  readonly baseUrl: string;
  readonly timeoutMs: number;
  readonly maxRetries: number;
  private readonly fetchImpl: typeof fetch;
  /** @internal Overridable in tests. */
  _sleep: (ms: number) => Promise<void> = sleep;

  constructor(options: SongbrainOptions = {}) {
    this.apiKey = options.apiKey !== undefined ? options.apiKey || undefined : env("SONGBRAIN_API_KEY");
    this.baseUrl = (options.baseUrl ?? env("SONGBRAIN_BASE_URL") ?? DEFAULT_BASE_URL).replace(/\/+$/, "");
    this.timeoutMs = options.timeoutMs ?? 60_000;
    this.maxRetries = Math.max(0, options.maxRetries ?? 3);
    const f = options.fetch ?? (globalThis.fetch as typeof fetch | undefined);
    if (!f) throw new Error("No global fetch found. Use Node 18+ or pass `fetch` in the options.");
    this.fetchImpl = f;
  }

  // ── songs ────────────────────────────────────────────────────────────────

  /**
   * Analyse a song from a file or a public URL. Pass exactly one of `file` or `audioUrl`.
   * Typically 60-90 s. With `wait: true` (default) resolves to the full document;
   * with `wait: false` to the 202 body `{ id, status: "processing", eta_sec, billing }`.
   */
  analyze(options: AnalyzeOptions & { wait: false }): Promise<SongCreated>;
  analyze(options: AnalyzeOptions & { wait?: true }): Promise<Song>;
  analyze(options: AnalyzeOptions): Promise<Song | SongCreated>;
  async analyze(options: AnalyzeOptions): Promise<Song | SongCreated> {
    const { file, audioUrl } = options;
    if ((file === undefined) === (audioUrl === undefined)) {
      throw new TypeError("Pass exactly one of `file` or `audioUrl`.");
    }
    const fields: Record<string, string> = {};
    if (options.title !== undefined) fields.title = options.title;
    if (options.artist !== undefined) fields.artist = options.artist;
    if (options.webhookUrl !== undefined) fields.webhook_url = options.webhookUrl;
    if (options.externalRef !== undefined) fields.external_ref = options.externalRef;

    let created: SongCreated;
    if (audioUrl !== undefined) {
      created = await this.request<SongCreated>("POST", "/songs", { json: { audio_url: audioUrl, ...fields } });
    } else {
      const { blob, name } = await toUpload(file as FileInput, options.filename);
      created = await this.request<SongCreated>("POST", "/songs", {
        form: () => {
          const form = new FormData();
          form.append("file", blob, name);
          for (const [k, v] of Object.entries(fields)) form.append(k, v);
          return form;
        },
      });
    }
    if (options.wait === false) return created;
    return this.waitFor(created.id, {
      pollIntervalMs: options.pollIntervalMs,
      timeoutMs: options.timeoutMs,
    });
  }

  /** Poll GET /songs/{id} until the song is done. Throws `AnalysisFailed` or `WaitTimeout`. */
  async waitFor(songId: string, options: WaitOptions = {}): Promise<Song> {
    const timeoutMs = options.timeoutMs ?? 300_000;
    const interval = Math.max(500, options.pollIntervalMs ?? 5_000);
    const deadline = Date.now() + timeoutMs;
    for (;;) {
      const doc = await this.getSong(songId);
      if (doc.status === "done") return doc;
      if (doc.status === "failed") {
        throw new AnalysisFailed(
          songId,
          doc.error?.code ?? "analysis_failed",
          doc.error?.message ?? "The analysis failed. Paid credits were refunded automatically.",
          doc,
        );
      }
      const remaining = deadline - Date.now();
      if (remaining <= 0) throw new WaitTimeout(songId, timeoutMs);
      await this._sleep(Math.min(interval, remaining));
    }
  }

  /** Status while processing, then the full document. */
  getSong(songId: string, options: GetSongOptions = {}): Promise<Song> {
    return this.request<Song>("GET", `/songs/${encodeURIComponent(songId)}`, { query: docQuery(options) });
  }

  /** Only the story and the shot plan: `{ id, status, song, story, shot_plan }`. */
  shotPlan(songId: string): Promise<SongShotPlan> {
    return this.request<SongShotPlan>("GET", `/songs/${encodeURIComponent(songId)}/shot-plan`);
  }

  /** Your songs, newest first. `limit` is 1-100 (default 20). */
  listSongs(options: { limit?: number } = {}): Promise<SongList> {
    return this.request<SongList>("GET", "/songs", { query: { limit: String(options.limit ?? 20) } });
  }

  /** Delete a song's audio and analysis now. 409 `still_processing` while it runs. */
  deleteSong(songId: string): Promise<DeleteResult> {
    return this.request<DeleteResult>("DELETE", `/songs/${encodeURIComponent(songId)}`);
  }

  // ── account ──────────────────────────────────────────────────────────────

  /** Free songs left this month, credit balance and price per song. */
  account(): Promise<Account> {
    return this.request<Account>("GET", "/account");
  }

  /** Prices and limits. No key needed. */
  pricing(): Promise<Pricing> {
    return this.request<Pricing>("GET", "/pricing");
  }

  // ── examples (no key) ────────────────────────────────────────────────────

  /** Example analyses of Songbrain's own songs. No key needed. */
  examples(): Promise<ExampleList> {
    return this.request<ExampleList>("GET", "/examples");
  }

  /** A full example document, in the same format as `getSong`. No key needed. */
  example(exampleId: string, options: GetSongOptions = {}): Promise<Song> {
    return this.request<Song>("GET", `/examples/${encodeURIComponent(exampleId)}`, { query: docQuery(options) });
  }

  /** An example story and shot plan, in the same format as `shotPlan`. No key needed. */
  exampleShotPlan(exampleId: string): Promise<SongShotPlan> {
    return this.request<SongShotPlan>("GET", `/examples/${encodeURIComponent(exampleId)}/shot-plan`);
  }

  // ── internals ────────────────────────────────────────────────────────────

  private backoffMs(attempt: number): number {
    return Math.min(500 * 2 ** attempt, 8_000) + Math.random() * 250;
  }

  private async request<T>(
    method: "GET" | "POST" | "DELETE",
    path: string,
    opts: { query?: Record<string, string | undefined>; json?: Json; form?: () => FormData } = {},
  ): Promise<T> {
    const url = new URL(this.baseUrl + path);
    for (const [k, v] of Object.entries(opts.query ?? {})) if (v !== undefined) url.searchParams.set(k, v);
    const idempotent = method !== "POST";

    for (let attempt = 0; ; attempt++) {
      const headers: Record<string, string> = {
        Accept: "application/json",
        "User-Agent": `songbrain-js/${VERSION}`,
      };
      if (this.apiKey) headers.Authorization = `Bearer ${this.apiKey}`;
      let body: BodyInit | undefined;
      if (opts.json) {
        headers["Content-Type"] = "application/json";
        body = JSON.stringify(opts.json);
      } else if (opts.form) {
        body = opts.form(); // fresh FormData per attempt; fetch sets the boundary
      }

      let res: Response;
      try {
        res = await this.fetchImpl(url, { method, headers, body, signal: AbortSignal.timeout(this.timeoutMs) });
      } catch (err) {
        // Network errors and timeouts: only resend if nothing can have been created.
        if (idempotent && attempt < this.maxRetries) {
          await this._sleep(this.backoffMs(attempt));
          continue;
        }
        const message = err instanceof Error ? err.message : String(err);
        throw new SongbrainError(0, "connection_error", message);
      }

      if (res.ok) {
        const text = await res.text();
        if (!text) return {} as T;
        try {
          return JSON.parse(text) as T;
        } catch {
          throw new SongbrainError(res.status, "invalid_response", "Response is not JSON.");
        }
      }

      const error = await errorFrom(res);
      // 429 never started any work. For POST only retry gateway errors (502/503).
      const retryable =
        res.status === 429 || (res.status >= 500 && (idempotent || res.status === 502 || res.status === 503));
      if (retryable && attempt < this.maxRetries) {
        const after = error instanceof RateLimited ? error.retryAfter : null;
        const delayMs = after !== null ? after * 1000 : this.backoffMs(attempt);
        if (delayMs <= MAX_RETRY_WAIT_SEC * 1000) {
          await this._sleep(delayMs);
          continue;
        }
      }
      throw error;
    }
  }
}

function docQuery(options: GetSongOptions): Record<string, string | undefined> {
  const include = Array.isArray(options.include) ? options.include.join(",") : options.include;
  return { view: options.view, include };
}

async function errorFrom(res: Response): Promise<SongbrainError> {
  const text = await res.text().catch(() => "");
  let body: unknown;
  let code = `http_${res.status}`;
  let message = text.trim().slice(0, 500) || res.statusText || `HTTP ${res.status}`;
  try {
    body = JSON.parse(text);
  } catch {
    body = undefined;
  }
  if (body && typeof body === "object") {
    const err = (body as { error?: unknown }).error;
    if (err && typeof err === "object") {
      const e = err as { code?: unknown; message?: unknown };
      if (e.code) code = String(e.code);
      if (e.message) message = String(e.message);
    } else if ("detail" in (body as object)) {
      code = "validation_error";
      message = JSON.stringify((body as { detail: unknown }).detail);
    }
  }
  switch (res.status) {
    case 401:
      return new AuthenticationError(401, code, message, body);
    case 402:
      return new InsufficientCredits(402, code, message, body);
    case 404:
      return new NotFound(404, code, message, body);
    case 429:
      return new RateLimited(429, code, message, body, retryAfterSeconds(res.headers.get("Retry-After")));
    default:
      return new SongbrainError(res.status, code, message, body);
  }
}

async function toUpload(file: FileInput, filename?: string): Promise<{ blob: Blob; name: string }> {
  let blob: Blob;
  let sourceName: string | undefined;
  if (typeof file === "string") {
    const { readFile } = await import("node:fs/promises");
    const data = await readFile(file);
    blob = new Blob([data as BlobPart]);
    sourceName = baseName(file);
  } else if (file instanceof ArrayBuffer) {
    blob = new Blob([file]);
  } else if (file instanceof Uint8Array) {
    blob = new Blob([file as BlobPart]);
  } else if (typeof Blob !== "undefined" && file instanceof Blob) {
    blob = file;
    const n = (file as Blob & { name?: unknown }).name;
    if (typeof n === "string" && n) sourceName = baseName(n);
  } else {
    throw new TypeError("`file` must be a Blob, a Buffer/Uint8Array, an ArrayBuffer or a file path.");
  }

  let name = filename ?? sourceName;
  if (!name || !extOf(name)) {
    const head = new Uint8Array(await blob.slice(0, 16).arrayBuffer());
    const ext = sniffExtension(head);
    if (!ext) {
      throw new TypeError('Could not tell the audio format. Pass `filename` with an extension, e.g. filename: "song.mp3".');
    }
    name = `${(name ?? "song").replace(/\.$/, "")}.${ext}`;
  }
  const type = MIME[extOf(name)];
  if (type && !blob.type) blob = new Blob([blob], { type });
  return { blob, name };
}
