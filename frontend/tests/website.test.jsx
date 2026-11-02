/** The superuser's website editor in the party portal. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const POST = {
  id: "p1",
  kind: "news",
  title: "Congress opens",
  body: "",
  image_url: "",
  event_date: null,
  venue: "",
  published_on: null,
  published: false,
  updated_at: "2026-11-01T00:00:00Z",
};

const ROUTES = {
  "GET /party/": { name: "Umoja Party" },
  "GET /admin/party/posts/": [POST],
  "GET /admin/party/leaders/": [],
  "POST /admin/party/posts/": { ...POST, id: "p2" },
  "PATCH /admin/party/posts/p1/": { ...POST, published: true },
  "DELETE /admin/party/posts/p1/": { status: 204, body: null },
};

const sent = (calls, method, path) => calls.find((c) => c.method === method && c.path === path);

function signInAsSuperuser() {
  signIn("manager");
  useAuth.setState({ user: { ...useAuth.getState().user, is_superuser: true } });
}

async function openWebsite() {
  signInAsSuperuser();
  const calls = stubApi(ROUTES);
  renderApp(<Root />, { path: "/party/website" });
  await screen.findByText("Congress opens");
  return calls;
}

describe("the website editor", () => {
  it("adds, publishes and deletes a post through its routes", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.click(screen.getByRole("button", { name: "Add post" }));
    await waitFor(() =>
      expect(sent(calls, "POST", "/admin/party/posts/")?.body).toEqual({
        kind: "news",
        title: "Rally next week",
        body: "",
        image_url: "",
      }),
    );

    await user.click(screen.getByRole("button", { name: "Publish" }));
    await waitFor(() =>
      expect(sent(calls, "PATCH", "/admin/party/posts/p1/")?.body).toEqual({ published: true }),
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(sent(calls, "DELETE", "/admin/party/posts/p1/")).toBeDefined());
  });

  it("saves an event only once it has a date", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.selectOptions(screen.getByLabelText("Kind"), "event");
    await user.type(screen.getByLabelText("Title"), "Nakuru rally");
    const add = screen.getByRole("button", { name: "Add post" });
    const offWithoutDate = add.disabled;
    await user.type(screen.getByLabelText("Date"), "2026-11-20");
    await user.click(add);

    expect(offWithoutDate).toBe(true);
    await waitFor(() =>
      expect(sent(calls, "POST", "/admin/party/posts/")?.body).toMatchObject({
        kind: "event",
        event_date: "2026-11-20",
      }),
    );
  });
});
