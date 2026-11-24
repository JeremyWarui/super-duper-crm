import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import InviteForm from "../src/pages/campaign/InviteForm";
import { INVITE_RESULT, renderApp, signIn } from "./helpers";

afterEach(() => vi.unstubAllGlobals());

const EVENT = { id: "e1", title: "Town hall", venue: "", ward_name: "Zimmerman" };
const PREVIEW = { ...INVITE_RESULT, dry_run: true, requested: 2, estimated_cost_cents: 160 };

// Answers each invite POST when the test calls the returned release function.
function heldInvites() {
  const posts = [];
  const pending = [];
  vi.stubGlobal("fetch", vi.fn((url, options = {}) => {
    const body = JSON.parse(options.body);
    posts.push(body);
    return new Promise((resolve) => pending.push(() => resolve(new Response(JSON.stringify(body.dry_run ? PREVIEW : INVITE_RESULT), { status: 200, headers: { "Content-Type": "application/json" } }))));
  }));
  return { posts, release: () => pending.shift()() };
}

describe("inviting contacts to an event", () => {
  it("offers Send only for the settings the preview on screen priced", async () => {
    signIn("manager");
    const { posts, release } = heldInvites();
    renderApp(<InviteForm event={EVENT} onClose={() => {}} />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Preview" }));
    await user.click(screen.getByRole("button", { name: "Opposed" }));
    release();
    await waitFor(() => expect(screen.getByRole("button", { name: "Preview" })).toBeEnabled());
    expect(screen.queryByText(/Would cost/)).toBeNull();
    expect(screen.queryByRole("button", { name: /^Send to/ })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Preview" }));
    release();
    expect(await screen.findByText("Would cost about KES 1.60")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Send to 2 people" }));
    await waitFor(() => expect(posts).toHaveLength(3));
    expect(posts[2]).toMatchObject({ support_levels: ["supporter", "undecided", "opposed"], dry_run: false });
  });
});
