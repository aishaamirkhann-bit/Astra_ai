import assert from "node:assert/strict";
import test from "node:test";
import { flushVoiceEvents, interruptVoiceOutput, parseVoiceEvent, sendVoiceTranscript } from "./voiceStream.mjs";

test("transcript events queue while the websocket connects, then flush in order", () => {
  const pending = [];
  const sent = [];
  const socket = { readyState: 0, send: (message) => sent.push(JSON.parse(message)) };
  sendVoiceTranscript(socket, pending, "laal shirt", false);
  sendVoiceTranscript(socket, pending, "laal shirt", true);
  assert.equal(pending.length, 2);
  socket.readyState = 1;
  flushVoiceEvents(socket, pending);
  assert.deepEqual(sent.map((event) => event.final), [false, true]);
});

test("barge-in cancels local speech immediately and signals the websocket", () => {
  let cancelled = false;
  const sent = [];
  interruptVoiceOutput({ readyState: 1, send: (message) => sent.push(JSON.parse(message)) }, { cancel: () => { cancelled = true; } });
  assert.equal(cancelled, true);
  assert.deepEqual(sent, [{ type: "interrupt" }]);
});

test("malformed websocket events are ignored", () => {
  assert.equal(parseVoiceEvent("{"), null);
  assert.deepEqual(parseVoiceEvent('{"type":"interrupted"}'), { type: "interrupted" });
});
