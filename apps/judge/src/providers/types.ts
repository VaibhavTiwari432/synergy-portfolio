export interface LLMProvider {
  readonly modelId: string;
  complete(prompt: string, maxTokens: number): Promise<string>;
}
