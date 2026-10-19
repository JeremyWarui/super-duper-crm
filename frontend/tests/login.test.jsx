import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { useAuth } from "../src/store/auth";
import { fakeSecret, renderApp } from "./helpers";

const PASSWORD = fakeSecret();

function stubLogin(status, body) {
  vi.stubGlobal(
    "fetch",
    vi.fn(async () => ({ ok: status < 400, status, json: async () => body })),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const OK = {
  token: fakeSecret(),
  user: { id: "u1", username: "amina", full_name: "Amina Kariuki", role: "manager" },
};

describe("the sign-in screen", () => {

  it("signs in and leaves the token in the store", async () => {
    const user = userEvent.setup();
    stubLogin(200, OK);
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], PASSWORD);
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(useAuth.getState().token).toBe(OK.token));
  });

  it("shows the server's rejection instead of failing silently", async () => {
    const user = userEvent.setup();
    stubLogin(400, { non_field_errors: ["Unable to log in with the provided credentials."] });
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], "wrong{Enter}");

    expect(
      await screen.findByText("Unable to log in with the provided credentials."),
    ).toBeInTheDocument();
    expect(useAuth.getState().token).toBeNull();
  });
});

describe("signing up", () => {
  const NEW_USER = {
    token: fakeSecret(),
    user: { id: "u2", username: "jane", full_name: "Jane Wanjiru", role: "candidate" },
  };

  async function openSignUp(user) {
    const rendered = renderApp(<Login />);
    await user.click(screen.getByRole("button", { name: "Start a campaign" }));
    return rendered;
  }

  it("sends the role the aspirant picked, and signs them straight in", async () => {
    const user = userEvent.setup({ delay: null });
    const calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url, options) => {
        calls.push({ url, body: JSON.parse(options.body) });
        return { ok: true, status: 201, json: async () => NEW_USER };
      }),
    );
    const { container } = await openSignUp(user);

    await user.type(container.querySelectorAll("input")[0], "Jane");
    await user.type(container.querySelectorAll("input")[1], "Wanjiru");
    await user.type(container.querySelectorAll("input")[2], "jane");
    await user.type(container.querySelectorAll("input")[3], PASSWORD);
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(useAuth.getState().token).toBe(NEW_USER.token));
    expect(calls[0].url).toContain("/auth/register/");
    expect(calls[0].body).toMatchObject({
      username: "jane",
      role: "candidate",
      first_name: "Jane",
      last_name: "Wanjiru",
    });
  });

});
