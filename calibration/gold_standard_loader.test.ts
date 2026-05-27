import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { DIMENSION_CODES, type GoldChat } from "@synergy/schemas";
import { loadGoldChat, loadGoldStandardChats } from "./gold_standard_loader.js";

const VALID_GOLD_CHAT: GoldChat = {
  id: "gc-999",
  platform: "chatgpt",
  turns: [
    {
      role: "user",
      content: "Please help me structure this study session.",
      turn_index: 0,
      timestamp_ms: null,
    },
  ],
  annotations: [
    {
      scorer_id: "sangillence",
      bands: {
        AL: "mid",
        PR: "high",
        AUI: "high",
        EC: "mid",
        CS: "high",
        CD: "mid",
        ES: "not_applicable",
        CA: "high",
      },
      notes: {
        AL: "Shows some awareness of AI limits.",
        PR: "Provides a clear goal and format.",
        AUI: "Uses AI for a task where it adds value.",
        EC: "Some validation is present.",
        CS: "Combines AI output with own constraints.",
        CD: "Explores a few alternatives.",
        ES: "No ethical content is present.",
        CA: "Keeps control of the workflow.",
      },
      scored_at: "2026-05-21T00:00:00Z",
    },
  ],
  rubric_version: "0.1",
};

describe("loadGoldStandardChats", () => {
  it("loads and validates the checked-in gold standard chats", () => {
    const chats = loadGoldStandardChats();

    expect(chats.length).toBeGreaterThanOrEqual(20);
    expect(chats.map((chat) => chat.id)).toContain("gc-001");
    expect(chats.map((chat) => chat.id)).toContain("gc-023");

    for (const chat of chats) {
      expect(chat.annotations.length).toBeGreaterThanOrEqual(1);

      for (const annotation of chat.annotations) {
        expect(Object.keys(annotation.bands)).toEqual([...DIMENSION_CODES]);
        expect(Object.keys(annotation.notes)).toEqual([...DIMENSION_CODES]);
      }
    }
  });

  it("loads a single valid gold chat file", () => {
    const tempDir = mkdtempSync(join(tmpdir(), "synergy-gold-"));
    const filePath = join(tempDir, "gc-999.json");

    try {
      writeFileSync(filePath, JSON.stringify(VALID_GOLD_CHAT), "utf8");

      expect(loadGoldChat(filePath)).toEqual(VALID_GOLD_CHAT);
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("fails clearly when a gold chat is malformed", () => {
    const tempDir = mkdtempSync(join(tmpdir(), "synergy-gold-"));
    const filePath = join(tempDir, "gc-999.json");

    try {
      writeFileSync(filePath, JSON.stringify({ id: "gc-999" }), "utf8");

      expect(() => loadGoldChat(filePath)).toThrow(/GoldChat validation/);
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });

  it("fails when fewer than the required number of chats are present", () => {
    const tempDir = mkdtempSync(join(tmpdir(), "synergy-gold-"));
    const filePath = join(tempDir, "gc-999.json");

    try {
      writeFileSync(filePath, JSON.stringify(VALID_GOLD_CHAT), "utf8");

      expect(() => loadGoldStandardChats({ directory: tempDir, minChats: 2 }))
        .toThrow(/expected at least 2 gold chats/);
    } finally {
      rmSync(tempDir, { recursive: true, force: true });
    }
  });
});
