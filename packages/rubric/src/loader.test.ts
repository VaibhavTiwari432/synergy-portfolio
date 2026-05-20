import { describe, it, expect } from "vitest";
import { loadRubric } from "./loader.js";
import { DIMENSION_CODES } from "@synergy/schemas";

describe("loadRubric", () => {
  it("returns exactly 24 anchors with no validation errors", () => {
    const anchors = loadRubric("0.1");
    expect(anchors).toHaveLength(24);
  });

  it("covers all 8 dimensions", () => {
    const anchors = loadRubric("0.1");
    for (const code of DIMENSION_CODES) {
      const forDim = anchors.filter((a) => a.dimension === code);
      expect(forDim).toHaveLength(3);
    }
  });

  it("has exactly one low, mid, and high anchor per dimension", () => {
    const anchors = loadRubric("0.1");
    for (const code of DIMENSION_CODES) {
      const forDim = anchors.filter((a) => a.dimension === code);
      const bands = forDim.map((a) => a.band).sort();
      expect(bands).toEqual(["high", "low", "mid"]);
    }
  });

  it("every anchor has non-empty signals arrays", () => {
    const anchors = loadRubric("0.1");
    for (const anchor of anchors) {
      expect(anchor.positive_signals.length).toBeGreaterThan(0);
      expect(anchor.negative_signals.length).toBeGreaterThan(0);
    }
  });

  it("every anchor is marked synthetic", () => {
    const anchors = loadRubric("0.1");
    for (const anchor of anchors) {
      expect(anchor.synthetic).toBe(true);
    }
  });

  it("throws a clear error for unknown version", () => {
    expect(() => loadRubric("99.9")).toThrow(/rubric_v99\.9\.json/);
  });
});
