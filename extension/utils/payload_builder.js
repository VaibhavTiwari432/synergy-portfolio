"use strict";

(function initPayloadBuilder(globalScope) {
  const SOURCE_MAP = Object.freeze({
    history: "chatgpt_history",
    history_import: "chatgpt_history",
    chatgpt_history: "chatgpt_history",
    live: "chatgpt_live",
    live_capture: "chatgpt_live",
    chatgpt_live: "chatgpt_live",
  });

  const ROLE_MAP = Object.freeze({
    human: "user",
    user: "user",
    ai: "assistant",
    assistant: "assistant",
  });

  function requireString(value, field) {
    if (typeof value !== "string" || !value.trim()) {
      throw new TypeError(`${field} must be a non-empty string`);
    }
    return value.trim();
  }

  function normaliseSource(source) {
    const mapped = SOURCE_MAP[String(source || "live").toLowerCase()];
    if (!mapped) {
      throw new TypeError(`unsupported capture source: ${source}`);
    }
    return mapped;
  }

  function normaliseTimestamp(value) {
    if (value === null || value === undefined || value === "") return null;
    const timestamp = Number(value);
    return Number.isFinite(timestamp) && timestamp >= 0
      ? Math.trunc(timestamp)
      : null;
  }

  function normaliseTurns(turns) {
    if (!Array.isArray(turns)) {
      throw new TypeError("turns must be an array");
    }

    return turns.reduce((result, turn, sourceIndex) => {
      const role = ROLE_MAP[String(turn?.role || "").toLowerCase()];
      const text = typeof turn?.text === "string" ? turn.text.trim() : "";
      if (!role || !text) return result;

      result.push({
        role,
        text,
        timestamp_ms: normaliseTimestamp(turn.timestamp_ms ?? turn.timestamp),
        turn_index: result.length,
        _sourceIndex: sourceIndex,
      });
      return result;
    }, []);
  }

  function validInteger(value) {
    if (value === null || value === undefined || value === "") return null;
    const number = Number(value);
    return Number.isFinite(number) && number >= 0 ? Math.trunc(number) : null;
  }

  function mapCompleteIntegerArray(values, sourceIndices) {
    if (!Array.isArray(values)) return undefined;
    const mapped = sourceIndices.map((index) => validInteger(values[index]));
    return mapped.every((value) => value !== null) ? mapped : undefined;
  }

  function mapCompleteBooleanArray(values, sourceIndices) {
    if (!Array.isArray(values)) return undefined;
    const mapped = sourceIndices.map((index) => values[index]);
    return mapped.every((value) => typeof value === "boolean") ? mapped : undefined;
  }

  function normaliseTelemetry(telemetry, sourceIndices) {
    if (!telemetry || typeof telemetry !== "object") return undefined;

    const result = {};
    const dwell = mapCompleteIntegerArray(telemetry.dwell_ms, sourceIndices);
    const copies = mapCompleteIntegerArray(telemetry.copy_events, sourceIndices);
    const edits = mapCompleteBooleanArray(telemetry.edit_detected, sourceIndices);

    if (dwell) result.dwell_ms = dwell;
    if (copies) result.copy_events = copies;
    if (edits) result.edit_detected = edits;
    if (
      typeof telemetry.selector_health === "string" &&
      telemetry.selector_health.trim()
    ) {
      result.selector_health = telemetry.selector_health.trim();
    }

    return Object.keys(result).length ? result : undefined;
  }

  function currentEraKey(now = new Date()) {
    return now.toISOString().slice(0, 7);
  }

  function normalisePartnerModel(partnerModel, now) {
    const model = partnerModel && typeof partnerModel === "object" ? partnerModel : {};
    const eraKey = /^(\d{4}-\d{2}|unknown)$/.test(String(model.era_key || ""))
      ? String(model.era_key)
      : currentEraKey(now);
    const family = ["anthropic", "openai", "google", "unknown"].includes(
      String(model.family || "").toLowerCase(),
    )
      ? String(model.family).toLowerCase()
      : "openai";

    return {
      family,
      model_id:
        typeof model.model_id === "string" && model.model_id.trim()
          ? model.model_id.trim()
          : "unknown",
      era_key: eraKey,
    };
  }

  function normaliseMetadata(metadata) {
    if (!metadata || typeof metadata !== "object" || Array.isArray(metadata)) {
      return undefined;
    }
    return { ...metadata };
  }

  function buildIngestPayload(input, now = new Date()) {
    if (!input || typeof input !== "object") {
      throw new TypeError("payload input must be an object");
    }

    const turnsWithIndices = normaliseTurns(input.turns);
    if (!turnsWithIndices.length) {
      throw new TypeError("at least one non-empty turn is required");
    }

    const sourceIndices = turnsWithIndices.map((turn) => turn._sourceIndex);
    const turns = turnsWithIndices.map(({ _sourceIndex, ...turn }) => turn);
    const telemetry = normaliseTelemetry(input.telemetry, sourceIndices);
    const metadata = normaliseMetadata(input.metadata);

    const payload = {
      user_ref: requireString(input.user_ref ?? input.userRef, "user_ref"),
      conversation_id: requireString(
        input.conversation_id ?? input.conversationId,
        "conversation_id",
      ),
      source: normaliseSource(input.source),
      partner_model: normalisePartnerModel(
        input.partner_model ?? input.partnerModel,
        now,
      ),
      turns,
    };

    if (telemetry) payload.telemetry = telemetry;
    if (metadata) payload.metadata = metadata;
    if (typeof input.capture_method === "string" && input.capture_method.trim()) {
      payload.capture_method = input.capture_method.trim();
    }
    const expectedTurnCount = validInteger(input.expected_turn_count ?? input.expectedTurnCount);
    if (expectedTurnCount !== null) payload.expected_turn_count = expectedTurnCount;
    // Always derive captured_turn_count from the normalised turns array, not the
    // client-provided scalar. normaliseTurns may drop empty-text turns, making the
    // client scalar stale → reconcile_captured_count would throw a 422.
    payload.captured_turn_count = turns.length;
    if (typeof input.capture_complete === "boolean") {
      payload.capture_complete = input.capture_complete;
    }
    if (typeof input.raw_retention_flag === "string" && input.raw_retention_flag.trim()) {
      payload.raw_retention_flag = input.raw_retention_flag.trim();
    }
    return payload;
  }

  const api = Object.freeze({
    SOURCE_MAP,
    ROLE_MAP,
    buildIngestPayload,
    normalisePartnerModel,
    normaliseSource,
    normaliseTelemetry,
    normaliseTurns,
  });

  globalScope.SAFPayloadBuilder = api;
  if (typeof module !== "undefined" && module.exports) {
    module.exports = api;
  }
})(typeof globalThis !== "undefined" ? globalThis : self);
