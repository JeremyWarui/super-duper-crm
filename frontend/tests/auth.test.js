import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import { fakeSecret } from "./helpers";

const TOKEN = fakeSecret();
const PASSWORD = fakeSecret();

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

  it("keeps the token and the role a successful sign-in returns", async () => {
    stubLogin(200, {
      token: TOKEN,
      user: { id: "u1", username: "amina", full_name: "Amina Kariuki", role: "manager" },
    });

    const user = await useAuth.getState().login("amina", PASSWORD);

    expect(useAuth.getState().token).toBe(TOKEN);
    expect(useAuth.getState().user.role).toBe("manager");
    expect(user.full_name).toBe("Amina Kariuki");
  });

  it("raises the server's rejection message", async () => {
    stubLogin(400, { non_field_errors: ["Unable to log in with the provided credentials."] });

    await expect(useAuth.getState().login("amina", "wrong")).rejects.toThrow(
      "Unable to log in with the provided credentials.",
    );
  });

  it("clears the token and the user on sign-out", async () => {
    stubLogin(200, { token: TOKEN, user: { role: "manager" } });
    await useAuth.getState().login("amina", PASSWORD);

    useAuth.getState().logout();

    expect(useAuth.getState().token).toBeNull();
    expect(useAuth.getState().user).toBeNull();
  });

});
