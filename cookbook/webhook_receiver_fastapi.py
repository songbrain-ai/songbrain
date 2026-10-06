"""A production-shaped Songbrain webhook receiver in FastAPI.

    pip install "songbrain>=0.2" fastapi uvicorn
    export SONGBRAIN_API_KEY=sb_live_...
    export SONGBRAIN_WEBHOOK_SECRET=...       # shown once when you create the key
    uvicorn webhook_receiver_fastapi:app --port 8080     # run from the cookbook/ folder
    # check it without Songbrain (needs httpx): python cookbook/webhook_receiver_fastapi.py --self-test

Then expose it (ngrok, cloudflared, …) and send a signed test event:

    from songbrain import Songbrain
    Songbrain().test_webhook("https://<your-tunnel>/songbrain")   # -> {"delivered": true, ...}

What it gets right:
1. Verifies `Songbrain-Signature` against the RAW body, before parsing JSON.
2. Dedupes on the event id (`evt_…`). Songbrain retries a delivery up to 10 times
   over ~3 days (anything but a 2xx counts as failed), always with the same id,
   so the same event can arrive twice. Ids live in SQLite here; use your database.
3. Answers 2xx fast and does slow work (fetching the shot plan, rendering) in the
   background. If recording the event fails, it answers 500 so Songbrain retries.
4. Handles ping, song.done, song.failed and account.low_balance; ignores unknown
   types with a 2xx (new event types can be added at any time).
"""

import logging
import os
import sqlite3
import sys
import threading
from typing import Any, Dict

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request

from songbrain import Songbrain, webhooks

SECRET = os.environ.get("SONGBRAIN_WEBHOOK_SECRET", "")
DB_PATH = os.environ.get("WEBHOOK_DB", "songbrain_events.sqlite3")

log = logging.getLogger("songbrain.webhooks")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

app = FastAPI()
sb = Songbrain()  # used to fetch results after song.done

_db_lock = threading.Lock()
_db = sqlite3.connect(DB_PATH, check_same_thread=False)
_db.execute("CREATE TABLE IF NOT EXISTS events (id TEXT PRIMARY KEY, type TEXT, received_at TEXT DEFAULT CURRENT_TIMESTAMP)")
_db.commit()


def first_time(event: Dict[str, Any]) -> bool:
    """Record the event id. False if it was handled before (a retry or a duplicate)."""
    with _db_lock:
        cur = _db.execute("INSERT OR IGNORE INTO events (id, type) VALUES (?, ?)", (event["id"], event.get("type")))
        _db.commit()
        return cur.rowcount == 1


def forget(event_id: str) -> None:
    with _db_lock:
        _db.execute("DELETE FROM events WHERE id = ?", (event_id,))
        _db.commit()


# ── what to do with each event (runs after the 2xx went out) ─────────────────


def on_song_done(data: Dict[str, Any], livemode: bool) -> None:
    song_id = data["id"]
    plan = sb.shot_plan(song_id)  # or sb.get_song(song_id) for the full document
    scenes = ((plan.get("shot_plan") or {}).get("clip") or {}).get("scenes") or []
    log.info("song.done %s ref=%s livemode=%s: %d scenes", song_id, data.get("external_ref"), livemode, len(scenes))
    # ... queue your render job here (see song_to_clips_fal.py) ...


def on_song_failed(data: Dict[str, Any]) -> None:
    err = data.get("error") or {}
    log.warning("song.failed %s ref=%s: %s %s", data.get("id"), data.get("external_ref"), err.get("code"), err.get("message"))


def on_low_balance(data: Dict[str, Any]) -> None:
    log.warning("account.low_balance: %s songs left, top up at %s", data.get("songs_left"), data.get("buy_credits_url"))


@app.post("/songbrain")
async def songbrain_webhook(request: Request, background: BackgroundTasks) -> Dict[str, Any]:
    raw = await request.body()  # the exact bytes Songbrain signed
    try:
        event = webhooks.construct_event(raw, request.headers.get(webhooks.SIGNATURE_HEADER), SECRET)
    except (webhooks.WebhookVerificationError, ValueError):
        raise HTTPException(status_code=400, detail="invalid signature")

    event_id = event.get("id") or request.headers.get("Songbrain-Event-Id")
    if not event_id:
        raise HTTPException(status_code=400, detail="event without id")
    event["id"] = event_id
    try:
        if not first_time(event):
            return {"ok": True, "duplicate": True}  # 2xx, so Songbrain stops retrying
    except sqlite3.Error:
        log.exception("could not record %s", event_id)
        raise HTTPException(status_code=500, detail="try again")  # Songbrain retries later

    etype, data, livemode = event.get("type"), event.get("data") or {}, bool(event.get("livemode", True))
    if etype == "ping":
        log.info("ping %s (livemode=%s)", event_id, livemode)
    elif etype == "song.done":
        background.add_task(on_song_done, data, livemode)
    elif etype == "song.failed":
        background.add_task(on_song_failed, data)
    elif etype == "account.low_balance":
        background.add_task(on_low_balance, data)
    else:
        log.info("ignoring unknown event type %s", etype)
    return {"ok": True}


def _self_test() -> None:
    """Sign a ping and a song.failed locally, post them twice and check the answers."""
    import json
    import time

    from fastapi.testclient import TestClient

    client = TestClient(app)
    for body in (
        {"id": f"evt_selftest_{int(time.time())}", "type": "ping", "created": int(time.time()), "livemode": False, "data": {}},
        {"id": f"evt_selftest_f_{int(time.time())}", "type": "song.failed", "created": int(time.time()), "livemode": False,
         "data": {"id": "test_0", "error": {"code": "decode_failed", "message": "self test"}}},
    ):
        raw = json.dumps(body).encode()
        headers = {webhooks.SIGNATURE_HEADER: webhooks.sign(raw, SECRET), "Content-Type": "application/json"}
        first = client.post("/songbrain", content=raw, headers=headers)
        again = client.post("/songbrain", content=raw, headers=headers)
        assert first.status_code == 200 and first.json() == {"ok": True}, first.text
        assert again.status_code == 200 and again.json().get("duplicate") is True, again.text
        forget(body["id"])
    bad = client.post("/songbrain", content=b"{}", headers={webhooks.SIGNATURE_HEADER: "t=1,v1=00"})
    assert bad.status_code == 400
    print("self-test ok: signature checked, duplicates answered 2xx without handling them twice")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        SECRET = SECRET or "whsec_selftest"
        _self_test()
    else:
        import uvicorn

        if not SECRET:
            raise SystemExit("Set SONGBRAIN_WEBHOOK_SECRET first.")
        uvicorn.run(app, port=int(os.environ.get("PORT", "8080")))
