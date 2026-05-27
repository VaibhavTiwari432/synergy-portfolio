import { GoogleGenerativeAI, type GenerationConfig } from "@google/generative-ai";
import type { LLMProvider } from "./types.js";

export function createGeminiProvider(modelId: string): LLMProvider {
  const apiKey = process.env["GEMINI_API_KEY"];
  if (!apiKey) throw new Error("GEMINI_API_KEY env var not set — get one at aistudio.google.com");

  const genAI = new GoogleGenerativeAI(apiKey);
  const model = genAI.getGenerativeModel({ model: modelId });

  return {
    modelId,
    async complete(prompt: string, maxTokens: number): Promise<string> {
      const result = await model.generateContent({
        contents: [{ role: "user", parts: [{ text: prompt }] }],
        // thinkingConfig not yet in the 0.21.x type definitions, hence the cast.
        // thinkingBudget:0 disables thinking so the maxOutputTokens budget is
        // not consumed by chain-of-thought before the JSON can be written.
        generationConfig: {
          maxOutputTokens: maxTokens,
          thinkingConfig: { thinkingBudget: 0 },
        } as GenerationConfig,
      });
      const usage = result.response.usageMetadata;
      if (usage) {
        process.stderr.write(
          `  [tokens] prompt=${usage.promptTokenCount ?? "?"} output=${usage.candidatesTokenCount ?? "?"} total=${usage.totalTokenCount ?? "?"}\n`,
        );
      }
      return result.response.text();
    },
  };
}
