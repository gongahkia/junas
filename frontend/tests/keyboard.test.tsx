import { describe, expect, it } from "vitest";
import { COMMAND_DEFINITIONS } from "../lib/commands/definitions";
import { findShortcutForEvent, KEYBOARD_SHORTCUTS } from "../lib/keyboard";

const expectedShortcutIds = [
  "open-command-palette",
  "open-keyboard-help",
  "focus-chat-input",
  "new-chat",
  "toggle-session-sidebar",
  "export-current-view-docx",
  "copy-last-assistant-response",
  "jump-to-page-palette",
  "rerun-last-benchmark",
];

function keyEvent(key: string, options: KeyboardEventInit = {}) {
  return new KeyboardEvent("keydown", { key, bubbles: true, ...options });
}

describe("keyboard shortcuts", () => {
  it("registers the requested power-user actions", () => {
    expect(KEYBOARD_SHORTCUTS.map((shortcut) => shortcut.id)).toEqual(expectedShortcutIds);
  });

  it("keeps help-dialog shortcuts and palette shortcut commands in sync", () => {
    const paletteShortcutIds = COMMAND_DEFINITIONS
      .filter((definition) => definition.action.kind === "shortcut")
      .map((definition) => definition.action.kind === "shortcut" ? definition.action.shortcutId : "");

    expect(new Set(paletteShortcutIds)).toEqual(new Set(expectedShortcutIds));
  });

  it("does not register reserved new-window/tab/close chords", () => {
    const combos = KEYBOARD_SHORTCUTS.flatMap((shortcut) => shortcut.combos.map((combo) => `${combo.mod ? "mod+" : ""}${combo.shift ? "shift+" : ""}${combo.key.toLowerCase()}`));
    expect(combos).not.toContain("mod+w");
    expect(combos).not.toContain("mod+t");
    expect(combos).not.toContain("mod+n");
  });

  it("matches global keyboard events", () => {
    expect(findShortcutForEvent(keyEvent("k", { metaKey: true }))?.id).toBe("open-command-palette");
    expect(findShortcutForEvent(keyEvent("/", { ctrlKey: true }))?.id).toBe("open-keyboard-help");
    expect(findShortcutForEvent(keyEvent("?", { shiftKey: true }))?.id).toBe("open-keyboard-help");
    expect(findShortcutForEvent(keyEvent("K", { metaKey: true, shiftKey: true }))?.id).toBe("rerun-last-benchmark");
  });
});
