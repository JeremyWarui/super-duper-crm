import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Login from "../src/components/Login";
import { useAuth } from "../src/store/auth";
import { renderApp } from "./helpers";

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
  token: "abc123",
  user: { id: "u1", username: "amina", full_name: "Amina Kariuki", role: "manager" },
};

describe("the sign-in screen", () => {
  it("asks for a username and a password", () => {
    renderApp(<Login />);

    expect(screen.getByText("Username")).toBeInTheDocument();
    expect(screen.getByText("Password")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign in" })).toBeInTheDocument();
  });

  it("keeps the button dead until both fields are filled", async () => {
    const user = userEvent.setup();
    const { container } = renderApp(<Login />);
    const button = screen.getByRole("button", { name: "Sign in" });
    expect(button).toBeDisabled();

    await user.type(container.querySelectorAll("input")[0], "amina");
    expect(button).toBeDisabled();

    await user.type(container.querySelectorAll("input")[1], "secret");
    expect(button).toBeEnabled();
  });

  it("hides what is typed into the password field", () => {
    const { container } = renderApp(<Login />);
    expect(container.querySelectorAll("input")[1]).toHaveAttribute("type", "password");
  });

  it("signs in and leaves the token in the store", async () => {
    const user = userEvent.setup();
    stubLogin(200, OK);
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], "secret");
    await user.click(screen.getByRole("button", { name: "Sign in" }));

    await waitFor(() => expect(useAuth.getState().token).toBe("abc123"));
  });

  it("submits on Enter, so the form works without reaching for the mouse", async () => {
    const user = userEvent.setup();
    stubLogin(200, OK);
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], "secret{Enter}");

    await waitFor(() => expect(useAuth.getState().token).toBe("abc123"));
  });

  it("trims a username that was pasted with a stray space", async () => {
    const user = userEvent.setup();
    const calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url, options) => {
        calls.push(JSON.parse(options.body));
        return { ok: true, status: 200, json: async () => OK };
      }),
    );
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "  amina  ");
    await user.type(container.querySelectorAll("input")[1], "secret{Enter}");

    await waitFor(() => expect(calls[0].username).toBe("amina"));
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
