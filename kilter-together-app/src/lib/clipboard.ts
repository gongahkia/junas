export type ClipboardCopyMethod = "clipboard" | "exec_command";

export async function copyTextToClipboard(text: string): Promise<ClipboardCopyMethod> {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return "clipboard";
    } catch {
      // Fall through to the legacy copy path for browsers that block clipboard writes.
    }
  }

  if (typeof document === "undefined" || typeof document.execCommand !== "function") {
    throw new Error("Clipboard is not available in this environment.");
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "0";
  textarea.style.opacity = "0";
  textarea.style.pointerEvents = "none";

  const activeElement =
    document.activeElement instanceof HTMLElement ? document.activeElement : null;
  const selection = document.getSelection();
  const savedRanges =
    selection && selection.rangeCount > 0
      ? Array.from({ length: selection.rangeCount }, (_, index) =>
          selection.getRangeAt(index).cloneRange()
        )
      : [];

  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  textarea.setSelectionRange(0, textarea.value.length);

  const copied = document.execCommand("copy");

  document.body.removeChild(textarea);
  if (selection) {
    selection.removeAllRanges();
    savedRanges.forEach((range) => selection.addRange(range));
  }
  activeElement?.focus();

  if (!copied) {
    throw new Error("The legacy clipboard copy command failed.");
  }

  return "exec_command";
}

export function isShareAbortError(error: unknown): boolean {
  if (error instanceof DOMException) {
    return error.name === "AbortError";
  }

  return (
    typeof error === "object" &&
    error !== null &&
    "name" in error &&
    error.name === "AbortError"
  );
}
