// Compile-time checks only (run by `npm run typecheck`, never executed).
import { Songbrain, verifyWebhook, type Scene, type Song, type SongCreated } from "../src/index.js";

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
}
