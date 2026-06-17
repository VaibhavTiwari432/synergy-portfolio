'use strict';

/**
 * utils/self_rating_prompt.js — client-side self-rating prompt template.
 * OWNER: Chief Engineer. Phase 4.
 *
 * This module is a companion to contracts/self_rating_prompt.txt.
 * The authoritative self-rating call is made server-side by
 * src/worker/self_rater.py (which reads the text file directly).
 *
 * This JS copy serves two purposes:
 *   1.  Lets the extension display the same prompt text to the user on
 *       request (transparency — user can see what was asked on their behalf).
 *   2.  Future path: if the extension ever needs to call OpenAI directly
 *       (without the worker), this is the single source for the prompt.
 *
 * Non-negotiable #10: self_rating_raw is NEVER shown to the user in any
 * form. This module only exposes the prompt template, not the result.
 *
 * IIFE pattern: attaches to globalScope.SAFSelfRatingPrompt.
 */

(function initSelfRatingPrompt(globalScope) {
  const SELF_RATING_PROMPT_VERSION = 'v1.0';

  /**
   * The prompt template sent to the user's own OpenAI key.
   * {transcript} is replaced with the conversation text by the caller.
   *
   * MUST match contracts/self_rating_prompt.txt exactly.
   * If this diverges, file a DISCREPANCY.md entry — do not silently patch.
   */
  const PROMPT_TEMPLATE = `You participated in the following conversation as the AI assistant.
Rate the HUMAN participant's collaborative behavior on these 8 dimensions,
each on a scale of 0.0 to 1.0.

Dimensions:
AL (AI Literacy): Does the human understand what AI can and cannot do?
PR (Prompt Reasoning): Does the human engineer prompts or just chat?
EC (Error Correction): Does the human verify and challenge your outputs?
ES (Ethics Sensitivity): Does the human show awareness of ethical implications?
CS (Contextual Synthesis): Does the human integrate your outputs with their own thinking?
CD (Creative Divergence): Does the human push beyond your suggestions?
AUI (Augmentation Instinct): Does the human use AI to extend capability, not replace effort?
CA (Collaborative Agency): Does the human maintain their own direction and judgment?

Return ONLY valid JSON in this exact format, no other text:
{
  "AL": 0.0, "PR": 0.0, "EC": 0.0, "ES": 0.0,
  "CS": 0.0, "CD": 0.0, "AUI": 0.0, "CA": 0.0,
  "confidence": 0.0,
  "evidence_notes": "one sentence"
}

[CONVERSATION TRANSCRIPT]
{transcript}`;

  /**
   * Build a ready-to-send prompt by substituting the transcript.
   * @param {string} transcript — formatted conversation text
   * @returns {string}
   */
  function buildPrompt(transcript) {
    if (typeof transcript !== 'string' || !transcript.trim()) {
      throw new TypeError('transcript must be a non-empty string');
    }
    return PROMPT_TEMPLATE.replace('{transcript}', transcript.trim());
  }

  /**
   * Format a list of turn objects into the plain-text transcript form
   * the prompt expects. Roles are mapped to "User:" / "Assistant:".
   * @param {Array<{role: string, text: string}>} turns
   * @returns {string}
   */
  function formatTurns(turns) {
    if (!Array.isArray(turns)) throw new TypeError('turns must be an array');
    return turns
      .map((t) => {
        const role = String(t?.role || '').toLowerCase();
        const label = (role === 'human' || role === 'user') ? 'User' : 'Assistant';
        const text = String(t?.text || '').trim();
        return text ? `${label}: ${text}` : null;
      })
      .filter(Boolean)
      .join('\n\n');
  }

  const api = Object.freeze({
    SELF_RATING_PROMPT_VERSION,
    PROMPT_TEMPLATE,
    buildPrompt,
    formatTurns,
  });

  globalScope.SAFSelfRatingPrompt = api;
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== 'undefined' ? globalThis : self);
