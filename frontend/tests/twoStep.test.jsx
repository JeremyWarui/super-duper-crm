import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useLocation } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import Security from "../src/pages/account/Security";
import Root, { forgetOnSwitch } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { TEST_TOKEN, fakeSecret, renderApp, signIn, stubApi } from "./helpers";

const PASSWORD = fakeSecret();
const SIGNED = { token: fakeSecret(), user: { id: "u1", username: "root", full_name: "Root", role: null, is_superuser: true, party_roles: [] } };
const ASK = { status: 400, body: { code_required: true, detail: "Enter the code.", non_field_errors: ["Enter the code."] } };

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("signing in with 2-step", () => {
  it("asks for the app's code after a right password, then sends it", async () => {
    const user = userEvent.setup();
    let asked = false;
    vi.stubGlobal("fetch", vi.fn(async (_url, options = {}) => {
      if (options.method !== "POST") return { ok: true, status: 200, json: async () => ({}) };
      const body = JSON.parse(options.body);
      const reply = body.code || asked ? { status: 200, body: SIGNED } : ASK;
      asked = true;
      return { ok: reply.status === 200, status: reply.status, json: async () => reply.body };
    }));
    const { container } = renderApp(<Login />);

    await user.type(screen.getByRole("textbox", { name: "Email" }), "root@example.com");
    await user.type(container.querySelector("input[type=password]"), `${PASSWORD}{Enter}`);
    await user.type(await screen.findByRole("textbox", { name: /Code from your app/ }), "123456{Enter}");

    await waitFor(() => expect(useAuth.getState().token).toBe(SIGNED.token));
    const sent = fetch.mock.calls.filter(([, o]) => o?.method === "POST").map(([, o]) => JSON.parse(o.body));
    expect(sent.at(-1)).toEqual({ email: "root@example.com", password: PASSWORD, code: "123456" });
  });

  it("finishes a Google sign-in from the handoff in the address", async () => {
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

describe("a login that needs 2-step", () => {
  it("is sent to set it up before anything opens", () => {
    signIn("manager");
    useAuth.setState({ user: { ...useAuth.getState().user, is_superuser: true, two_step_needed: true } });
    stubApi({});
    renderApp(<><Root /><Where /></>, { path: "/console" });

    expect(screen.getByTestId("where")).toHaveTextContent("/security");
  });

  it("scans a QR code, confirms a code and is shown its recovery codes once", async () => {
    const user = userEvent.setup();
    signIn("manager");
    const codes = Array.from({ length: 10 }, (_, i) => `abcde-fgh${i}k`);
    const key = fakeSecret().replace(/-/g, "").slice(0, 16).toUpperCase();
    const passedToken = fakeSecret();
    const calls = stubApi({
      "GET /auth/two-step/": { on: false, required: true, recovery_left: 0 },
      "POST /auth/two-step/start/": { secret: key, uri: `otpauth://totp/x?secret=${key}` },
      "POST /auth/two-step/confirm/": { codes, token: passedToken },
    });
    // The old token stops working the moment 2-step is on, as on the server.
    const answer = fetch;
    vi.stubGlobal("fetch", async (url, options = {}) =>
      String(url).endsWith("/auth/me/") && options.headers?.Authorization === `Token ${TEST_TOKEN}` && calls.some((c) => c.path === "/auth/two-step/confirm/")
        ? { ok: false, status: 401, json: async () => ({ detail: "Invalid token." }) }
        : answer(url, options));
    // The app's own rule for a token change runs here too.
    const { queryClient } = renderApp(<Security />);
    const stop = forgetOnSwitch(queryClient);

    await user.click(await screen.findByRole("button", { name: "Set up 2-step sign-in" }));
    expect(await screen.findByTitle("QR code for your authenticator app")).toBeInTheDocument();
    expect(screen.getByLabelText("Setup key")).toHaveTextContent(key.match(/.{4}/g).join(" "));
    await user.type(screen.getByRole("textbox", { name: /Code from your app/ }), "654321");
    await user.click(screen.getByRole("button", { name: "Turn on" }));

    const shown = await screen.findByRole("region", { name: "Recovery codes" });
    expect(shown).toHaveTextContent(codes[9]);
    expect(calls.find((c) => c.path === "/auth/two-step/confirm/").body).toEqual({ code: "654321" });
    expect(useAuth.getState()).toMatchObject({ token: passedToken, user: { two_step_needed: false } });
    stop();
  });
});
