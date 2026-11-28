import assert from "node:assert/strict";
import { test } from "node:test";
import { readFile } from "node:fs/promises";
import vm from "node:vm";
import { admitText } from "../src/contract.js";
import { randomUUID } from "node:crypto";

test("context-menu selection starts in the background without a popup or tab", async () => {
  let click, submitted, badge;
  const chrome = {
    runtime: { id: "self", getURL: p => p, getContexts: async () => [{}], onMessage: { addListener() {} }, onInstalled: { addListener() {} },
      sendMessage: async command => { submitted = command; return { ok: true, state: { busy: true } }; } },
    contextMenus: { create() {}, onClicked: { addListener: fn => { click = fn; } } },
    action: { setBadgeText: async value => { badge = value.text; }, setTitle: async () => {}, openPopup: () => assert.fail("no automatic popup") },
    scripting: { executeScript: async () => [{ result: true }] },
    tabs: { create: () => assert.fail("no automatic tab") },
  };
  vm.runInNewContext((await readFile(new URL("../src/background.js", import.meta.url), "utf8")).replace(/^import .*;$/gm, ""), { chrome, admitText, crypto: { randomUUID }, captureSelection() {}, replaceSelection() {} });
  await click({ menuItemId: "process", selectionText: "Only the highlighted text." }, { id: 42 });
  assert.equal(submitted.kind, "capture");
  assert.equal(submitted.text, "Only the highlighted text.");
  assert.equal(badge, "…");
});
