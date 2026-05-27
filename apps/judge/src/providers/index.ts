import type { JudgeConfig } from "../types.js";
import type { LLMProvider } from "./types.js";
import { createGeminiProvider } from "./gemini.js";
import { createAnthropicProvider } from "./anthropic.js";

export type { LLMProvider } from "./types.js";

/** Returns null in dry-run mode (provider is never called). */
export function createProvider(config: JudgeConfig): LLMProvider | null {
  if (config.dry_run) return null;
  if (config.provider === "gemini") return createGeminiProvider(config.default_model);
  return createAnthropicProvider(config.default_model);
}
