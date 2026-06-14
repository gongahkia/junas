import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { createElement } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessionSidebar from "../components/SessionSidebar";
import { deleteConversationRemote, listConversationsRemote, renameConversationRemote } from "../lib/conversation-store";

vi.mock("../lib/conversation-store", () => ({
  deleteConversation: vi.fn(),
  deleteConversationRemote: vi.fn(async () => true),
  listConversations: vi.fn(() => [
    { id: "conv-local", title: "Local draft", createdAt: 10, updatedAt: 20, messageCount: 1 },
  ]),
  listConversationsRemote: vi.fn(async () => [
    { id: "conv-remote", title: "Remote session", createdAt: 100, updatedAt: 200, messageCount: 2 },
  ]),
  renameConversationRemote: vi.fn(async () => ({ id: "conv-remote", title: "Renamed", createdAt: 100, updatedAt: 300, messageCount: 2 })),
}));

describe("SessionSidebar", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it("renders remote sessions after refresh", async () => {
    render(createElement(SessionSidebar, { activeConversationId: "", onLoadConversation: vi.fn(), onDeletedActive: vi.fn() }));

    await screen.findByText("Remote session");
    expect(listConversationsRemote).toHaveBeenCalled();
  });

  it("renames and deletes sessions", async () => {
    const promptSpy = vi.spyOn(window, "prompt").mockReturnValue("Renamed");
    const onDeletedActive = vi.fn();
    render(createElement(SessionSidebar, { activeConversationId: "conv-remote", onLoadConversation: vi.fn(), onDeletedActive }));

    await screen.findByText("Remote session");
    fireEvent.click(screen.getByTitle("Rename"));
    await waitFor(() => expect(renameConversationRemote).toHaveBeenCalledWith("conv-remote", "Renamed"));

    fireEvent.click(screen.getByTitle("Delete"));
    await waitFor(() => expect(deleteConversationRemote).toHaveBeenCalledWith("conv-remote"));
    expect(onDeletedActive).toHaveBeenCalled();
    promptSpy.mockRestore();
  });
});
