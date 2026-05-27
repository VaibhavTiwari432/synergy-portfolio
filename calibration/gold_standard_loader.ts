import { existsSync, readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { GoldChatSchema, type GoldChat } from "@synergy/schemas";

const GOLD_CHAT_FILE_PATTERN = /^gc-\d{3}\.json$/;

export type LoadGoldStandardOptions = {
  directory?: string;
  minChats?: number;
};

export function loadGoldStandardChats(
  options: LoadGoldStandardOptions = {},
): GoldChat[] {
  const directory = options.directory ?? findGoldStandardDirectory(process.cwd());
  const minChats = options.minChats ?? 20;

  const fileNames = readdirSync(directory)
    .filter((fileName) => GOLD_CHAT_FILE_PATTERN.test(fileName))
    .sort();

  if (fileNames.length < minChats) {
    throw new Error(
      `loadGoldStandardChats: expected at least ${minChats} gold chats in ${directory}, found ${fileNames.length}`,
    );
  }

  return fileNames.map((fileName) => loadGoldChat(join(directory, fileName)));
}

function findGoldStandardDirectory(startDirectory: string): string {
  let currentDirectory = startDirectory;

  while (true) {
    const candidate = join(currentDirectory, "gold_standard", "chats");
    if (existsSync(candidate)) return candidate;

    const parentDirectory = dirname(currentDirectory);
    if (parentDirectory === currentDirectory) {
      throw new Error(
        `loadGoldStandardChats: could not find gold_standard/chats from ${startDirectory}`,
      );
    }

    currentDirectory = parentDirectory;
  }
}

export function loadGoldChat(filePath: string): GoldChat {
  let raw: unknown;
  try {
    raw = JSON.parse(readFileSync(filePath, "utf8"));
  } catch (err) {
    throw new Error(
      `loadGoldChat: could not parse ${filePath}: ${String(err)}`,
    );
  }

  const result = GoldChatSchema.safeParse(raw);
  if (!result.success) {
    throw new Error(
      `loadGoldChat: ${filePath} failed GoldChat validation: ${result.error.message}`,
    );
  }

  return result.data;
}
