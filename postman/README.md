# Postman collection

[`Songbrain.postman_collection.json`](Songbrain.postman_collection.json) (Collection v2.1) has every v1 endpoint: examples, songs (create from URL, upload, test mode), get, shot plan, list with cursor, delete, account, pricing, status, and webhook test ping and delivery log.

1. Postman → Import → pick the file.
2. Set the collection variable `apiKey` to your key (`sb_live_…`). Examples, Pricing and Status work without it.
3. Run **Songs → Create song (test mode)**, then **Get song**. Test mode is free and done right away.

- Auth is a bearer token at collection level; the no-key requests override it with "No Auth".
- Create requests send `Idempotency-Key: {{$guid}}`. Re-sending in Postman makes a new key; set a fixed value to try a replay.
- The create requests store the new id in `songId`; **List songs** stores `next_cursor` in `nextCursor` for the next page.

Prefer Bruno or Insomnia? Both import this file as it is; there is no separate collection to keep in sync.
