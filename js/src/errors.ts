/**
 * Every API error has the shape `{ error: { code, message, request_id } }`.
 * The client turns it into a `SongbrainError` (or a subclass) with `status`,
 * `code`, `message` and `requestId`. The message ends with
 * ` (request_id: req_…)` when there is one; quote it when you contact support.
 */
export class SongbrainError extends Error {
  /** HTTP status, or 0 when the error did not come from an HTTP response. */
  readonly status: number;
  /** Machine-readable code, e.g. "invalid_url" or "rate_limited". */
  readonly code: string;
  /** The parsed response body, when there was one. */
  readonly body: unknown;
  /** The `Songbrain-Request-Id` of the failed request (`req_…`), or null. */
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, body?: unknown, requestId: string | null = null) {
    super(requestId ? `${message} (request_id: ${requestId})` : message);
    this.name = new.target.name;
    this.status = status;
    this.code = code;
    this.body = body;
    this.requestId = requestId;
    Object.setPrototypeOf(this, new.target.prototype);
  }
}

/** 401: the API key is missing, invalid or revoked. */
export class AuthenticationError extends SongbrainError {}

/** 402: the free songs for this month are used up and the balance is below one song. */
export class InsufficientCredits extends SongbrainError {}

/** 404: unknown id, or the song belongs to another account. */
export class NotFound extends SongbrainError {}

/** 429: too many requests, too many songs in flight, daily cap or busy pipeline. */
export class RateLimited extends SongbrainError {
  /** Seconds to wait, from the Retry-After header (null if absent). */
  readonly retryAfter: number | null;

  constructor(
    status: number,
    code: string,
    message: string,
    body?: unknown,
    retryAfter: number | null = null,
    requestId: string | null = null,
  ) {
    super(status, code, message, body, requestId);
    this.retryAfter = retryAfter;
  }
}

/** The song was accepted but its analysis failed. Paid credits are refunded automatically. */
export class AnalysisFailed extends SongbrainError {
  readonly songId: string;

  constructor(songId: string, code: string, message: string, body?: unknown) {
    super(0, code, message, body);
    this.songId = songId;
  }
}

/** `analyze({ wait: true })` gave up before the song was done. It keeps processing on the server. */
export class WaitTimeout extends SongbrainError {
  readonly songId: string;

  constructor(songId: string, timeoutMs: number) {
    super(
      0,
      "wait_timeout",
      `Song ${songId} was not done after ${Math.round(timeoutMs / 1000)} s. It is still processing; fetch it later with getSong("${songId}").`,
    );
    this.songId = songId;
  }
}
