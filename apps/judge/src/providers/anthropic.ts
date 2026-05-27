import type { LLMProvider } from "./types.js";

// Stub — Anthropic provider is not active in Phase 1.
// Full two-pass implementation is preserved on the anthropic-judge branch.
export function createAnthropicProvider(_modelId: string): LLMProvider {
  throw new Error(
    "Anthropic provider is not active in Phase 1. " +
      "Set provider: 'gemini' in JudgeConfig, or switch to the anthropic-judge branch.",
  );
}
