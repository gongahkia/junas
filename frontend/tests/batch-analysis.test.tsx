import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import BatchAnalysisPage from "../app/batch-analysis/page";
import { createContractBatch } from "../lib/api-client";

vi.mock("../lib/api-client", () => ({
  cancelContractBatch: vi.fn(async () => ({ id: "batch-1", status: "cancelled", total: 1, completed: 0, cancelled: true, results: [] })),
  contractBatchEventsUrl: vi.fn(() => "http://localhost/events"),
  createContractBatch: vi.fn(async () => ({
    id: "batch-1",
    status: "queued",
    total: 1,
    completed: 0,
    cancelled: false,
    created_at: "2026-06-14T00:00:00Z",
    updated_at: "2026-06-14T00:00:00Z",
    results: [],
  })),
  getContractBatch: vi.fn(async () => null),
  parseDocument: vi.fn(),
}));

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, Array<(event: MessageEvent) => void>> = {};
  onmessage: ((event: MessageEvent) => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }
  addEventListener(name: string, callback: (event: MessageEvent) => void) {
    this.listeners[name] = [...(this.listeners[name] || []), callback];
  }
  emit(name: string, payload: unknown) {
    const event = new MessageEvent(name, { data: JSON.stringify(payload) });
    for (const callback of this.listeners[name] || []) callback(event);
  }
  close() {}
}

describe("BatchAnalysisPage", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
    MockEventSource.instances = [];
    localStorage.clear();
  });

  it("uploads text files and streams batch progress", async () => {
    vi.stubGlobal("EventSource", MockEventSource as any);
    render(createElement(BatchAnalysisPage));

    const file = new File(["Singapore law applies."], "contract.txt", { type: "text/plain" });
    fireEvent.change(document.querySelector("input[type=file]")!, { target: { files: [file] } });
    fireEvent.click(screen.getByRole("button", { name: /Analyze 1 document/ }));

    await waitFor(() => expect(createContractBatch).toHaveBeenCalled());
    MockEventSource.instances[0].emit("completed", {
      batch: {
        id: "batch-1",
        status: "completed",
        total: 1,
        completed: 1,
        cancelled: false,
        results: [{ document_id: "contract.txt-22-0", file_name: "contract.txt", status: "done", summary: "1 clause", flagged_clauses: [], clauses: [], reasoning: "" }],
      },
    });

    await screen.findByText("contract.txt");
    expect(screen.getByText("1 clause")).toBeTruthy();
  });
});
