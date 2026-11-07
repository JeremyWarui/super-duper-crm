import { screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { useAuth } from "../src/store/auth";
import { fakeSecret, renderApp, stubApi } from "./helpers";

const SIGNED = { token: fakeSecret(), user: { id: "u1", username: "root", full_name: "Root", role: null, is_superuser: true, party_roles: [] } };

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("Google sign-in", () => {
  it("is not offered until the installation has it set up", async () => {
    stubApi({ "GET /auth/options/": { google: false } });
    renderApp(<Login />);

    await screen.findByRole("button", { name: "Sign in" });
    expect(screen.queryByRole("button", { name: "Sign in with Google" })).toBeNull();
  });

  it("finishes from the handoff in the address, with this tab's value", async () => {
    sessionStorage.setItem("google-sign-in-bind", "bind-from-this-tab");
    const calls = stubApi({ "POST /auth/google/finish/": SIGNED, "GET /auth/options/": { google: true } });
    renderApp(<Login />, { path: "/signin?google=h4nd0ff" });

    await waitFor(() => expect(useAuth.getState().token).toBe(SIGNED.token));
    expect(calls.find((c) => c.path === "/auth/google/finish/").body).toEqual({ handoff: "h4nd0ff", bind: "bind-from-this-tab" });
    expect(sessionStorage.getItem("google-sign-in-bind")).toBeNull();
  });

  it("says why Google refused", async () => {
    stubApi({ "GET /auth/options/": { google: true } });
    renderApp(<Login />, { path: "/signin?google_error=unknown" });

    expect(await screen.findByRole("alert")).toHaveTextContent("has no login here");
    expect(await screen.findByRole("button", { name: "Sign in with Google" })).toBeInTheDocument();
  });
});
