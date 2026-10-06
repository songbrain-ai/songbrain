import { createHmac, timingSafeEqual } from "node:crypto";
import type { WebhookEvent } from "./types.js";

/** The header Songbrain signs webhooks with. */
export const SIGNATURE_HEADER = "Songbrain-Signature";

type RawBody = string | Uint8Array | ArrayBuffer;

function toBuffer(body: RawBody): Buffer {
  if (typeof body === "string") return Buffer.from(body, "utf8");
  if (body instanceof ArrayBuffer) return Buffer.from(new Uint8Array(body));
  return Buffer.from(body.buffer, body.byteOffset, body.byteLength);
}

function parseHeader(header: string): { t: number | null; v1: string[] } {
  let t: number | null = null;
  const v1: string[] = [];
  for (const part of header.split(",")) {
    const i = part.indexOf("=");
    if (i < 0) continue;
    const key = part.slice(0, i).trim();
    const value = part.slice(i + 1).trim();
    if (key === "t") {
      if (!/^\d+$/.test(value)) return { t: null, v1: [] };
      t = Number(value);
    } else if (key === "v1" && value) {
      v1.push(value.toLowerCase());
    }
  }
  return { t, v1 };
}

function mac(body: Buffer, t: number, secret: string): string {
  return createHmac("sha256", secret).update(`${t}.`).update(body).digest("hex");
}

/**
 * Check a `Songbrain-Signature: t=<unix>,v1=<hex>` header, where v1 is the
 * HMAC-SHA256 of `"<t>.<raw body>"` with your key's webhook secret.
 *
 * Pass the raw request body exactly as received, before any JSON parsing.
 * Returns false (never throws) for a missing, malformed, wrong or old signature.
 *
 * @param toleranceSec Maximum age in seconds (default 300). 0 disables the check.
 */
export function verifyWebhook(
  rawBody: RawBody,
  header: string | null | undefined,
  secret: string,
  toleranceSec = 300,
): boolean {
  if (!header || !secret) return false;
  const { t, v1 } = parseHeader(header);
  if (t === null || v1.length === 0) return false;
  if (toleranceSec > 0 && Math.abs(Date.now() / 1000 - t) > toleranceSec) return false;
  const expected = Buffer.from(mac(toBuffer(rawBody), t, secret), "utf8");
  return v1.some((sig) => {
    const given = Buffer.from(sig, "utf8");
    return given.length === expected.length && timingSafeEqual(given, expected);
  });
}

/**
 * Verify the signature and return the parsed event:
 * `{ id, type: "song.done" | "song.failed" | "account.low_balance" | "ping", created, livemode, data }`.
 * Throws if the signature is not valid.
 *
 * `id` (`evt_…`, also the `Songbrain-Event-Id` header) stays the same when
 * Songbrain retries an event (up to 10 attempts over about 3 days): store the
 * ids you have handled and skip repeats.
 */
export function constructWebhookEvent<T = Record<string, unknown>>(
  rawBody: RawBody,
  header: string | null | undefined,
  secret: string,
  toleranceSec = 300,
): WebhookEvent<T> {
  if (!verifyWebhook(rawBody, header, secret, toleranceSec)) {
    throw new Error("Invalid Songbrain-Signature");
  }
  return JSON.parse(toBuffer(rawBody).toString("utf8")) as WebhookEvent<T>;
}

/** Build a signature header value. Useful to test your webhook handler. */
export function signWebhook(rawBody: RawBody, secret: string, timestampSec = Math.floor(Date.now() / 1000)): string {
  return `t=${timestampSec},v1=${mac(toBuffer(rawBody), timestampSec, secret)}`;
}
