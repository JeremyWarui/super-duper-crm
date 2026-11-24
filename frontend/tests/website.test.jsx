/** The workspace's website editor. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

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

const ROUTES = dashboardRoutes({
  "POST /workspace/site/images/": { status: 201, body: { id: "f1", url: UPLOADED } },
  "GET /workspace/site/candidate/": { name: "Jane", photo_url: "", bio: "", priorities: [], published: false },
  "GET /workspace/site/posts/": [POST],
  "POST /workspace/site/posts/": { ...POST, id: "p2" },
  "PATCH /workspace/site/posts/p1/": { ...POST, published: true },
  "DELETE /workspace/site/posts/p1/": { status: 204, body: null },
});

const sent = (calls, method, path) => calls.find((c) => c.method === method && c.path === path);

async function openWebsite() {
  signIn("manager");
  const calls = stubApi(ROUTES);
  renderApp(<App />, { path: "/campaign/website" });
  await userEvent.setup().click(await screen.findByRole("button", { name: "News" }));
  await screen.findByText("Congress opens");
  return calls;
}

describe("the website editor", () => {
  it("puts the page's content in the main landmark", async () => {
    await openWebsite();

    expect(within(screen.getByRole("main")).getByText("Congress opens")).toBeInTheDocument();
  });

  it("saves the post's text as the editor's formatted HTML", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.click(screen.getByRole("button", { name: "Bold" }));
    await user.type(screen.getByRole("textbox", { name: "Text" }), "Come early");
    await user.click(screen.getByRole("button", { name: "Add post" }));

    await waitFor(() => expect(sent(calls, "POST", "/workspace/site/posts/")?.body.body).toBe("<p><strong>Come early</strong></p>"));
  });

  it("uploads a statement's signed PDF to the documents area", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.selectOptions(screen.getByLabelText("Label"), "statement");
    await user.type(screen.getByLabelText("Title"), "On prices");
    await user.upload(screen.getByLabelText("Choose a file for Signed PDF (optional)"), new File(["%PDF-1.7"], "s.pdf", { type: "application/pdf" }));
    await waitFor(() => expect(screen.getByLabelText("Signed PDF (optional)")).toHaveValue(UPLOADED));
    await user.click(screen.getByRole("button", { name: "Add post" }));

    expect(sent(calls, "POST", "/workspace/site/images/").body.get("area")).toBe("documents");
    await waitFor(() => expect(sent(calls, "POST", "/workspace/site/posts/")?.body.pdf_url).toBe(UPLOADED));
  });

  it("uploads a chosen image and saves its address on the post", async () => {
    const user = userEvent.setup();
    const url = UPLOADED;
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.upload(screen.getByLabelText("Choose a file for Image (optional)"), new File(["png"], "rally.png", { type: "image/png" }));
    await waitFor(() => expect(screen.getByLabelText("Image (optional)")).toHaveValue(url));
    await user.click(screen.getByRole("button", { name: "Add post" }));

    expect(sent(calls, "POST", "/workspace/site/images/").body.get("area")).toBe("site");
    await waitFor(() => expect(sent(calls, "POST", "/workspace/site/posts/")?.body.image_url).toBe(url));
  });

  it("adds, publishes and deletes a post through its routes", async () => {
    const user = userEvent.setup();
    const calls = await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));
    await user.type(screen.getByLabelText("Title"), "Rally next week");
    await user.click(screen.getByRole("button", { name: "Add post" }));
    await waitFor(() =>
      expect(sent(calls, "POST", "/workspace/site/posts/")?.body).toEqual({
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
      expect(sent(calls, "PATCH", "/workspace/site/posts/p1/")?.body).toEqual({ published: true }),
    );

    await user.click(screen.getByRole("button", { name: "Delete" }));
    const dialog = screen.getByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(sent(calls, "DELETE", "/workspace/site/posts/p1/")).toBeDefined());
  });

  it("saves slides with the order the editor gives them", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      ...ROUTES,
      "GET /workspace/site/slides/": [{ id: "s1", headline: "Jobs for all", kicker: "", line: "", button_label: "", button_url: "", image_url: "", sort_order: 1, published: true }],
      "GET /workspace/site/issues/": [],
      "POST /workspace/site/slides/": { id: "s2" },
      "PATCH /workspace/site/slides/s1/": { id: "s1" },
    });
    signIn("manager");
    renderApp(<App />, { path: "/campaign/website" });
    await user.click(await screen.findByRole("button", { name: "Homepage" }));

    await user.click(await screen.findByRole("button", { name: "New slide" }));
    await user.type(screen.getByLabelText("Headline"), "Fair prices");
    await user.clear(screen.getByLabelText(/^Order/));
    await user.type(screen.getByLabelText(/^Order/), "2");
    await user.click(screen.getByRole("button", { name: "Add slide" }));
    await waitFor(() =>
      expect(sent(calls, "POST", "/workspace/site/slides/")?.body).toMatchObject({ headline: "Fair prices", sort_order: 2 }),
    );

    await user.click(screen.getByRole("button", { name: "Edit" }));
    await user.clear(screen.getByLabelText(/^Order/));
    await user.type(screen.getByLabelText(/^Order/), "3");
    await user.click(screen.getByRole("button", { name: "Save slide" }));
    await waitFor(() =>
      expect(sent(calls, "PATCH", "/workspace/site/slides/s1/")?.body).toEqual({ sort_order: 3 }),
    );
  });

  it("offers news only: events are put on the website from Events", async () => {
    const user = userEvent.setup();
    await openWebsite();

    await user.click(screen.getByRole("button", { name: "New post" }));

    expect(screen.queryByLabelText("Kind")).toBeNull();
    expect(screen.queryByLabelText("Date")).toBeNull();
  });
});
