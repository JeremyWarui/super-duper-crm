import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { ADMIN_CAMPAIGN, ADMIN_TOTALS, ADMIN_USERS, CAMPAIGN, TEST_TOKEN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const SITE = {
  name: "Jane 2027",
  short_name: "J",
  slogan: "Roysambu first",
  contact_phone: "0700 000000",
  payment_instructions: "M-Pesa paybill 123456",
  privacy_notice: "We keep your data safe.",
  privacy_notice_version: "1",
  subscribe_consent_wording: "I agree to campaign news.",
  social_links: {},
};

const PAGE = {
  slug: "",
  name: "Jane Wanjiku",
  seat: "mp",
  area: "Roysambu",
  county: "Nairobi City",
  photo_url: "",
  slogan: "Roysambu first",
  bio: "A teacher for twenty years.",
  priorities: [{ title: "Water", text: "Piped water in every ward." }],
  office_address: "",
  office_phone: "",
  office_email: "",
  events: [],
  volunteering_open: true,
  consent_wording: "I agree the campaign may contact me.",
  wards: [{ id: "w1", name: "Zimmerman" }],
};

const ISSUE = { id: "i1", title: "Clean water", summary: "Water in every home.", what_we_will_do: "Drill boreholes", why_it_matters: "Health." };

const ROUTES = {
  "GET /site/": SITE,
  "GET /site/candidate/": PAGE,
  "GET /website/posts/?kind=news&offset=0": [],
  "GET /website/posts/?kind=event&offset=0": [],
  "GET /website/places/": [],
  "GET /website/slides/": [],
  "GET /website/issues/": [ISSUE],
  "GET /website/issues/i1/": ISSUE,
  "GET /website/videos/": [{ id: "v1", title: "Town hall in Kahawa", url: "https://example.com/v1", duration: "4:10", thumbnail_url: "" }],
  "GET /website/documents/": [{ id: "d1", title: "Campaign plan (PDF)", url: "https://example.com/plan.pdf" }],
};

/** The visible text of a page once its heading and `loaded` show. */
async function textOf(path, heading, loaded) {
  stubApi(ROUTES);
  const { unmount } = renderApp(<AppRoutes />, { path });
  await screen.findByRole("heading", { name: heading, level: 1 });
  if (loaded) await screen.findByText(loaded);
  const text = document.body.textContent;
  unmount();
  return text;
}

describe("the campaign website", () => {
  it("lays the homepage out: carousel with the candidate beside it, then three ways to take part", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("heading", { name: "Jane Wanjiku" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Three ways to take part" })).toBeInTheDocument();
    expect(screen.queryByText(/Chip in/)).toBeNull();
  });

  it("shows what the Website editor publishes on the homepage, and links every page from the menu", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("heading", { name: "Why Jane?" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /Clean water/ })).toHaveAttribute("href", "/issues/i1");
    expect(screen.getAllByRole("link", { name: "Give now" })[0]).toHaveAttribute("href", "/contribute");
    const menu = screen.getAllByRole("link").map((a) => a.getAttribute("href"));
    for (const path of ["/about", "/agenda", "/media", "/volunteer"]) expect(menu).toContain(path);
  });

  it("shows each agenda issue as a card with its photo behind the title", async () => {
    stubApi({ ...ROUTES, "GET /website/issues/": [{ ...ISSUE, image_url: "https://example.org/water.jpg" }] });
    renderApp(<AppRoutes />);

    const card = await screen.findByRole("link", { name: /Clean water/ });
    expect(card).toHaveAttribute("href", "/issues/i1");
    expect(card.querySelector("img")).toHaveAttribute("src", "https://example.org/water.jpg");
  });

  it("rotates published slides in the hero, and shows the candidate page's slogan when there are none", async () => {
    const slide = { id: "s1", kicker: "Roysambu 2027", headline: "Water for every ward", line: "", image_url: "", button_label: "", button_url: "" };
    stubApi({ ...ROUTES, "GET /website/slides/": [slide] });
    const first = renderApp(<AppRoutes />);
    expect(await screen.findByRole("heading", { name: "Water for every ward", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Volunteer for Jane" }).length).toBeGreaterThan(0);
    first.unmount();

    stubApi({ ...ROUTES, "GET /site/": { ...SITE, slogan: "An old site slogan" } });
    renderApp(<AppRoutes />);
    expect(await screen.findByRole("heading", { name: "Roysambu first", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByText("Vying for MP · Roysambu").length).toBeGreaterThan(0);
  });

  it.each([
    ["/about", "Jane Wanjiku", "A teacher for twenty years."],
    ["/agenda", "Agenda", "Clean water"],
    ["/media", "Videos & documents", "Campaign plan (PDF)"],
    ["/issues/i1", "Clean water", "Drill boreholes"],
  ])("serves %s with no party word", async (path, heading, loaded) => {
    const text = await textOf(path, heading, loaded);

    expect(text).not.toMatch(/party/i);
  });

  it.each([
    ["/", "Roysambu first", "A teacher for twenty years."],
    ["/volunteer", "Volunteer", "Volunteer for Jane"],
    ["/contribute", "Contribute", "M-Pesa paybill 123456"],
    ["/privacy", "Privacy notice", "We keep your data safe."],
    ["/news", "News", null],
    ["/events", /Events/, null],
    ["/signin", "The team behind the movement.", "Use the email and password of your campaign account."],
  ])("never says party on %s", async (path, heading, loaded) => {
    const text = await textOf(path, heading, loaded);

    expect(text).not.toMatch(/party/i);
  });

  it("signs a volunteer up through the campaign's own form", async () => {
    const calls = stubApi({
      ...ROUTES,
      "GET /website/places/?ward=w1": [{ id: "c1", name: "Zimmerman Primary" }],
      "POST /site/volunteer/": { message: "Thank you.", withdraw_code: "abc" },
    });
    renderApp(<AppRoutes />, { path: "/volunteer" });
    const user = userEvent.setup();
    await screen.findByRole("heading", { name: "Volunteer for Jane" });
    const form = within(document.querySelector("form"));

    await user.type(form.getByLabelText("First name"), "Wanjiru");
    await user.type(form.getByLabelText("Last name"), "Kamau");
    await user.type(form.getByLabelText("Email"), "wanjiru@example.com");
    await user.type(form.getByLabelText("Phone"), "0712 345678");
    await user.selectOptions(form.getByLabelText("Ward"), "w1");
    await user.selectOptions(await form.findByLabelText("Polling station"), "c1");
    await user.selectOptions(form.getByLabelText("Profession"), "teacher");
    await user.click(form.getAllByRole("checkbox")[0]);
    await user.selectOptions(form.getByLabelText("Preferred contact"), "sms");
    await user.click(form.getByRole("checkbox", { name: /campaign may contact me/ }));
    await user.click(form.getByRole("button", { name: "I'll volunteer" }));

    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.path).toBe("/site/volunteer/"));
    expect(await screen.findByText(/\/volunteer\/withdraw\/abc/)).toBeInTheDocument();
  });
});

describe("the console and workspace", () => {
  const CONSOLE = {
    ...ROUTES,
    "GET /admin/overview/": { totals: ADMIN_TOTALS, campaigns: [ADMIN_CAMPAIGN] },
    "GET /admin/users/": ADMIN_USERS,
    "GET /admin/audit/": [{ id: "a1", created_at: "2026-11-01T08:00:00+00:00", actor_name: "root", action: "site.post.create", detail: {} }],
    "GET /admin/backups/": [],
    "GET /admin/health/": {
      version: "0.1.0",
      migration: { current: "x", head: "x", up_to_date: true },
      database: { reachable: true, detail: "", size_bytes: 1 },
      services: [],
      last_backup: null,
      disks: [],
    },
  };

  function signInAsSuperuser() {
    useAuth.setState({
      token: TEST_TOKEN,
      user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true },
    });
  }

  it("never says party in the console and calls only the site's shared routes", async () => {
    signInAsSuperuser();
    const calls = stubApi(CONSOLE);
    renderApp(<AppRoutes />, { path: "/console" });
    const user = userEvent.setup();

    const logins = await screen.findByRole("button", { name: /Logins/ });
    expect(screen.getByRole("navigation", { name: "Campaign admin" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Console" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Members" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Notifications/ })).toBeNull();
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(logins);
    await user.click(await screen.findByRole("button", { name: "Add a login" }));
    await screen.findByText("amina");
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Site settings" }));
    await screen.findByRole("button", { name: "Save the site settings" });
    await user.click(screen.getByRole("button", { name: "Help" }));
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Audit" }));
    expect(await screen.findByText("site.post.create")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Health" }));
    await screen.findByText("0.1.0");
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Export" }));
    expect(document.body.textContent).not.toMatch(/party/i);

    expect(calls.filter((c) => /party/.test(c.path))).toEqual([]);
  });

  it.each([
    ["supporters", "Contacts"],
    ["volunteers", "Volunteers"],
  ])("never says party on the workspace's %s page", async (page, heading) => {
    signIn("manager");
    stubApi(dashboardRoutes({ ...ROUTES, "GET /campaigns/c1/volunteers/": [] }));
    renderApp(<App />, { path: `/campaign/${page}` });

    await screen.findByRole("heading", { name: heading });
    await screen.findByText(page === "volunteers" ? /None yet/ : /Private to your campaign team/);
    expect(document.body.textContent).not.toMatch(/party/i);
  });
});

describe("the workspace website", () => {
  it("lets comms save the candidate page through site.write", async () => {
    signIn("comms");
    const calls = stubApi(
      dashboardRoutes({
        ...ROUTES,
        "GET /workspace/site/candidate/": { ...PAGE, published: false },
        "PUT /workspace/site/candidate/": { ...PAGE, published: true },
      }),
    );
    renderApp(<App />, { path: "/campaign/website" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("checkbox", { name: "Published on the website" }));
    await user.click(screen.getByRole("button", { name: "Save profile" }));

    await waitFor(() => expect(calls.some((c) => c.method === "PUT" && c.path === "/workspace/site/candidate/")).toBe(true));
    const sent = calls.find((c) => c.method === "PUT").body;
    expect(sent.published).toBe(true);
    expect(screen.getByRole("link", { name: "Settings" })).toBeInTheDocument();
  });

  it("does not offer the website to a coordinator", async () => {
    signIn("coordinator");
    stubApi(dashboardRoutes(ROUTES));
    renderApp(<App />);

    await screen.findByRole("link", { name: "Overview" });
    expect(screen.queryByRole("link", { name: "Website" })).toBeNull();
  });
});

