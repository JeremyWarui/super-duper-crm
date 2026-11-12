import { afterEach, describe, expect, it, vi } from "vitest";
import { api, upload } from "../src/api/client";
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

  it("keeps the user signed in when a public request is refused with a 401", async () => {
    signIn();
    stubApi({ "GET /party/places/": { status: 401, body: { detail: "No." } } });

    await expect(api("/party/places/", { anonymous: true })).rejects.toThrow("No.");
    expect(useAuth.getState().token).toBe(TEST_TOKEN);
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

  it("reads an upload's refusal the way it reads any other, with its status and code", async () => {
    signIn();
    stubApi({ "POST /files/": { status: 413, body: { file: ["The file is larger than 5 MB."], code: "too_large" } } });

    await expect(upload("/files/", new Blob(["x"]), { area: "site" })).rejects.toMatchObject({
      message: "The file is larger than 5 MB.",
      status: 413,
      code: "too_large",
    });
  });
});
