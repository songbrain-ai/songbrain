// Compile-time checks only (run by `npm run typecheck`, never executed).
import {
  Songbrain,
  SongbrainError,
  constructWebhookEvent,
  verifyWebhook,
  type RateLimitInfo,
  type Scene,
  type Song,
  type SongCreated,
  type SongList,
  type SongListItem,
  type WebhookDeliveryList,
  type WebhookTestResult,
} from "../src/index.js";

export async function typeChecks(sb: Songbrain): Promise<void> {
  const done: Song = await sb.analyze({ file: "song.mp3" });
  const created: SongCreated = await sb.analyze({ audioUrl: "https://example.com/a.mp3", wait: false });
  const scenes: Scene[] = done.shot_plan?.clip?.scenes ?? [];
  const first: number | undefined = scenes[0]?.start_sec;
  const id: string = created.id;
  const ok: boolean = verifyWebhook("{}", "t=1,v1=00", "secret");
  // @ts-expect-error  wait:false returns the 202 body, not the full document
  const wrong = created.song_dna;
  void [first, id, ok, wrong];

  const testSong: Song = await sb.analyze({ test: true, idempotencyKey: "job-1" });
  const live: boolean | undefined = testSong.livemode;
  const page: SongList = await sb.listSongs({ limit: 10, startingAfter: "abc" });
  const cursor: string | null | undefined = page.next_cursor;
  for await (const item of sb.iterSongs({ pageSize: 50 })) {
    const it: SongListItem = item;
    void it;
  }
  const ping: WebhookTestResult = await sb.testWebhook("https://example.com/hook");
  const deliveries: WebhookDeliveryList = await sb.webhookDeliveries({ limit: 5 });
  const rl: RateLimitInfo | null = sb.lastRateLimit;
  const rid: string | null = sb.lastRequestId;
  const event = constructWebhookEvent("{}", "t=1,v1=00", "secret");
  const eventId: string = event.id;
  const errId: string | null = new SongbrainError(400, "x", "y").requestId;
  void [live, cursor, ping, deliveries, rl, rid, eventId, errId];
}
