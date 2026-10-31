/** Pure parsing and insertion rules for xterm completion. */

const PATH_COMMANDS = new Set([
  "cd", "pushd", "ls", "ll", "la", "cat", "bat", "less", "more", "head", "tail",
  "cp", "mv", "rm", "rmdir", "mkdir", "touch", "ln", "stat", "du", "wc", "file",
  "open", "code", "vim", "vi", "nvim", "nano", "emacs", "source", ".", "chmod",
  "chown", "diff", "rsync", "tar", "zip", "unzip", "python", "python3", "node",
  "sh", "bash", "zsh", "go", "cargo", "make",
]);
const FOLDER_COMMANDS = new Set(["cd", "pushd", "rmdir", "mkdir"]);
const WRAPPERS = new Set(["sudo", "env", "time", "nohup", "command", "exec"]);
const PROMPT = /(?:❯|➜|»|▶|\$|%|#|>)[ \t]+/g;
const COMMAND_SEPARATOR = /\|\||&&|[|;&]/;

export type CompletionMode = "path" | "command" | "none";
export interface WordContext {
  raw: string;
  token: string;
  start: number;
  command: string;
  argv: string[];
}

function trailingEscapes(value: string): number {
  let count = 0;
  while (count < value.length && value[value.length - 1 - count] === "\\") count += 1;
  return count;
}

export function extractToken(line: string, cursor: number): { token: string; start: number } {
  const end = Math.max(0, Math.min(cursor, line.length));
  let start = end;
  while (start > 0) {
    const previous = line[start - 1];
    if (!/\s/.test(previous)) { start -= 1; continue; }
    if (trailingEscapes(line.slice(0, start - 1)) % 2 === 0) break;
    start -= 1;
  }
  return { token: line.slice(start, end), start };
}

export function atWordEnd(line: string, cursor: number): boolean {
  return line[cursor] === undefined || /\s/.test(line[cursor]);
}

export function commandStart(line: string, tokenStart: number, marker?: number): number {
  if (marker !== undefined && marker >= 0 && marker <= tokenStart) return marker;
  PROMPT.lastIndex = 0;
  let end = 0;
  let match: RegExpExecArray | null;
  while ((match = PROMPT.exec(line.slice(0, tokenStart))) !== null) {
    end = match.index + match[0].length;
  }
  return end;
}

export function isPlainWord(line: string, start: number, tokenStart: number, token: string): boolean {
  if (/["']/.test(token) || /["']/.test(line.slice(start, tokenStart))) return false;
  if (trailingEscapes(token) % 2 === 1) return false;
  const escapes = /(\\*)\s*$/.exec(line.slice(start, tokenStart));
  return !escapes || escapes[1].length % 2 === 0;
}

export function unescapeWord(value: string): string {
  return value.replace(/\\([\s\S])/g, "$1");
}

function splitWords(value: string): string[] {
  const words: string[] = [];
  let current = "";
  for (let index = 0; index < value.length; index += 1) {
    const char = value[index];
    if (char === "\\" && index + 1 < value.length) {
      current += char + value[index + 1]; index += 1; continue;
    }
    if (/\s/.test(char)) {
      if (current) { words.push(current); current = ""; }
    } else current += char;
  }
  if (current) words.push(current);
  return words;
}

function commandWords(line: string, tokenStart: number, marker?: number): string[] {
  const segment = line.slice(commandStart(line, tokenStart, marker), tokenStart);
  const words = splitWords(segment.split(COMMAND_SEPARATOR).pop() ?? "");
  let index = 0;
  while (index < words.length - 1 && (WRAPPERS.has(words[index]) || words[index].includes("="))) index += 1;
  return words.slice(index);
}

export function readWord(line: string, cursor: number, marker?: number): WordContext | null {
  if (!atWordEnd(line, cursor)) return null;
  const { token: raw, start } = extractToken(line, cursor);
  const commandAt = commandStart(line, start, marker);
  if (!isPlainWord(line, commandAt, start, raw)) return null;
  const words = commandWords(line, start, marker);
  return {
    raw, token: unescapeWord(raw), start,
    command: words[0] ?? "", argv: words.map(unescapeWord),
  };
}

export function completionMode(token: string, command: string): CompletionMode {
  if (command === "" || token.startsWith("$") || token.startsWith("`")) return "none";
  const pathShape = token.includes("/") || token.startsWith("~") || token.startsWith(".");
  if (!token.startsWith("-") && (pathShape || PATH_COMMANDS.has(command))) return "path";
  if (PATH_COMMANDS.has(command) || pathShape) return "none";
  return "command";
}

export function foldersOnly(command: string): boolean {
  return FOLDER_COMMANDS.has(command);
}

export function commonPrefix(names: readonly string[]): string {
  if (!names.length) return "";
  let prefix = [...names[0]];
  for (const name of names.slice(1)) {
    const chars = [...name]; let index = 0;
    while (index < prefix.length && index < chars.length && prefix[index] === chars[index]) index += 1;
    prefix = prefix.slice(0, index);
  }
  return prefix.join("");
}

export function extendsWord(candidate: string, prefix: string): boolean {
  return Boolean(candidate) && candidate.length >= prefix.length
    && candidate.toLowerCase().startsWith(prefix.toLowerCase()) && candidate !== prefix;
}

export function isSafeName(name: string): boolean {
  return !/[\p{Cc}\p{Cs}]/u.test(name);
}

export function isCommandToken(name: string, flag: boolean): boolean {
  if (!isSafeName(name)) return false;
  return flag
    ? /^--?[\p{L}\p{N}][\p{L}\p{N}._-]*=?$/u.test(name)
    : /^[\p{L}\p{N}][\p{L}\p{N}._+:@-]*$/u.test(name);
}

export function buildInsertion(word: string, replacement: string, suffix = "", path = true) {
  const separator = word.lastIndexOf("/");
  const onScreen = word.slice(separator + 1);
  let text = path
    ? replacement.replace(/[^\p{L}\p{N}_@%+:,./-]/gu, (char) => `\\${char}`)
    : replacement;
  if (path && /^[-+]|:/.test(replacement) && separator < 0) text = `./${text}`;
  if (text.startsWith(onScreen)) return { erase: 0, text: text.slice(onScreen.length) + suffix };
  return { erase: [...onScreen].length, text: text + suffix };
}
