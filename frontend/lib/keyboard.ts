"use client";

export type KeyboardActionId =
  | "open-command-palette"
  | "open-keyboard-help"
  | "focus-chat-input"
  | "new-chat"
  | "toggle-session-sidebar"
  | "export-current-view-docx"
  | "copy-last-assistant-response"
  | "jump-to-page-palette"
  | "rerun-last-benchmark";

export type ShortcutCategory = "navigation" | "chat" | "workflow";

export type KeyCombo = {
  key: string;
  mod?: boolean;
  shift?: boolean;
  alt?: boolean;
  allowInEditable?: boolean;
};

export type KeyboardShortcut = {
  id: KeyboardActionId;
  label: string;
  description: string;
  category: ShortcutCategory;
  mac: string;
  windows: string;
  combos: KeyCombo[];
  allowInEditable?: boolean;
};

export const KEYBOARD_SHORTCUTS: readonly KeyboardShortcut[] = [
  {
    id: "open-command-palette",
    label: "Open command palette",
    description: "Search commands and app pages",
    category: "navigation",
    mac: "⌘K",
    windows: "Ctrl+K",
    combos: [{ key: "k", mod: true, allowInEditable: true }],
  },
  {
    id: "open-keyboard-help",
    label: "Open keyboard help",
    description: "Show all shortcuts",
    category: "navigation",
    mac: "⌘/ or ?",
    windows: "Ctrl+/ or ?",
    combos: [{ key: "/", mod: true, allowInEditable: true }, { key: "?", shift: true }],
  },
  {
    id: "focus-chat-input",
    label: "Focus chat input",
    description: "Jump to the chat composer",
    category: "chat",
    mac: "⌘L",
    windows: "Ctrl+L",
    combos: [{ key: "l", mod: true }],
  },
  {
    id: "new-chat",
    label: "New chat",
    description: "Start a fresh chat session",
    category: "chat",
    mac: "⌘⇧L",
    windows: "Ctrl+Shift+L",
    combos: [{ key: "l", mod: true, shift: true, allowInEditable: true }],
  },
  {
    id: "toggle-session-sidebar",
    label: "Toggle session sidebar",
    description: "Show or hide the sidebar",
    category: "navigation",
    mac: "⌘B",
    windows: "Ctrl+B",
    combos: [{ key: "b", mod: true }],
  },
  {
    id: "export-current-view-docx",
    label: "Export current view to DOCX",
    description: "Download the active exportable view",
    category: "workflow",
    mac: "⌘⇧E",
    windows: "Ctrl+Shift+E",
    combos: [{ key: "e", mod: true, shift: true }],
  },
  {
    id: "copy-last-assistant-response",
    label: "Copy last assistant response",
    description: "Copy the newest Junas response",
    category: "chat",
    mac: "⌘⇧C",
    windows: "Ctrl+Shift+C",
    combos: [{ key: "c", mod: true, shift: true }],
  },
  {
    id: "jump-to-page-palette",
    label: "Jump to page",
    description: "Open page-only palette",
    category: "navigation",
    mac: "⌘P",
    windows: "Ctrl+P",
    combos: [{ key: "p", mod: true }],
  },
  {
    id: "rerun-last-benchmark",
    label: "Re-run last benchmark",
    description: "Repeat the latest leaderboard run",
    category: "workflow",
    mac: "⌘⇧K",
    windows: "Ctrl+Shift+K",
    combos: [{ key: "k", mod: true, shift: true }],
  },
];

export const SHORTCUT_BY_ID = new Map(KEYBOARD_SHORTCUTS.map((shortcut) => [shortcut.id, shortcut]));

export function isEditableTarget(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  const tag = target.tagName.toLowerCase();
  return tag === "input" || tag === "textarea" || target.isContentEditable;
}

export function comboMatches(event: KeyboardEvent, combo: KeyCombo): boolean {
  const key = event.key.toLowerCase();
  const expected = combo.key.toLowerCase();
  const mod = event.metaKey || event.ctrlKey;
  return key === expected
    && Boolean(combo.mod) === mod
    && Boolean(combo.shift) === event.shiftKey
    && Boolean(combo.alt) === event.altKey;
}

export function findShortcutForEvent(event: KeyboardEvent): KeyboardShortcut | null {
  if (isEditableTarget(event.target)) {
    const editableShortcut = KEYBOARD_SHORTCUTS.find((shortcut) => shortcut.combos.some((combo) => (shortcut.allowInEditable || combo.allowInEditable) && comboMatches(event, combo)));
    return editableShortcut ?? null;
  }
  return KEYBOARD_SHORTCUTS.find((shortcut) => shortcut.combos.some((combo) => comboMatches(event, combo))) ?? null;
}
