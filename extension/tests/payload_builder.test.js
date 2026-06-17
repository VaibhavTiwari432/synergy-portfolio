'use strict';

/**
 * extension/tests/payload_builder.test.js
 * Run: node --test extension/tests/payload_builder.test.js
 *
 * Tests for SAFPayloadBuilder — the only extension utility with no browser deps.
 */

const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

// Load the IIFE; it attaches to globalThis.SAFPayloadBuilder and also sets module.exports
const pb = require(path.resolve(__dirname, '../utils/payload_builder.js'));

// ── buildIngestPayload ─────────────────────────────────────────────────────────

test('buildIngestPayload: minimal valid input', () => {
  const now = new Date('2025-01-15T10:00:00Z');
  const result = pb.buildIngestPayload({
    user_ref: 'alice',
    conversation_id: 'conv-001',
    source: 'chatgpt_live',
    turns: [
      { role: 'user', text: 'Hello AI' },
      { role: 'assistant', text: 'Hello human' },
    ],
  }, now);

  assert.equal(result.user_ref, 'alice');
  assert.equal(result.conversation_id, 'conv-001');
  assert.equal(result.source, 'chatgpt_live');
  assert.equal(result.partner_model.family, 'openai');
  assert.equal(result.partner_model.model_id, 'unknown');
  assert.equal(result.partner_model.era_key, '2025-01');
  assert.equal(result.turns.length, 2);
  assert.equal(result.turns[0].role, 'user');
  assert.equal(result.turns[1].role, 'assistant');
  assert.equal(result.turns[0].turn_index, 0);
  assert.equal(result.turns[1].turn_index, 1);
});

test('buildIngestPayload: source "history" normalises to chatgpt_history', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'bob',
    conversation_id: 'c2',
    source: 'history',
    turns: [{ role: 'user', text: 'hi' }],
  });
  assert.equal(payload.source, 'chatgpt_history');
});

test('buildIngestPayload: source "live" normalises to chatgpt_live', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'bob',
    conversation_id: 'c3',
    source: 'live',
    turns: [{ role: 'human', text: 'hi' }],
  });
  assert.equal(payload.source, 'chatgpt_live');
});

test('buildIngestPayload: human/ai roles pass through to user/assistant', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c4',
    source: 'live',
    turns: [
      { role: 'human', text: 'question' },
      { role: 'ai', text: 'answer' },
    ],
  });
  assert.equal(payload.turns[0].role, 'user');
  assert.equal(payload.turns[1].role, 'assistant');
});

test('buildIngestPayload: empty-text turns are dropped', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c5',
    source: 'live',
    turns: [
      { role: 'user', text: '' },
      { role: 'user', text: '   ' },
      { role: 'assistant', text: 'answer' },
    ],
  });
  assert.equal(payload.turns.length, 1);
  assert.equal(payload.turns[0].text, 'answer');
});

test('buildIngestPayload: throws if no valid turns', () => {
  assert.throws(() => {
    pb.buildIngestPayload({
      user_ref: 'u',
      conversation_id: 'c6',
      source: 'live',
      turns: [{ role: 'user', text: '' }],
    });
  }, { message: /at least one non-empty turn/ });
});

test('buildIngestPayload: throws if user_ref missing', () => {
  assert.throws(() => {
    pb.buildIngestPayload({
      conversation_id: 'c7',
      source: 'live',
      turns: [{ role: 'user', text: 'hi' }],
    });
  }, TypeError);
});

test('buildIngestPayload: partner_model.family is always "openai"', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c8',
    source: 'live',
    partner_model: { family: 'anthropic', model_id: 'claude-3', era_key: '2025-01' },
    turns: [{ role: 'user', text: 'hi' }],
  });
  // family is hardcoded to "openai" regardless of input (non-negotiable)
  assert.equal(payload.partner_model.family, 'openai');
});

test('buildIngestPayload: turn_index is assigned sequentially after filtering', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c9',
    source: 'live',
    turns: [
      { role: 'user', text: 'a' },
      { role: 'user', text: '' },         // dropped
      { role: 'assistant', text: 'b' },
    ],
  });
  assert.equal(payload.turns.length, 2);
  assert.equal(payload.turns[0].turn_index, 0);
  assert.equal(payload.turns[1].turn_index, 1);
});

test('buildIngestPayload: telemetry normalised from valid arrays', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c10',
    source: 'live',
    turns: [
      { role: 'user', text: 'a' },
      { role: 'assistant', text: 'b' },
    ],
    telemetry: {
      dwell_ms: [1000, 2000],
      copy_events: [0, 1],
      edit_detected: [false, true],
      selector_health: 'ok',
    },
  });
  assert.ok(payload.telemetry);
  assert.deepEqual(payload.telemetry.dwell_ms, [1000, 2000]);
  assert.deepEqual(payload.telemetry.copy_events, [0, 1]);
  assert.deepEqual(payload.telemetry.edit_detected, [false, true]);
  assert.equal(payload.telemetry.selector_health, 'ok');
});

test('buildIngestPayload: null measurements are not coerced to zero', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'null-values',
    source: 'live',
    turns: [
      { role: 'user', text: 'a', timestamp_ms: null },
      { role: 'assistant', text: 'b', timestamp_ms: 20 },
    ],
    telemetry: {
      dwell_ms: [null, 200],
      copy_events: [null, 0],
    },
  });

  assert.equal(payload.turns[0].timestamp_ms, null);
  assert.equal(payload.telemetry, undefined);
});

test('buildIngestPayload: metadata passes through', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c11',
    source: 'live',
    turns: [{ role: 'user', text: 'hi' }],
    metadata: { title: 'My Chat', url: 'https://chat.openai.com/c/abc', openai_api_key: 'sk-x' },
  });
  assert.equal(payload.metadata.title, 'My Chat');
  assert.equal(payload.metadata.openai_api_key, 'sk-x');
});

test('buildIngestPayload: era_key derived from now if not provided', () => {
  const now = new Date('2026-03-01T00:00:00Z');
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'c12',
    source: 'live',
    turns: [{ role: 'user', text: 'hi' }],
  }, now);
  assert.equal(payload.partner_model.era_key, '2026-03');
});

test('buildIngestPayload: conversationId camelCase alias accepted', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversationId: 'camel-case-id',
    source: 'live',
    turns: [{ role: 'user', text: 'hi' }],
  });
  assert.equal(payload.conversation_id, 'camel-case-id');
});

test('buildIngestPayload: userRef camelCase alias accepted', () => {
  const payload = pb.buildIngestPayload({
    userRef: 'alice',
    conversation_id: 'c-ref',
    source: 'live',
    turns: [{ role: 'user', text: 'hi' }],
  });
  assert.equal(payload.user_ref, 'alice');
});

test('buildIngestPayload: capture completeness fields pass through', () => {
  const payload = pb.buildIngestPayload({
    user_ref: 'u',
    conversation_id: 'capture-fields',
    source: 'live',
    turns: [{ role: 'user', text: 'hi' }],
    capture_method: 'dom_scroll_full_load',
    expected_turn_count: 1,
    captured_turn_count: 1,
    capture_complete: true,
    raw_retention_flag: 'retain_30d',
  });
  assert.equal(payload.capture_method, 'dom_scroll_full_load');
  assert.equal(payload.expected_turn_count, 1);
  assert.equal(payload.captured_turn_count, 1);
  assert.equal(payload.capture_complete, true);
  assert.equal(payload.raw_retention_flag, 'retain_30d');
});

// ── normaliseSource ────────────────────────────────────────────────────────────

test('normaliseSource: all known aliases', () => {
  const cases = [
    ['history', 'chatgpt_history'],
    ['history_import', 'chatgpt_history'],
    ['chatgpt_history', 'chatgpt_history'],
    ['live', 'chatgpt_live'],
    ['live_capture', 'chatgpt_live'],
    ['chatgpt_live', 'chatgpt_live'],
  ];
  for (const [input, expected] of cases) {
    assert.equal(pb.normaliseSource(input), expected, `source "${input}" should normalise to "${expected}"`);
  }
});

test('normaliseSource: unknown source throws', () => {
  assert.throws(() => pb.normaliseSource('claude_export'), TypeError);
  assert.throws(() => pb.normaliseSource('unknown'), TypeError);
});
