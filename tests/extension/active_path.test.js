"use strict";

/**
 * tests/extension/active_path.test.js — ADR-0007 / D-015 §2 active-path walk.
 *
 * activePathFromMapping(convo) reconstructs the displayed thread from ChatGPT's
 * conversation TREE: the single path from `current_node` to the root. The
 * load-bearing property is that an EDITED/forked conversation has multiple
 * branches in `mapping`, but only the active branch (the one ending at
 * current_node) is the thread the user sees — the alternate branch must never
 * leak into the captured transcript.
 */

const test = require("node:test");
const assert = require("node:assert/strict");

const { activePathFromMapping } = require("../../extension/content.js");

// A conversation that was forked at the assistant's first answer:
//   root → u1 → a1 ┬→ u2a → a2a   (ACTIVE: current_node = a2a)
//                  └→ u2b → a2b   (alternate branch — must be excluded)
function branchedConvo() {
  return {
    current_node: "a2a",
    mapping: {
      root: { parent: null, message: null }, // tree root carries no user/ai message
      u1: {
        parent: "root",
        message: {
          id: "u1",
          author: { role: "user" },
          content: { content_type: "text", parts: ["first question"] },
          create_time: 1,
        },
      },
      a1: {
        parent: "u1",
        message: {
          id: "a1",
          author: { role: "assistant" },
          content: { content_type: "text", parts: ["first answer"] },
          create_time: 2,
          metadata: { model_slug: "gpt-4o" },
        },
      },
      // ── active branch ──
      u2a: {
        parent: "a1",
        message: {
          id: "u2a",
          author: { role: "user" },
          content: { content_type: "text", parts: ["branch A question"] },
          create_time: 3,
        },
      },
      a2a: {
        parent: "u2a",
        message: {
          id: "a2a",
          author: { role: "assistant" },
          content: { content_type: "text", parts: ["branch A answer"] },
          create_time: 4,
          metadata: { model_slug: "gpt-4o-mini" },
        },
      },
      // ── alternate branch (NOT on the path to current_node) ──
      u2b: {
        parent: "a1",
        message: {
          id: "u2b",
          author: { role: "user" },
          content: { content_type: "text", parts: ["branch B question"] },
          create_time: 5,
        },
      },
      a2b: {
        parent: "u2b",
        message: {
          id: "a2b",
          author: { role: "assistant" },
          content: { content_type: "text", parts: ["branch B answer"] },
          create_time: 6,
        },
      },
    },
  };
}

test("active-path walk returns ONLY the active branch, in display order", () => {
  const result = activePathFromMapping(branchedConvo());

  assert.equal(result.complete, true);
  assert.equal(result.expected_turn_count, 4);

  // Exactly the root→current_node path, root reversed into display order; the tree
  // root (no message) is dropped, both alternate-branch turns are absent.
  assert.deepEqual(
    result.turns.map((t) => ({ role: t.role, text: t.text })),
    [
      { role: "user", text: "first question" },
      { role: "assistant", text: "first answer" },
      { role: "user", text: "branch A question" },
      { role: "assistant", text: "branch A answer" },
    ],
  );

  // The alternate branch must never appear.
  const allText = result.turns.map((t) => t.text);
  assert.ok(!allText.includes("branch B question"));
  assert.ok(!allText.includes("branch B answer"));

  // turn_index is a 0-based dense sequence over KEPT turns.
  assert.deepEqual(result.turns.map((t) => t.turn_index), [0, 1, 2, 3]);

  // §5: model_slug is the last assistant on the active path; create_time → ms.
  assert.equal(result.model_slug, "gpt-4o-mini");
  assert.deepEqual(result.turns.map((t) => t.timestamp_ms), [1000, 2000, 3000, 4000]);
});

test("system/tool turns and hidden messages are dropped, not counted", () => {
  const convo = branchedConvo();
  // Insert a hidden system node between u1 and a1 on the active path.
  convo.mapping.u1.parent = "sys";
  convo.mapping.sys = {
    parent: "root",
    message: {
      id: "sys",
      author: { role: "system" },
      content: { content_type: "text", parts: ["you are a helpful assistant"] },
      create_time: 0,
    },
  };
  // Mark a1 visually hidden — it must be excluded even though it is on the path.
  convo.mapping.a1.message.metadata.is_visually_hidden_from_conversation = true;

  const result = activePathFromMapping(convo);
  assert.equal(result.complete, true);
  assert.deepEqual(
    result.turns.map((t) => t.text),
    ["first question", "branch A question", "branch A answer"],
  );
});

test("non-text content (e.g. multimodal) is skipped", () => {
  const convo = branchedConvo();
  convo.mapping.a2a.message.content = {
    content_type: "multimodal_text",
    parts: [{ asset_pointer: "file-service://img" }],
  };
  const result = activePathFromMapping(convo);
  // a2a drops out; the path is still complete with the remaining text turns.
  assert.deepEqual(
    result.turns.map((t) => t.text),
    ["first question", "first answer", "branch A question"],
  );
});

test("fail-closed: missing current_node yields complete=false, no turns", () => {
  const convo = branchedConvo();
  delete convo.current_node;
  const result = activePathFromMapping(convo);
  assert.equal(result.complete, false);
  assert.equal(result.reason, "no_current_node");
  assert.deepEqual(result.turns, []);
});

test("fail-closed: a parent pointing at a missing node is a broken chain", () => {
  const convo = branchedConvo();
  convo.mapping.u1.parent = "ghost"; // ghost not in mapping
  const result = activePathFromMapping(convo);
  assert.equal(result.complete, false);
  assert.equal(result.reason, "broken_chain");
  assert.deepEqual(result.turns, []);
});

test("fail-closed: missing mapping yields complete=false", () => {
  const result = activePathFromMapping({ current_node: "a2a" });
  assert.equal(result.complete, false);
  assert.equal(result.reason, "no_mapping");
});

test("fail-closed: a path with zero visible turns is not a complete capture", () => {
  const convo = {
    current_node: "only",
    mapping: { only: { parent: null, message: { author: { role: "system" }, content: { content_type: "text", parts: ["sys"] } } } },
  };
  const result = activePathFromMapping(convo);
  assert.equal(result.complete, false);
  assert.equal(result.reason, "no_visible_turns");
});
