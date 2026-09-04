import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import { API } from "./helpers";

function stubLogin(status, body) {
  const calls = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url, options) => {
      calls.push({ url, body: JSON.parse(options.body) });
      return { ok: status < 400, status, json: async () => body };
    }),
  );
  return calls;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the auth store", () => {
  it("starts signed out", () => {
    expect(useAuth.getState().token).toBeNull();
    expect(useAuth.getState().user).toBeNull();
  });

  it("keeps the token and the role a successful sign-in returns", async () => {
    stubLogin(200, {
      token: "abc123",
      user: { id: "u1", username: "amina", full_name: "Amina Kariuki", role: "manager" },
    });

    const user = await useAuth.getState().login("amina", "secret");

    expect(useAuth.getState().token).toBe("abc123");
    expect(useAuth.getState().user.role).toBe("manager");
    expect(user.full_name).toBe("Amina Kariuki");
  });

  it("posts to the sign-in route with no token of its own", async () => {
    const calls = stubLogin(200, { token: "abc123", user: { role: "manager" } });

    await useAuth.getState().login("amina", "secret");

    expect(calls[0].url).toBe(`${API}/auth/login/`);
    expect(calls[0].body).toEqual({ username: "amina", password: "secret" });
  });

  it("raises the server's rejection message", async () => {
    stubLogin(400, { non_field_errors: ["Unable to log in with the provided credentials."] });

    await expect(useAuth.getState().login("amina", "wrong")).rejects.toThrow(
      "Unable to log in with the provided credentials.",
    );
  });

  it("stays signed out after a rejected sign-in", async () => {
    stubLogin(400, { non_field_errors: ["Nope."] });

    await expect(useAuth.getState().login("amina", "wrong")).rejects.toThrow();

    expect(useAuth.getState().token).toBeNull();
  });

  it("falls back to a plain message when the server explains nothing", async () => {
    stubLogin(500, {});

    await expect(useAuth.getState().login("amina", "secret")).rejects.toThrow(
      /wrong username or password/i,
    );
  });

  it("clears the token and the user on sign-out", async () => {
    stubLogin(200, { token: "abc123", user: { role: "manager" } });
    await useAuth.getState().login("amina", "secret");

    useAuth.getState().logout();

    expect(useAuth.getState().token).toBeNull();
    expect(useAuth.getState().user).toBeNull();
  });

  it("writes the session to storage, so a refresh stays signed in", async () => {
    stubLogin(200, { token: "abc123", user: { role: "manager" } });

    await useAuth.getState().login("amina", "secret");

    expect(JSON.parse(localStorage.getItem("campaign-auth")).state.token).toBe("abc123");
  });
});
