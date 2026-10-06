"""A minimal Songbrain webhook receiver (Flask) that verifies the signature.

    pip install songbrain flask
    export SONGBRAIN_API_KEY=sb_live_...
    export SONGBRAIN_WEBHOOK_SECRET=...   # shown once when you create the key
    python webhook_server.py              # listens on http://localhost:8080/songbrain

The URL has to be public for Songbrain to reach it (use a tunnel such as
ngrok or cloudflared while developing). Then start a song with:

    sb.analyze("song.mp3", webhook_url="https://<your-tunnel>/songbrain", wait=False)

Songbrain retries a failed delivery up to 10 times over about 3 days, always
with the same event id. Answer 2xx quickly and do slow work elsewhere.
Check the receiver with a signed ping: sb.test_webhook("https://<your-tunnel>/songbrain").
"""

import os

from flask import Flask, abort, request

from songbrain import Songbrain, webhooks

SECRET = os.environ.get("SONGBRAIN_WEBHOOK_SECRET", "")

app = Flask(__name__)
sb = Songbrain()
seen = set()  # event ids you have handled; use your database in production


@app.post("/songbrain")
def songbrain_webhook():
    raw = request.get_data()  # the raw bytes, before any JSON parsing
    header = request.headers.get(webhooks.SIGNATURE_HEADER)
    try:
        event = webhooks.construct_event(raw, header, SECRET)
    except (webhooks.WebhookVerificationError, ValueError):
        abort(400)

    data = event.get("data", {})
    # Retries deliver the same event (same id) again; handle each id once.
    if event["id"] in seen:
        return "", 200
    seen.add(event["id"])

    if event["type"] == "ping":
        print(f"ping {event['id']}")
    elif event["type"] == "song.done":
        plan = sb.shot_plan(data["id"])
        scenes = plan["shot_plan"]["clip"]["scenes"]
        print(f"song.done {data['id']} (ref {data.get('external_ref')}): {len(scenes)} scenes")
    elif event["type"] == "song.failed":
        print(f"song.failed {data['id']} (ref {data.get('external_ref')})")
    elif event["type"] == "account.low_balance":
        print(f"low balance: {data.get('songs_left')} songs left. Top up: {data.get('buy_credits_url')}")
    return "", 200


if __name__ == "__main__":
    if not SECRET:
        raise SystemExit("Set SONGBRAIN_WEBHOOK_SECRET first.")
    app.run(port=int(os.environ.get("PORT", "8080")))
