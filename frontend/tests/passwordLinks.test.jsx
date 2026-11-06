import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { fakeSecret, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  useAuth.getState().logout();
});

const SENT = "If that email has a login, a link to choose a new password is on its way.";
const SITE = { "GET /site/": { name: "Umoja Party", organisation_type: "party" } };
const ME = { id: "u1", username: "jane", full_name: "Jane", role: "manager", kind: "campaign", is_superuser: false, party_roles: [], member_account: false };

describe("forgot password", () => {
  it("asks for a link and shows the server's answer", async () => {
    const calls = stubApi({ ...SITE, "POST /auth/password-reset/": { detail: SENT } });
    renderApp(<AppRoutes />, { path: "/forgot-password" });
    const user = userEvent.setup();

    await user.type(await screen.findByRole("textbox", { name: "Email" }), " jane@example.com ");
    await user.click(screen.getByRole("button", { name: "Send the link" }));

    expect(await screen.findByText(SENT)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ email: "jane@example.com" });
  });
});

describe("an invite link", () => {
  it("sets the password once both entries match, and signs the person in", async () => {
    const [session, chosen] = [fakeSecret(), fakeSecret()];
    const calls = stubApi({
      ...SITE,
      "GET /auth/links/tok1/": { purpose: "invite", username: "jane", email: "jane@example.com" },
      "POST /auth/links/tok1/": { token: session, user: ME },
    });
    renderApp(<AppRoutes />, { path: "/invite/tok1" });
    const user = userEvent.setup();

    expect(await screen.findByRole("heading", { name: "Choose your password" })).toBeInTheDocument();
    await user.type(screen.getByLabelText("New password"), chosen);
    await user.type(screen.getByLabelText("The same password again"), `${chosen}x`);
    const save = screen.getByRole("button", { name: "Save and sign in" });
    expect(save).toBeDisabled();
    await user.clear(screen.getByLabelText("The same password again"));
    await user.type(screen.getByLabelText("The same password again"), chosen);
    await user.click(save);

    await waitFor(() => expect(useAuth.getState().token).toBe(session));
    expect(calls.find((c) => c.method === "POST").body).toEqual({ password: chosen });
  });

  it("says a spent link no longer works and offers a new one", async () => {
    stubApi({ ...SITE, "GET /auth/links/old/": { status: 400, body: { detail: "This link has expired or was already used. Ask for a new one." } } });
    renderApp(<AppRoutes />, { path: "/reset/old" });

    expect(await screen.findByRole("heading", { name: "This link no longer works" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Send a new link" })).toHaveAttribute("href", "/forgot-password");
  });
});
