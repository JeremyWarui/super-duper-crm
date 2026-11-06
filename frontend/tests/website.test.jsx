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

const UPLOADED = "/api/files/0b6f1c1e-5a7d-4c1e-9f3a-2d4e6f8a0b1c/";

const ROUTES = {
  "POST /files/": { status: 201, body: { id: "f1", url: UPLOADED } },
  "GET /site/": { name: "Umoja Party" },
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
  it("uploads a chosen image and saves its address on the post", async () => {
    const user = userEvent.setup();
    const url = UPLOADED;
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.upload(screen.getByLabelText("Choose a file for Image (optional)"), new File(["png"], "rally.png", { type: "image/png" }));
    await waitFor(() => expect(screen.getByLabelText("Image (optional)")).toHaveValue(url));
    await user.click(screen.getByRole("button", { name: "Add post" }));

    expect(sent(calls, "POST", "/files/").body.get("area")).toBe("site");
    await waitFor(() => expect(sent(calls, "POST", "/admin/party/posts/")?.body.image_url).toBe(url));
  });

  it("adds, publishes and deletes a post through its routes", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.click(screen.getByRole("button", { name: "Add post" }));
    await waitFor(() =>
      expect(sent(calls, "POST", "/admin/party/posts/")?.body).toEqual({
        kind: "news",
        label: "news",
        title: "Rally next week",
        place: "",
        author: "",
        author_photo_url: "",
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

  it("saves slides with the order the editor gives them", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      ...ROUTES,
      "GET /admin/party/slides/": [{ id: "s1", headline: "Jobs for all", kicker: "", line: "", button_label: "", button_url: "", image_url: "", sort_order: 1, published: true }],
      "GET /admin/party/issues/": [],
      "POST /admin/party/slides/": { id: "s2" },
      "PATCH /admin/party/slides/s1/": { id: "s1" },
    });
    signInAsSuperuser();
    renderApp(<Root />, { path: "/party/website" });
    await user.click(await screen.findByRole("button", { name: "Homepage" }));

    await user.click(await screen.findByRole("button", { name: "New slide" }));
    await user.type(screen.getByLabelText("Headline"), "Fair prices");
    await user.clear(screen.getByLabelText(/^Order/));
    await user.type(screen.getByLabelText(/^Order/), "2");
    await user.click(screen.getByRole("button", { name: "Add slide" }));
    await waitFor(() =>
      expect(sent(calls, "POST", "/admin/party/slides/")?.body).toMatchObject({ headline: "Fair prices", sort_order: 2 }),
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText(/^Order/));
    await user.type(screen.getByLabelText(/^Order/), "3");
    await user.click(screen.getByRole("button", { name: "Save slide" }));
    await waitFor(() =>
      expect(sent(calls, "PATCH", "/admin/party/slides/s1/")?.body).toEqual({ sort_order: 3 }),
    );
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
