import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/api/client";
import { useAuth } from "../src/store/auth";
import { TEST_TOKEN, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the API client", () => {
  it("sends the token as the scheme the server expects", async () => {
    signIn();
    const calls = stubApi({ "GET /campaigns/": [] });

    await api("/campaigns/");

    expect(calls[0].options.headers.Authorization).toBe(`Token ${TEST_TOKEN}`);
  });

  it("signs the user out when the token stops working", async () => {
    signIn();
    stubApi({ "GET /campaigns/": { status: 401, body: { detail: "Invalid token." } } });

    await expect(api("/campaigns/")).rejects.toThrow(/session expired/i);
    expect(useAuth.getState().token).toBeNull();
  });

  it("raises the server's message rather than a status code", async () => {
    signIn();
    stubApi({
      "POST /events/": {
        status: 400,
        body: { detail: "Attendance cannot exceed the number reached." },
      },
    });

    await expect(api("/events/", { method: "POST", body: {} })).rejects.toThrow(
      "Attendance cannot exceed the number reached.",
    );
  });

});
