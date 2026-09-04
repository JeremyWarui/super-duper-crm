import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "../src/api/client";
import { useAuth } from "../src/store/auth";
import { API, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the API client", () => {
  it("sends the token as the scheme the server expects", async () => {
    signIn();
    const calls = stubApi({ "GET /campaigns/": [] });

    await api("/campaigns/");

    expect(calls[0].options.headers.Authorization).toBe("Token test-token");
  });

  it("omits the header entirely when nobody is signed in", async () => {
    const calls = stubApi({ "POST /supporters/": { id: "s1" } });

    await api("/supporters/", { method: "POST", body: { full_name: "Wanjiku" } });

    expect(calls[0].options.headers.Authorization).toBeUndefined();
  });

  it("sends the body as JSON", async () => {
    signIn();
    const calls = stubApi({ "POST /events/": { id: "e1" } });

    await api("/events/", { method: "POST", body: { title: "Rally" } });

    expect(calls[0].options.headers["Content-Type"]).toBe("application/json");
    expect(calls[0].body).toEqual({ title: "Rally" });
  });

  it("prefixes every path with the API base", async () => {
    signIn();
    stubApi({ "GET /targets/": [] });

    await api("/targets/");

    expect(fetch).toHaveBeenCalledWith(`${API}/targets/`, expect.anything());
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

  it("reads a field error out of its list", async () => {
    signIn();
    stubApi({
      "POST /supporters/": { status: 400, body: { consent_given: ["Consent is required."] } },
    });

    await expect(api("/supporters/", { method: "POST", body: {} })).rejects.toThrow(
      "Consent is required.",
    );
  });

  it("falls back to a readable message when the body says nothing", async () => {
    signIn();
    stubApi({ "GET /strategy/": { status: 500, body: null } });

    await expect(api("/strategy/")).rejects.toThrow("Request failed.");
  });

  it("returns null for a no-content reply rather than failing to parse it", async () => {
    signIn();
    stubApi({ "DELETE /events/e1/": { status: 204, body: null } });

    await expect(api("/events/e1/", { method: "DELETE" })).resolves.toBeNull();
  });
});
