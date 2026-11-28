// injected only after the user's context-menu action, into the frame they selected.
export function captureSelection(expected, id) {
  const anchors = globalThis.__junasSelections ??= new Map();
  for (const [key, value] of anchors) if (Date.now() - value.created > 600_000) anchors.delete(key);
  if (anchors.size >= 8) throw Error("Too many pending selections.");
  const element = document.activeElement;
  let anchor;
  if (element instanceof HTMLTextAreaElement || (element instanceof HTMLInputElement && ["text", "search", "email", "url", "tel"].includes(element.type))) {
    const start = element.selectionStart, end = element.selectionEnd;
    if (!Number.isInteger(start) || element.value.slice(start, end) !== expected || element.readOnly || element.disabled) throw Error("Editable selection is unavailable.");
    anchor = { element, start, end, original: element.value };
  } else {
    const selection = getSelection();
    if (element instanceof HTMLInputElement && element.type === "password") throw Error("Password fields are excluded.");
    if (selection?.rangeCount !== 1 || selection.toString() !== expected) throw Error("Selection changed before capture.");
    const range = selection.getRangeAt(0).cloneRange();
    if (range.cloneContents().querySelector("script,style,input,textarea,select,button,iframe,canvas,video,audio,svg")) throw Error("Select text without embedded controls.");
    anchor = { range };
  }
  anchors.set(id, { ...anchor, expected, created: Date.now() });
  return true;
}
export function replaceSelection(id, replacement) {
  const anchors = globalThis.__junasSelections, anchor = anchors?.get(id);
  anchors?.delete(id);
  if (!anchor || Date.now() - anchor.created > 600_000 || typeof replacement !== "string") throw Error("Selection expired.");
  if (anchor.element) {
    const { element, original, start, end } = anchor;
    if (!element.isConnected || element.value !== original || element.readOnly || element.disabled) throw Error("The source changed; no text was replaced.");
    element.setRangeText(replacement, start, end, "select");
    element.dispatchEvent(new InputEvent("input", { bubbles: true, inputType: "insertReplacementText", data: replacement }));
  } else {
    const range = anchor.range;
    if (!range.startContainer.isConnected || !range.endContainer.isConnected || range.toString() !== anchor.expected) throw Error("The source changed; no text was replaced.");
    range.deleteContents(); range.insertNode(document.createTextNode(replacement));
  }
  return true;
}
