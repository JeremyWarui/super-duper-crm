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
  user: {
    id: "u1",
    username: "amina",
    full_name: "Amina Kariuki",
    role: "manager",
  },
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
    stubLogin(400, {
      non_field_errors: ["Unable to log in with the provided credentials."],
    });
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], "wrong{Enter}");

    expect(
      await screen.findByText(
        "Unable to log in with the provided credentials.",
      ),
    ).toBeInTheDocument();
    expect(useAuth.getState().token).toBeNull();
  });
});

describe("signing up", () => {
  it("is not offered: logins are handed out, not taken", () => {
    stubLogin(200, OK);
    renderApp(<Login />);

    expect(
      screen.queryByText(/start a campaign|sign up|create account/i),
    ).toBeNull();
    expect(screen.getAllByRole("button").map((b) => b.textContent)).toEqual([
      "",
      "Sign in",
    ]);
    expect(
      screen.getByText(/Ask whoever runs your campaign/),
    ).toBeInTheDocument();
  });
});
