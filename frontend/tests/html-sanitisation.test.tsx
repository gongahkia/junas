// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import GlossaryTermPage from "../app/glossary/[phrase]/page";
import StatuteSectionPage from "../app/statutes/section/[number]/page";
import { compareGlossaryTerm, getGlossaryTerm, getStatuteSection } from "../lib/api-server";

vi.mock("../lib/api-server", () => ({
  compareGlossaryTerm: vi.fn(),
  getGlossaryTerm: vi.fn(),
  getStatuteSection: vi.fn(),
}));

describe("html sanitisation", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("blocks hostile statute section html and preserves valid markup", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);
    vi.mocked(getStatuteSection).mockResolvedValue({
      number: "1",
      name: "Interpretation",
      chapter_number: "1",
      edition: 2020,
      text_html: '<p><strong>valid statute text</strong></p><img src="x" onerror="alert(1)"><script>alert(1)</script>',
      text_plain: "valid statute text",
      amendment_history: "",
      cross_references: [],
      referenced_by: [],
    });

    const view = await StatuteSectionPage({ params: { number: "1" } });
    const { container } = render(view);
    const image = container.querySelector("img");

    expect(screen.getByText("valid statute text")).toBeTruthy();
    expect(container.querySelector("strong")?.textContent).toBe("valid statute text");
    expect(container.querySelector("script")).toBeNull();
    expect(image?.getAttribute("onerror")).toBeNull();
    image?.dispatchEvent(new Event("error"));
    expect(alertSpy).not.toHaveBeenCalled();
  });

  it("blocks hostile glossary definition html and preserves valid markup", async () => {
    const alertSpy = vi.spyOn(window, "alert").mockImplementation(() => undefined);
    vi.mocked(getGlossaryTerm).mockResolvedValue({
      phrase: "director",
      definitions: [
        {
          jurisdiction: "SG",
          domain: "Companies",
          definition_html: '<p><em>valid glossary text</em></p><img src="x" onerror="alert(1)"><script>alert(1)</script>',
          definition_text: "valid glossary text",
          source_title: "Companies Act",
          source_url: "https://example.test/companies-act",
        },
      ],
    });
    vi.mocked(compareGlossaryTerm).mockResolvedValue({
      term: "director",
      comparisons: [],
      available_in: ["SG"],
      not_found_in: [],
    });

    const view = await GlossaryTermPage({ params: { phrase: "director" } });
    const { container } = render(view);
    const image = container.querySelector("img");

    expect(screen.getByText("valid glossary text")).toBeTruthy();
    expect(container.querySelector("em")?.textContent).toBe("valid glossary text");
    expect(container.querySelector("script")).toBeNull();
    expect(image?.getAttribute("onerror")).toBeNull();
    image?.dispatchEvent(new Event("error"));
    expect(alertSpy).not.toHaveBeenCalled();
  });
});
