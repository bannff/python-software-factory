"use client";

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { ChevronRight, File as FileIcon, Folder, Minus } from "lucide-react";
import type { Terminal } from "@xterm/xterm";
import {
  completeTerminalSession, type TerminalCompletionEntry,
} from "@/lib/terminal-api";
import {
  buildInsertion, commonPrefix, completionMode, extendsWord, foldersOnly,
  isCommandToken, isSafeName, readWord, type CompletionMode, type WordContext,
} from "@/lib/terminal-completion";

const DEBOUNCE_MS = 120;
const IME_GRACE_MS = 120;
interface Entry extends TerminalCompletionEntry { here?: boolean }
interface Suggestions {
  entries: Entry[]; prefix: string; raw: string; token: string;
  mode: CompletionMode; argv: string[]; col: number; row: number;
  directory: string | null; truncated: boolean;
}

export function TerminalCompletion({ term, sessionId, active, enabled, send }: {
  term: Terminal; sessionId: string; active: boolean; enabled: boolean;
  send: (data: string) => void;
}) {
  const [suggestions, setSuggestions] = useState<Suggestions | null>(null);
  const [selected, setSelected] = useState(0);
  const [position, setPosition] = useState<{ left: number; top: number } | null>(null);
  const state = useRef({ suggestions, selected }); state.current = { suggestions, selected };
  const markers = useRef(new Map<number, number>());
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const request = useRef<AbortController | null>(null);
  const dismissed = useRef<string | null>(null);
  const navigated = useRef(false);
  const imeEnded = useRef(0);
  const menuRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = null; request.current?.abort(); request.current = null;
    setSuggestions(null); setSelected(0); navigated.current = false;
  }, []);

  const currentWord = useCallback((): WordContext | null => {
    const buffer = term.buffer.active;
    if (buffer.type === "alternate") return null;
    const absoluteRow = buffer.baseY + buffer.cursorY;
    const line = buffer.getLine(absoluteRow);
    if (!line || line.isWrapped) return null;
    const cursor = Math.min(buffer.cursorX, line.length);
    for (let column = 0; column < cursor; column += 1) {
      const cell = line.getCell(column);
      if ((cell?.getWidth() ?? 1) !== 1 || (cell?.getChars() ?? "").length > 1) return null;
    }
    return readWord(line.translateToString(false), cursor, markers.current.get(absoluteRow));
  }, [term]);

  useEffect(() => {
    const record = () => {
      const buffer = term.buffer.active;
      markers.current.set(buffer.baseY + buffer.cursorY, buffer.cursorX);
      if (markers.current.size > 100) markers.current.delete(markers.current.keys().next().value!);
    };
    const first = term.parser.registerOscHandler(133, (data) => { if (data === "B" || data.startsWith("B;")) record(); return true; });
    const second = term.parser.registerOscHandler(697, (data) => { if (data === "EndPrompt" || data.startsWith("NewCmd")) record(); return true; });
    return () => { first.dispose(); second.dispose(); };
  }, [term]);

  useEffect(() => {
    if (!active || !enabled) { close(); return; }
    const run = async () => {
      const word = currentWord();
      const mode = word ? completionMode(word.token, word.command) : "none";
      if (!word || mode === "none" || dismissed.current === word.token) { close(); return; }
      dismissed.current = null;
      request.current?.abort(); const controller = new AbortController(); request.current = controller;
      try {
        const result = await completeTerminalSession(
          sessionId, word.token, foldersOnly(word.command),
          mode === "command" ? word.argv : undefined, controller.signal,
        );
        if (controller.signal.aborted) return;
        const listed = result.entries.filter((entry) => isSafeName(entry.name)
          && (mode === "path" ? entry.kind === null
            : entry.kind !== null && isCommandToken(entry.name, entry.kind === "flag")));
        if (!listed.length) { close(); return; }
        const entries: Entry[] = mode === "path" && word.token.endsWith("/")
          ? [{ name: "", dir: true, at: 0, kind: null, description: null, nospace: false, here: true }, ...listed]
          : listed;
        setSuggestions({ entries, prefix: result.prefix, raw: word.raw, token: word.token,
          mode, argv: word.argv, col: word.start, row: term.buffer.active.cursorY,
          directory: result.directory, truncated: result.truncated });
        setSelected(0); navigated.current = false;
      } catch { if (!controller.signal.aborted) close(); }
    };
    const schedule = () => {
      if (timer.current) clearTimeout(timer.current);
      timer.current = setTimeout(() => void run(), DEBOUNCE_MS);
    };
    const cursor = term.onCursorMove(schedule);
    const line = term.onLineFeed(() => { dismissed.current = null; close(); });
    return () => { cursor.dispose(); line.dispose(); close(); };
  }, [active, enabled, term, sessionId, currentWord, close]);

  const accept = useCallback((entry: Entry, value: Suggestions) => {
    close();
    if (entry.here) { dismissed.current = value.token; return; }
    const suffix = value.mode === "path" ? (entry.dir ? "/" : " ") : (entry.nospace ? "" : " ");
    const insertion = buildInsertion(value.raw, entry.name, suffix, value.mode === "path");
    if (value.mode === "path" && !entry.dir) dismissed.current = "";
    send("\x7f".repeat(insertion.erase) + insertion.text);
  }, [close, send]);

  useEffect(() => {
    const claim = (event: KeyboardEvent) => { event.preventDefault(); event.stopPropagation(); return false; };
    term.attachCustomKeyEventHandler((event) => {
      if (event.type !== "keydown" || event.isComposing || event.keyCode === 229) return true;
      if (Date.now() - imeEnded.current < IME_GRACE_MS) return event.key === "Tab" ? claim(event) : true;
      const value = state.current.suggestions;
      if (!value || event.ctrlKey || event.metaKey || event.altKey) return true;
      const fresh = currentWord();
      const stale = !fresh || fresh.token !== value.token
        || (value.mode === "command" && fresh.argv.join("\0") !== value.argv.join("\0"));
      if (event.key === "ArrowDown" || event.key === "ArrowUp") {
        navigated.current = true; const delta = event.key === "ArrowDown" ? 1 : -1;
        setSelected((index) => (index + delta + value.entries.length) % value.entries.length); return claim(event);
      }
      if (event.key === "Escape") { dismissed.current = value.token; close(); return claim(event); }
      if (event.key === "Enter") {
        if (!navigated.current || stale) { close(); return true; }
        accept(value.entries[state.current.selected], value); return claim(event);
      }
      if (event.key === "Tab") {
        if (stale) { close(); return true; }
        const common = commonPrefix(value.entries.filter((entry) => !entry.here).map((entry) => entry.name));
        if (extendsWord(common, value.prefix)) {
          const insertion = buildInsertion(value.raw, common, "", value.mode === "path");
          close(); send("\x7f".repeat(insertion.erase) + insertion.text);
        } else accept(value.entries[state.current.selected], value);
        return claim(event);
      }
      return true;
    });
    return () => { term.attachCustomKeyEventHandler(() => true); };
  }, [term, currentWord, close, accept, send]);

  useEffect(() => {
    const textarea = term.textarea; if (!textarea) return;
    const done = () => { imeEnded.current = Date.now(); };
    textarea.addEventListener("compositionend", done);
    return () => textarea.removeEventListener("compositionend", done);
  }, [term]);

  useLayoutEffect(() => {
    if (!suggestions || !menuRef.current) { setPosition(null); return; }
    const screen = term.element?.querySelector(".xterm-screen") as HTMLElement | null;
    const pane = menuRef.current.offsetParent as HTMLElement | null;
    if (!screen || !pane) return;
    const left = Math.min(suggestions.col * screen.clientWidth / Math.max(1, term.cols), pane.clientWidth - 204);
    const below = (suggestions.row + 1) * screen.clientHeight / Math.max(1, term.rows);
    setPosition({ left: Math.max(4, left), top: Math.max(4, Math.min(below, pane.clientHeight - 132)) });
  }, [suggestions, term]);

  if (!suggestions) return null;
  return <div ref={menuRef} role="listbox" aria-label="Terminal completions" data-testid="terminal-completion"
    className="absolute z-30 min-w-52 max-w-[70%] overflow-hidden rounded-md border border-border bg-popover text-popover-foreground shadow-lg"
    style={{ left: position?.left ?? 0, top: position?.top ?? 0, opacity: position ? 1 : 0 }}>
    <div className="max-h-28 overflow-y-auto">
      {suggestions.entries.map((entry, index) => <div key={entry.here ? "here" : entry.name} role="option"
        aria-selected={index === selected} className={`flex h-6 items-center gap-1.5 px-2 font-mono text-xs ${index === selected ? "bg-accent text-accent-foreground" : ""}`}>
        {entry.here ? <ChevronRight className="h-3 w-3" /> : entry.kind === "flag" ? <Minus className="h-3 w-3" />
          : entry.dir ? <Folder className="h-3 w-3" /> : <FileIcon className="h-3 w-3" />}
        <span className="truncate">{entry.here ? "Use this folder" : entry.name + (entry.dir && !entry.kind ? "/" : "")}</span>
        {entry.description && <span className="min-w-0 flex-1 truncate text-[10px] text-muted-foreground">{entry.description}</span>}
      </div>)}
    </div>
    <div className="flex items-center justify-between gap-3 border-t border-border px-2 py-1 text-[10px] text-muted-foreground">
      <span className="min-w-0 truncate font-mono">
        {suggestions.directory
          ? `${suggestions.directory}${suggestions.truncated ? " (more results)" : ""}`
          : suggestions.truncated ? "More results available" : ""}
      </span>
      <span className="shrink-0">↑↓ choose · Tab complete · Enter run · Esc close</span>
    </div>
  </div>;
}
