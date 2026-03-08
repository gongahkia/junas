import { buildInviteLink, extractRoomSlugFromValue } from "./room-links";

describe("room link helpers", () => {
  it("extracts a room slug from raw slugs and invite URLs", () => {
    expect(extractRoomSlugFromValue("session-123")).toBe("session-123");
    expect(extractRoomSlugFromValue("join/session-123")).toBe("session-123");
    expect(
      extractRoomSlugFromValue("https://kilter-together.test/join/session-123")
    ).toBe("session-123");
    expect(
      extractRoomSlugFromValue("https://kilter-together.test/rooms/session-123")
    ).toBe("session-123");
  });

  it("rejects invalid join values", () => {
    expect(extractRoomSlugFromValue("")).toBeNull();
    expect(extractRoomSlugFromValue("https://kilter-together.test")).toBeNull();
    expect(extractRoomSlugFromValue("bad/value/here")).toBeNull();
  });

  it("builds an invite link from the current origin", () => {
    expect(buildInviteLink("session-123")).toBe(
      "http://localhost:3000/join/session-123"
    );
  });
});
