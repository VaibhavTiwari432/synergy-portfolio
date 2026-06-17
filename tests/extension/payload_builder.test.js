"use strict";

const test = require("node:test");
const assert = require("node:assert/strict");

const {
  buildIngestPayload,
  normaliseSource,
} = require("../../extension/utils/payload_builder.js");

test("buildIngestPayload creates a dense API request and aligns telemetry", () => {
  const payload = buildIngestPayload(
    {
      userRef: "user-1",
      conversationId: "chat-1",
      source: "live_capture",
      partnerModel: { family: "google", model_id: "gpt-4o" },
      turns: [
        { role: "human", text: " First ", timestamp_ms: 10, turn_index: 9 },
        { role: "assistant", text: "" },
        { role: "ai", text: "Second", timestamp_ms: 20 },
      ],
      telemetry: {
        dwell_ms: [100, 200, 300],
        copy_events: [0, 9, 2],
        edit_detected: [false, true, true],
        selector_health: "ok",
      },
      metadata: { title: "Example" },
    },
    new Date("2026-06-14T12:00:00Z"),
  );

  assert.equal(payload.source, "chatgpt_live");
  assert.deepEqual(payload.partner_model, {
    family: "openai",
    model_id: "gpt-4o",
    era_key: "2026-06",
  });
  assert.deepEqual(payload.turns, [
    { role: "user", text: "First", timestamp_ms: 10, turn_index: 0 },
    { role: "assistant", text: "Second", timestamp_ms: 20, turn_index: 1 },
  ]);
  assert.deepEqual(payload.telemetry, {
    dwell_ms: [100, 300],
    copy_events: [0, 2],
    edit_detected: [false, true],
    selector_health: "ok",
  });
});

test("normaliseSource rejects unknown source values", () => {
  assert.equal(normaliseSource("history"), "chatgpt_history");
  assert.throws(() => normaliseSource("claude_live"), /unsupported capture source/);
});

test("incomplete dwell telemetry is omitted rather than represented as zero", () => {
  const payload = buildIngestPayload({
    user_ref: "user-1",
    conversation_id: "chat-1",
    turns: [{ role: "user", text: "Hello" }, { role: "assistant", text: "Hi" }],
    telemetry: { dwell_ms: [100] },
  });

  assert.equal(payload.telemetry, undefined);
});

test("incomplete copy and edit telemetry is omitted rather than fabricated", () => {
  const payload = buildIngestPayload({
    user_ref: "user-1",
    conversation_id: "chat-1",
    turns: [{ role: "user", text: "Hello" }, { role: "assistant", text: "Hi" }],
    telemetry: {
      copy_events: [1],
      edit_detected: [false, "false"],
      selector_health: "ok",
    },
  });

  assert.deepEqual(payload.telemetry, { selector_health: "ok" });
});

test("null timestamps and telemetry values are not coerced to zero", () => {
  const payload = buildIngestPayload({
    user_ref: "user-1",
    conversation_id: "chat-1",
    turns: [
      { role: "user", text: "Hello", timestamp_ms: null },
      { role: "assistant", text: "Hi", timestamp_ms: 20 },
    ],
    telemetry: {
      dwell_ms: [null, 200],
      copy_events: [null, 0],
    },
  });

  assert.equal(payload.turns[0].timestamp_ms, null);
  assert.equal(payload.telemetry, undefined);
});
