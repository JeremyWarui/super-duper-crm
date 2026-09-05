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

  it("reveals the password when the eye is clicked, and hides it again", async () => {
    const user = userEvent.setup();
    const { container } = renderApp(<Login />);
    const field = () => container.querySelectorAll("input")[1];

    await user.type(field(), "campaign1234");
    expect(field()).toHaveAttribute("type", "password");

    await user.click(screen.getByRole("button", { name: "Show password" }));
    expect(field()).toHaveAttribute("type", "text");
    expect(field()).toHaveValue("campaign1234");

    await user.click(screen.getByRole("button", { name: "Hide password" }));
    expect(field()).toHaveAttribute("type", "password");
    expect(field()).toHaveValue("campaign1234");
  });

  it("says whether the password is showing, for a screen reader", async () => {
    const user = userEvent.setup();
    renderApp(<Login />);

    const eye = screen.getByRole("button", { name: "Show password" });
    expect(eye).toHaveAttribute("aria-pressed", "false");

    await user.click(eye);
    expect(screen.getByRole("button", { name: "Hide password" })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
  });

  it("does not sign in when the eye is clicked", async () => {
    const user = userEvent.setup();
    stubLogin(200, OK);
    const { container } = renderApp(<Login />);

    await user.type(container.querySelectorAll("input")[0], "amina");
    await user.type(container.querySelectorAll("input")[1], "secret");
    await user.click(screen.getByRole("button", { name: "Show password" }));

    expect(fetch).not.toHaveBeenCalled();
    expect(useAuth.getState().token).toBeNull();
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

describe("signing up", () => {
  const NEW_USER = {
    token: "signup-token",
    user: { id: "u2", username: "jane", full_name: "Jane Wanjiru", role: "candidate" },
  };

  async function openSignUp(user) {
    const rendered = renderApp(<Login />);
    await user.click(screen.getByRole("button", { name: "Start a campaign" }));
    return rendered;
  }

  it("is reachable from the sign-in screen and goes back", async () => {
    const user = userEvent.setup({ delay: null });
    await openSignUp(user);

    expect(screen.getByRole("button", { name: "Create account" })).toBeInTheDocument();
    expect(screen.getByText("Which are you?")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Sign in" }));
    expect(screen.queryByText("Which are you?")).not.toBeInTheDocument();
  });

  it("offers the aspirant and the manager, starting on the aspirant", async () => {
    const user = userEvent.setup({ delay: null });
    await openSignUp(user);

    expect(screen.getByRole("button", { name: /I'm the aspirant/ })).toHaveAttribute(
      "aria-pressed",
      "true",
    );
    expect(screen.getByRole("button", { name: /I run the campaign/ })).toHaveAttribute(
      "aria-pressed",
      "false",
    );
  });

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
    await user.type(container.querySelectorAll("input")[3], "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(useAuth.getState().token).toBe("signup-token"));
    expect(calls[0].url).toContain("/auth/register/");
    expect(calls[0].body).toMatchObject({
      username: "jane",
      role: "candidate",
      first_name: "Jane",
      last_name: "Wanjiru",
    });
  });

  it("sends role manager when that is the one picked", async () => {
    const user = userEvent.setup({ delay: null });
    const calls = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url, options) => {
        calls.push(JSON.parse(options.body));
        return { ok: true, status: 201, json: async () => NEW_USER };
      }),
    );
    const { container } = await openSignUp(user);

    await user.click(screen.getByRole("button", { name: /I run the campaign/ }));
    await user.type(container.querySelectorAll("input")[2], "amina");
    await user.type(container.querySelectorAll("input")[3], "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    await waitFor(() => expect(calls[0].role).toBe("manager"));
  });

  it("will not submit a password the API would reject", async () => {
    const user = userEvent.setup({ delay: null });
    const { container } = await openSignUp(user);

    await user.type(container.querySelectorAll("input")[2], "jane");
    await user.type(container.querySelectorAll("input")[3], "short");

    expect(screen.getByText("At least 8 characters.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Create account" })).toBeDisabled();
  });

  it("shows the server's reason when the username is taken", async () => {
    const user = userEvent.setup({ delay: null });
    stubLogin(400, { detail: "The username jane is already taken." });
    const { container } = await openSignUp(user);

    await user.type(container.querySelectorAll("input")[2], "jane");
    await user.type(container.querySelectorAll("input")[3], "a-real-password");
    await user.click(screen.getByRole("button", { name: "Create account" }));

    expect(await screen.findByText("The username jane is already taken.")).toBeInTheDocument();
    expect(useAuth.getState().token).toBeNull();
  });
});
