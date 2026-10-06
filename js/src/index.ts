/**
 * Songbrain: song in, video plan out.
 * The official client for the Songbrain API (https://www.songbrain.ai/docs/api).
 */
export { Songbrain, DEFAULT_BASE_URL } from "./client.js";
export type { SongbrainOptions, AnalyzeOptions, WaitOptions, GetSongOptions, FileInput } from "./client.js";
export {
  SongbrainError,
  AuthenticationError,
  InsufficientCredits,
  NotFound,
  RateLimited,
  AnalysisFailed,
  WaitTimeout,
} from "./errors.js";
export { verifyWebhook, constructWebhookEvent, signWebhook, SIGNATURE_HEADER } from "./webhooks.js";
export { VERSION } from "./version.js";
export type * from "./types.js";
