import { readFileSync } from "fs";
import { fileURLToPath } from "url";
import { dirname, join } from "path";
import { z } from "zod";
import { RubricAnchorSchema, type RubricAnchor } from "@synergy/schemas";

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

export function loadRubric(version: string): RubricAnchor[] {
  const filePath = join(__dirname, "..", `rubric_v${version}.json`);

  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(filePath, "utf8"));
  } catch (err) {
    throw new Error(
      `loadRubric: could not read rubric_v${version}.json at ${filePath}: ${String(err)}`,
    );
  }

  if (!Array.isArray(raw)) {
    throw new Error(`loadRubric: rubric_v${version}.json must be a JSON array`);
  }

  const anchors: RubricAnchor[] = [];
  for (let i = 0; i < raw.length; i++) {
    const result = RubricAnchorSchema.safeParse(raw[i]);
    if (!result.success) {
      const item = raw[i] as Record<string, unknown>;
      throw new Error(
        `loadRubric: anchor[${i}] (dimension=${String(item["dimension"])}, band=${String(item["band"])}) failed validation: ${result.error.message}`,
      );
    }
    anchors.push(result.data);
  }

  return anchors;
}
