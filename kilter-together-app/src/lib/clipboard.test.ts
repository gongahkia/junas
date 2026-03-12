import { copyTextToClipboard, isShareAbortError } from "./clipboard";

const originalClipboardDescriptor = Object.getOwnPropertyDescriptor(navigator, "clipboard");
const originalExecCommandDescriptor = Object.getOwnPropertyDescriptor(document, "execCommand");

describe("clipboard helpers", () => {
  afterEach(() => {
    vi.restoreAllMocks();
    document.body.innerHTML = "";

    if (originalClipboardDescriptor) {
      Object.defineProperty(navigator, "clipboard", originalClipboardDescriptor);
    } else {
      Reflect.deleteProperty(navigator, "clipboard");
    }

    if (originalExecCommandDescriptor) {
      Object.defineProperty(document, "execCommand", originalExecCommandDescriptor);
    } else {
      Reflect.deleteProperty(document, "execCommand");
    }
  });

  it("uses the clipboard api when it is available", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const execCommand = vi.fn().mockReturnValue(true);

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await expect(copyTextToClipboard("invite-link")).resolves.toBe("clipboard");
    expect(writeText).toHaveBeenCalledWith("invite-link");
    expect(execCommand).not.toHaveBeenCalled();
  });

  it("falls back to execCommand when clipboard writes are blocked", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("blocked"));
    const execCommand = vi.fn().mockReturnValue(true);

    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText },
    });
    Object.defineProperty(document, "execCommand", {
      configurable: true,
      value: execCommand,
    });

    await expect(copyTextToClipboard("invite-link")).resolves.toBe("exec_command");
    expect(writeText).toHaveBeenCalledWith("invite-link");
    expect(execCommand).toHaveBeenCalledWith("copy");
    expect(document.querySelector("textarea")).not.toBeInTheDocument();
  });

  it("detects aborted share sheets without treating them as copy errors", () => {
    expect(isShareAbortError(new DOMException("cancelled", "AbortError"))).toBe(true);
    expect(isShareAbortError({ name: "AbortError" })).toBe(true);
    expect(isShareAbortError(new Error("other failure"))).toBe(false);
  });
});
