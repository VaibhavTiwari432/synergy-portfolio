'use strict';

/**
 * extension/tests/self_rating_prompt.test.js
 * Run: node --test extension/tests/self_rating_prompt.test.js
 */

const { test } = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');

const srp = require(path.resolve(__dirname, '../utils/self_rating_prompt.js'));

test('SELF_RATING_PROMPT_VERSION is v1.0', () => {
  assert.equal(srp.SELF_RATING_PROMPT_VERSION, 'v1.0');
});

test('PROMPT_TEMPLATE contains {transcript} placeholder', () => {
  assert.ok(srp.PROMPT_TEMPLATE.includes('{transcript}'));
});

test('PROMPT_TEMPLATE contains all 8 dimension codes', () => {
  for (const dim of ['AL', 'PR', 'EC', 'ES', 'CS', 'CD', 'AUI', 'CA']) {
    assert.ok(srp.PROMPT_TEMPLATE.includes(dim), `Missing dimension ${dim}`);
  }
});

test('PROMPT_TEMPLATE never contains forbidden words', () => {
  const lower = srp.PROMPT_TEMPLATE.toLowerCase();
  for (const word of ['synergy', 'surrender', 'dependent', 'decline']) {
    assert.ok(!lower.includes(word), `Forbidden word "${word}" found in prompt`);
  }
});

test('buildPrompt: substitutes transcript', () => {
  const transcript = 'User: hello\nAssistant: hi there';
  const result = srp.buildPrompt(transcript);
  assert.ok(result.includes(transcript));
  assert.ok(!result.includes('{transcript}'));
});

test('buildPrompt: throws on empty transcript', () => {
  assert.throws(() => srp.buildPrompt(''), TypeError);
  assert.throws(() => srp.buildPrompt('   '), TypeError);
  assert.throws(() => srp.buildPrompt(null), TypeError);
});

test('formatTurns: produces User/Assistant labels', () => {
  const turns = [
    { role: 'human', text: 'question' },
    { role: 'ai', text: 'answer' },
  ];
  const result = srp.formatTurns(turns);
  assert.ok(result.includes('User: question'));
  assert.ok(result.includes('Assistant: answer'));
});

test('formatTurns: user/assistant roles also work', () => {
  const turns = [
    { role: 'user', text: 'q' },
    { role: 'assistant', text: 'a' },
  ];
  const result = srp.formatTurns(turns);
  assert.ok(result.includes('User: q'));
  assert.ok(result.includes('Assistant: a'));
});

test('formatTurns: empty-text turns are skipped', () => {
  const turns = [
    { role: 'user', text: '' },
    { role: 'assistant', text: 'response' },
  ];
  const result = srp.formatTurns(turns);
  assert.ok(!result.includes('User:'));
  assert.ok(result.includes('Assistant: response'));
});

test('formatTurns: throws on non-array', () => {
  assert.throws(() => srp.formatTurns('not an array'), TypeError);
  assert.throws(() => srp.formatTurns(null), TypeError);
});

test('buildPrompt on formatTurns output produces complete prompt', () => {
  const turns = [
    { role: 'human', text: 'Can you help me with X?' },
    { role: 'ai', text: 'Sure! Here is how...' },
  ];
  const transcript = srp.formatTurns(turns);
  const prompt = srp.buildPrompt(transcript);
  assert.ok(prompt.includes('Can you help me with X?'));
  assert.ok(prompt.includes('Sure! Here is how...'));
  assert.ok(!prompt.includes('{transcript}'));
});
