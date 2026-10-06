import { test } from "node:test";
import assert from "node:assert/strict";
import { createHmac } from "node:crypto";
import { verifyWebhook, constructWebhookEvent, signWebhook } from "../dist/index.js";

const SECRET = "whsec_test_123";
const BODY = JSON.stringify({ type: "song.done", created: 1791200000, data: { id: "8f0c", status: "done" } });
const now = () => Math.floor(Date.now() / 1000);

function header(body = BODY, t = now(), secret = SECRET) {
  const v1 = createHmac("sha256", secret).update(`${t}.${body}`).digest("hex");
  return `t=${t},v1=${v1}`;
}

test("valid signature (string, Buffer, Uint8Array, ArrayBuffer body)", () => {
  const h = header();
  assert.equal(verifyWebhook(BODY, h, SECRET), true);
  const buf = Buffer.from(BODY);
  assert.equal(verifyWebhook(buf, h, SECRET), true);
  assert.equal(verifyWebhook(new Uint8Array(buf), h, SECRET), true);
  assert.equal(verifyWebhook(new TextEncoder().encode(BODY).buffer, h, SECRET), true);
});

test("tampered body and wrong secret fail", () => {
  assert.equal(verifyWebhook(BODY.replace("done", "fail"), header(), SECRET), false);
  assert.equal(verifyWebhook(BODY, header(), "other"), false);
});

test("old and future signatures fail, tolerance 0 disables the check", () => {
  const old = header(BODY, now() - 301);
  assert.equal(verifyWebhook(BODY, old, SECRET), false);
  assert.equal(verifyWebhook(BODY, old, SECRET, 0), true);
  assert.equal(verifyWebhook(BODY, header(BODY, now() - 200), SECRET), true);
  assert.equal(verifyWebhook(BODY, header(BODY, now() + 400), SECRET), false);
});

test("malformed headers fail without throwing", () => {
  for (const h of ["", "garbage", "t=abc,v1=00", `t=${now()}`, "v1=00", null, undefined]) {
    assert.equal(verifyWebhook(BODY, h, SECRET), false, String(h));
  }
});

test("spaces and several v1 values", () => {
  const good = header().split("v1=")[1];
  assert.equal(verifyWebhook(BODY, `t=${now()}, v1=deadbeef, v1=${good}`, SECRET), true);
});

test("signWebhook matches the documented scheme", () => {
  const t = 1791200000;
  assert.equal(signWebhook(BODY, SECRET, t), header(BODY, t));
});

test("constructWebhookEvent verifies and parses", () => {
  const event = constructWebhookEvent(BODY, header(), SECRET);
  assert.equal(event.type, "song.done");
  assert.equal(event.data.id, "8f0c");
  assert.throws(() => constructWebhookEvent(BODY, header(BODY, now(), "nope"), SECRET));
});
