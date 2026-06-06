import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import ResearchPage from "./page";
import { askResearch } from "../../lib/api-client";

vi.mock("../../lib/api-client", () => ({
  askResearch: vi.fn(async () => ({
    answer: "Inline research answer",
    sources: [],
    citations: {
      citations: [],
      total_citations: 0,
      verified_citations: 0,
      hallucinated_citations: [],
      citation_rate: 0,
    },
    conversation_id: "conv-test",
  })),
  getResearchConversation: vi.fn(async () => ({
    conversation_id: "conv-test",
    turns: [
      { role: "user", content: "Question received" },
      { role: "assistant", content: "Inline research answer" },
    ],
  })),
  getResearchConfig: vi.fn(async () => ({
    provider: "mock",
    model: "mock-model",
    available_sources: ["statute", "glossary"],
    max_context_chunks: 12,
  })),
}));

describe("ResearchPage", () => {
  beforeEach(() => {
    window.history.replaceState({}, "", `${window.location.origin}/research`);
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it("does not put submitted legal text in the URL", async () => {
    const sensitiveText = "Confidential acquisition facts and breakup fee are privileged";
    render(createElement(ResearchPage));

    const textarea = screen.getByLabelText("Question");
    const form = textarea.closest("form");
    expect(form?.getAttribute("method")).toBe("post");

    fireEvent.change(textarea, { target: { value: sensitiveText } });
    fireEvent.click(screen.getByRole("button", { name: "Ask" }));

    await screen.findByText("Inline research answer");
    await waitFor(() => expect(askResearch).toHaveBeenCalledWith(sensitiveText, ["statute", "glossary"], 8, undefined));

    expect(window.location.pathname).toBe("/research");
    expect(window.location.search).toBe("");
    expect(window.location.href).not.toContain(sensitiveText);
    expect(window.location.href).not.toContain(encodeURIComponent(sensitiveText));
  });
});
