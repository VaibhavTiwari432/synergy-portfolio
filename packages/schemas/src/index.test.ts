import { describe, it, expect } from "vitest";
import {
  BAND_THRESHOLDS,
  DIMENSION_CODES,
  deriveBand,
  DimensionCodeSchema,
  RubricAnchorSchema,
  TurnSchema,
  TaskFrameSchema,
  DimensionScoreSchema,
  JudgeOutputSchema,
  AggregatedScoreSchema,
  PortfolioSchema,
  GoldChatAnnotationSchema,
  GoldChatSchema,
} from "./index.js";

// ── Fixtures ──────────────────────────────────────────────────────────────────

function makeScore(delta: number | null) {
  if (delta === null) {
    return {
      delta: null,
      band: "not_applicable",
      evidence_quote: null,
      evidence_turn_index: null,
      confidence: 0.9,
      rationale: "No applicable content in this frame.",
    };
  }
  return {
    delta,
    band: deriveBand(delta),
    evidence_quote: "User said: 'flag anything uncertain'",
    evidence_turn_index: 0,
    confidence: 0.85,
    rationale: "User explicitly requested uncertainty flags.",
  };
}

function allDimScores(delta: number | null = 0.5) {
  return Object.fromEntries(DIMENSION_CODES.map((k) => [k, makeScore(delta)]));
}

function allBands(band: "low" | "mid" | "high" | "not_applicable" = "mid") {
  return Object.fromEntries(DIMENSION_CODES.map((k) => [k, band]));
}

function allNotes(note = "Scored per rubric.") {
  return Object.fromEntries(DIMENSION_CODES.map((k) => [k, note]));
}

const VALID_ANNOTATION = {
  scorer_id: "sangillence",
  bands: allBands("mid"),
  notes: allNotes(),
  scored_at: "2026-05-20T10:00:00Z",
};

const VALID_TURNS = [
  { role: "user", content: "Help me plan my career.", turn_index: 0, timestamp_ms: null },
  { role: "assistant", content: "Sure, here's a roadmap.", turn_index: 1, timestamp_ms: null },
];

const VALID_FRAME = {
  id: "123e4567-e89b-12d3-a456-426614174000",
  chat_id: "chat-abc",
  platform: "claude.ai",
  user_id: "user-1",
  turns: VALID_TURNS,
  chunk_index: 0,
  captured_at: "2026-05-20T10:00:00Z",
  rubric_version: "0.1",
};

// ── deriveBand ────────────────────────────────────────────────────────────────

describe("deriveBand", () => {
  it("returns 'low' at and below LOW_MAX", () => {
    expect(deriveBand(BAND_THRESHOLDS.LOW_MAX)).toBe("low");
    expect(deriveBand(-2.0)).toBe("low");
    expect(deriveBand(-0.68)).toBe("low");
  });

  it("returns 'high' at and above HIGH_MIN", () => {
    expect(deriveBand(BAND_THRESHOLDS.HIGH_MIN)).toBe("high");
    expect(deriveBand(2.0)).toBe("high");
    expect(deriveBand(0.68)).toBe("high");
  });

  it("returns 'mid' in the open interval between thresholds", () => {
    expect(deriveBand(0.0)).toBe("mid");
    expect(deriveBand(-0.66)).toBe("mid");
    expect(deriveBand(0.66)).toBe("mid");
  });
});

// ── DimensionCodeSchema ───────────────────────────────────────────────────────

describe("DimensionCodeSchema", () => {
  it("accepts all 8 valid codes", () => {
    for (const code of DIMENSION_CODES) {
      expect(DimensionCodeSchema.parse(code)).toBe(code);
    }
  });

  it("rejects unknown code", () => {
    expect(() => DimensionCodeSchema.parse("XX")).toThrow();
    expect(() => DimensionCodeSchema.parse("al")).toThrow(); // case-sensitive
    expect(() => DimensionCodeSchema.parse("")).toThrow();
  });
});

// ── RubricAnchorSchema ────────────────────────────────────────────────────────

describe("RubricAnchorSchema", () => {
  const valid = {
    dimension: "AL",
    band: "mid",
    label: "Aware but passive",
    description: "The user knows AI can be wrong but does not act on it.",
    positive_signals: ["plans to verify later"],
    negative_signals: ["elicits calibrated uncertainty in prompts"],
    example_chat_snippet: "I'll double-check the numbers after.",
    synthetic: true,
  };

  it("accepts a valid rubric anchor", () => {
    expect(RubricAnchorSchema.parse(valid)).toEqual(valid);
  });

  it("rejects 'not_applicable' as band (human rubric uses only low/mid/high)", () => {
    expect(() => RubricAnchorSchema.parse({ ...valid, band: "not_applicable" })).toThrow();
  });

  it("rejects empty positive_signals array", () => {
    expect(() => RubricAnchorSchema.parse({ ...valid, positive_signals: [] })).toThrow();
  });

  it("rejects unknown dimension code", () => {
    expect(() => RubricAnchorSchema.parse({ ...valid, dimension: "XX" })).toThrow();
  });
});

// ── TurnSchema ────────────────────────────────────────────────────────────────

describe("TurnSchema", () => {
  const valid = { role: "user", content: "Hello", turn_index: 0, timestamp_ms: null };

  it("accepts a valid user turn", () => {
    expect(TurnSchema.parse(valid)).toEqual(valid);
  });

  it("accepts a valid assistant turn with timestamp", () => {
    const t = { role: "assistant", content: "Hi there.", turn_index: 1, timestamp_ms: 1716199200000 };
    expect(TurnSchema.parse(t)).toEqual(t);
  });

  it("rejects invalid role", () => {
    expect(() => TurnSchema.parse({ ...valid, role: "system" })).toThrow();
  });

  it("rejects empty content", () => {
    expect(() => TurnSchema.parse({ ...valid, content: "" })).toThrow();
  });

  it("rejects negative turn_index", () => {
    expect(() => TurnSchema.parse({ ...valid, turn_index: -1 })).toThrow();
  });
});

// ── TaskFrameSchema ───────────────────────────────────────────────────────────

describe("TaskFrameSchema", () => {
  it("accepts a valid task frame", () => {
    expect(TaskFrameSchema.parse(VALID_FRAME)).toEqual(VALID_FRAME);
  });

  it("rejects fewer than 2 turns", () => {
    expect(() => TaskFrameSchema.parse({ ...VALID_FRAME, turns: [VALID_TURNS[0]] })).toThrow();
  });

  it("rejects invalid platform", () => {
    expect(() => TaskFrameSchema.parse({ ...VALID_FRAME, platform: "perplexity" })).toThrow();
  });

  it("rejects malformed UUID for id", () => {
    expect(() => TaskFrameSchema.parse({ ...VALID_FRAME, id: "not-a-uuid" })).toThrow();
  });

  it("rejects malformed datetime for captured_at", () => {
    expect(() => TaskFrameSchema.parse({ ...VALID_FRAME, captured_at: "2026-05-20" })).toThrow();
  });
});

// ── DimensionScoreSchema ──────────────────────────────────────────────────────

describe("DimensionScoreSchema", () => {
  it("accepts a scored dimension with correct band", () => {
    const scored = makeScore(1.0);
    expect(DimensionScoreSchema.parse(scored)).toEqual(scored);
  });

  it("accepts a not_applicable dimension", () => {
    const na = makeScore(null);
    expect(DimensionScoreSchema.parse(na)).toEqual(na);
  });

  it("accepts delta exactly at LOW_MAX boundary → band 'low'", () => {
    const s = makeScore(BAND_THRESHOLDS.LOW_MAX);
    expect(DimensionScoreSchema.parse(s)).toMatchObject({ band: "low" });
  });

  it("accepts delta exactly at HIGH_MIN boundary → band 'high'", () => {
    const s = makeScore(BAND_THRESHOLDS.HIGH_MIN);
    expect(DimensionScoreSchema.parse(s)).toMatchObject({ band: "high" });
  });

  it("rejects band inconsistent with delta (high delta, low band)", () => {
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(1.5), band: "low" })
    ).toThrow();
  });

  it("rejects band 'not_applicable' when delta is numeric", () => {
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(0.5), band: "not_applicable" })
    ).toThrow();
  });

  it("rejects band 'mid' when delta is null", () => {
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(null), band: "mid" })
    ).toThrow();
  });

  it("rejects delta outside [-2, +2]", () => {
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(0.5), delta: 2.1 })
    ).toThrow();
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(-0.8), delta: -2.1 })
    ).toThrow();
  });

  it("rejects confidence outside [0, 1]", () => {
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(0.0), confidence: 1.1 })
    ).toThrow();
    expect(() =>
      DimensionScoreSchema.parse({ ...makeScore(0.0), confidence: -0.1 })
    ).toThrow();
  });
});

// ── JudgeOutputSchema ─────────────────────────────────────────────────────────

describe("JudgeOutputSchema", () => {
  const valid = {
    task_frame_id: "123e4567-e89b-12d3-a456-426614174000",
    judge_model: "claude-sonnet-4-6",
    judge_prompt_version: "0.1",
    rubric_version: "0.1",
    dimensions: allDimScores(0.5),
    scored_at: "2026-05-20T10:00:00Z",
  };

  it("accepts a valid judge output", () => {
    expect(JudgeOutputSchema.parse(valid)).toBeTruthy();
  });

  it("accepts a judge output where some dimensions are not_applicable", () => {
    const withNA = { ...valid, dimensions: { ...allDimScores(0.5), ES: makeScore(null) } };
    expect(JudgeOutputSchema.parse(withNA)).toBeTruthy();
  });

  it("rejects missing dimension key", () => {
    const { AL: _, ...dimWithoutAL } = allDimScores(0.5) as Record<string, unknown>;
    expect(() => JudgeOutputSchema.parse({ ...valid, dimensions: dimWithoutAL })).toThrow();
  });

  it("rejects malformed task_frame_id", () => {
    expect(() => JudgeOutputSchema.parse({ ...valid, task_frame_id: "bad-id" })).toThrow();
  });
});

// ── AggregatedScoreSchema ─────────────────────────────────────────────────────

describe("AggregatedScoreSchema", () => {
  const validScored = {
    score: 7.5,
    status: "scored",
    confidence: 0.8,
    sample_size: 10,
    applicable_sample_size: 9,
    trend_7d: 0.5,
    last_evidence_quote: "User flagged the AI's mistake.",
  };

  it("accepts a valid scored aggregate", () => {
    expect(AggregatedScoreSchema.parse(validScored)).toEqual(validScored);
  });

  it("accepts not_applicable with null score", () => {
    const na = { ...validScored, score: null, status: "not_applicable" };
    expect(AggregatedScoreSchema.parse(na)).toEqual(na);
  });

  it("accepts insufficient_data with null score and null trend", () => {
    const insuf = { ...validScored, score: null, status: "insufficient_data", trend_7d: null };
    expect(AggregatedScoreSchema.parse(insuf)).toEqual(insuf);
  });

  it("rejects scored status with null score", () => {
    expect(() => AggregatedScoreSchema.parse({ ...validScored, score: null })).toThrow();
  });

  it("rejects not_applicable status with non-null score", () => {
    expect(() =>
      AggregatedScoreSchema.parse({ ...validScored, status: "not_applicable" })
    ).toThrow();
  });

  it("rejects score outside [0, 10]", () => {
    expect(() => AggregatedScoreSchema.parse({ ...validScored, score: 10.1 })).toThrow();
    expect(() => AggregatedScoreSchema.parse({ ...validScored, score: -0.1 })).toThrow();
  });
});

// ── PortfolioSchema ───────────────────────────────────────────────────────────

describe("PortfolioSchema", () => {
  const validAggScore = {
    score: 6.0,
    status: "scored",
    confidence: 0.75,
    sample_size: 5,
    applicable_sample_size: 5,
    trend_7d: null,
    last_evidence_quote: null,
  };

  const valid = {
    user_id: "user-abc",
    current_scores: Object.fromEntries(DIMENSION_CODES.map((k) => [k, validAggScore])),
    total_frames_scored: 5,
    archetype: null,
    archetype_confidence: null,
    last_updated: "2026-05-20T10:00:00Z",
    rubric_version: "0.1",
  };

  it("accepts a valid portfolio", () => {
    expect(PortfolioSchema.parse(valid)).toBeTruthy();
  });

  it("accepts portfolio with archetype set", () => {
    const withArch = { ...valid, archetype: "Methodical Augmentor", archetype_confidence: 0.82 };
    expect(PortfolioSchema.parse(withArch)).toBeTruthy();
  });

  it("rejects missing dimension in current_scores", () => {
    const { AL: _, ...scoresWithoutAL } = valid.current_scores as Record<string, unknown>;
    expect(() => PortfolioSchema.parse({ ...valid, current_scores: scoresWithoutAL })).toThrow();
  });
});

// ── GoldChatAnnotationSchema ──────────────────────────────────────────────────

describe("GoldChatAnnotationSchema", () => {
  it("accepts a valid annotation", () => {
    expect(GoldChatAnnotationSchema.parse(VALID_ANNOTATION)).toEqual(VALID_ANNOTATION);
  });

  it("accepts not_applicable for any band", () => {
    const withNA = { ...VALID_ANNOTATION, bands: { ...allBands("mid"), ES: "not_applicable" } };
    expect(GoldChatAnnotationSchema.parse(withNA)).toBeTruthy();
  });

  it("rejects missing dimension in bands", () => {
    const { AL: _, ...bandsWithoutAL } = allBands("mid") as Record<string, string>;
    expect(() =>
      GoldChatAnnotationSchema.parse({ ...VALID_ANNOTATION, bands: bandsWithoutAL })
    ).toThrow();
  });

  it("rejects missing dimension in notes", () => {
    const { AL: _, ...notesWithoutAL } = allNotes() as Record<string, string>;
    expect(() =>
      GoldChatAnnotationSchema.parse({ ...VALID_ANNOTATION, notes: notesWithoutAL })
    ).toThrow();
  });

  it("rejects invalid band value", () => {
    const badBands = { ...allBands("mid"), AL: "excellent" };
    expect(() =>
      GoldChatAnnotationSchema.parse({ ...VALID_ANNOTATION, bands: badBands })
    ).toThrow();
  });
});

// ── GoldChatSchema ────────────────────────────────────────────────────────────

describe("GoldChatSchema", () => {
  const valid = {
    id: "gc-001",
    platform: "chatgpt",
    turns: [{ role: "user", content: "Help me.", turn_index: 0, timestamp_ms: null }],
    annotations: [VALID_ANNOTATION],
    rubric_version: "0.1",
  };

  it("accepts a valid gold chat with one annotation", () => {
    expect(GoldChatSchema.parse(valid)).toEqual(valid);
  });

  it("accepts multiple annotations (IRR scenario)", () => {
    const secondAnnotation = { ...VALID_ANNOTATION, scorer_id: "scorer-2" };
    const withTwo = { ...valid, annotations: [VALID_ANNOTATION, secondAnnotation] };
    expect(GoldChatSchema.parse(withTwo)).toBeTruthy();
  });

  it("rejects zero annotations", () => {
    expect(() => GoldChatSchema.parse({ ...valid, annotations: [] })).toThrow();
  });

  it("rejects zero turns", () => {
    expect(() => GoldChatSchema.parse({ ...valid, turns: [] })).toThrow();
  });

  it("rejects invalid platform", () => {
    expect(() => GoldChatSchema.parse({ ...valid, platform: "perplexity" })).toThrow();
  });
});
