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
  organisation_type: "aspirant",
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
  "GET /party/posts/?kind=news&offset=0": [],
  "GET /party/posts/?kind=event&offset=0": [],
  "GET /party/places/": [],
  "GET /party/slides/": [],
  "GET /party/issues/": [ISSUE],
  "GET /party/issues/i1/": ISSUE,
  "GET /party/videos/": [{ id: "v1", title: "Town hall in Kahawa", url: "https://example.com/v1", duration: "4:10", thumbnail_url: "" }],
  "GET /party/documents/": [{ id: "d1", title: "Campaign plan (PDF)", url: "https://example.com/plan.pdf" }],
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

describe("an aspirant installation's website", () => {
  it("lays the homepage out as the party's: carousel with the candidate beside it, then three ways to take part", async () => {
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

  it("rotates published slides in the hero, and shows the site's slogan when there are none", async () => {
    const slide = { id: "s1", kicker: "Roysambu 2027", headline: "Water for every ward", line: "", image_url: "", button_label: "", button_url: "" };
    stubApi({ ...ROUTES, "GET /party/slides/": [slide] });
    const first = renderApp(<AppRoutes />);
    expect(await screen.findByRole("heading", { name: "Water for every ward", level: 1 })).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Volunteer for Jane" }).length).toBeGreaterThan(0);
    first.unmount();

    stubApi(ROUTES);
    renderApp(<AppRoutes />);
    expect(await screen.findByRole("heading", { name: "Roysambu first", level: 1 })).toBeInTheDocument();
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

  it.each(["/join-party", "/candidates", "/counties", "/vie", "/results"])(
    "sends the party-only %s home",
    async (path) => {
      stubApi(ROUTES);
      renderApp(<AppRoutes />, { path });

      expect(await screen.findByRole("heading", { name: "Jane Wanjiku" })).toBeInTheDocument();
    },
  );

  it.each([
    ["/", "Roysambu first", "A teacher for twenty years."],
    ["/volunteer", "Volunteer", "Support Jane"],
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
      "GET /party/places/?ward=w1": [{ id: "c1", name: "Zimmerman Primary" }],
      "POST /site/volunteer/": { message: "Thank you.", withdraw_code: "abc" },
    });
    renderApp(<AppRoutes />, { path: "/volunteer" });
    const user = userEvent.setup();
    const form = within((await screen.findByRole("heading", { name: "Support Jane" })).closest("form"));

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

describe("an aspirant installation when signed in", () => {
  const CONSOLE = {
    ...ROUTES,
    "GET /admin/overview/": { totals: ADMIN_TOTALS, campaigns: [ADMIN_CAMPAIGN] },
    // A staff login among them, the row a party installation offers offices on.
    "GET /admin/users/": ADMIN_USERS.map((u) => ({ ...u, party_roles: [], party_member: null })),
    "GET /admin/audit/": [{ id: "a1", created_at: "2026-11-01T08:00:00+00:00", actor_name: "root", action: "party.post.create", detail: {} }],
    "GET /admin/backups/": [],
    "GET /admin/health/": {
      version: "0.1.0",
      migration: { current: "x", head: "x", up_to_date: true },
      database: { reachable: true, detail: "", size_bytes: 1 },
      organisation_type: "aspirant",
      services: [],
      last_backup: null,
      disks: [],
    },
  };

  function signInAsSuperuser() {
    useAuth.setState({
      token: TEST_TOKEN,
      user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true, party_roles: [] },
    });
  }

  it("sends the superuser from /party to the console", async () => {
    signInAsSuperuser();
    stubApi(CONSOLE);
    renderApp(<AppRoutes />, { path: "/party/aspirants" });

    expect(await screen.findByRole("button", { name: /Campaigns \(/ })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Aspirants" })).toBeNull();
  });

  it("never says party in the console and calls no party-only route", async () => {
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
    await screen.findByText("wafula");
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Site settings" }));
    await screen.findByRole("button", { name: "Save the site settings" });
    await user.click(screen.getByRole("button", { name: "Help" }));
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Audit" }));
    expect(await screen.findByText("site.post.create")).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Health" }));
    await screen.findByText("aspirant");
    expect(document.body.textContent).not.toMatch(/party/i);

    await user.click(screen.getByRole("button", { name: "Export" }));
    expect(document.body.textContent).not.toMatch(/party/i);

    const shared = /^\/party\/(posts|places|slides|issues|documents|videos|subscribe|unsubscribe)\b/;
    expect(calls.filter((c) => /party/.test(c.path) && !shared.test(c.path))).toEqual([]);
  });

  it.each([
    ["supporters", "Supporters"],
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

describe("the party workspace's recruitment page", () => {
  it("gives a coordinator their link, its QR code and their applicants", async () => {
    signIn("coordinator");
    stubApi(
      dashboardRoutes({
        "GET /site/": { name: "Umoja Party", organisation_type: "party" },
        "GET /campaigns/": [{ ...CAMPAIGN, kind: "party", seat: "National", area_name: "" }],
        "GET /party/workspace/recruitment/": { code: "Zx9", by_status: { pending: 4, approved: 2 } },
      }),
    );
    renderApp(<App />, { path: "/campaign/recruitment" });

    expect(await screen.findByText(/\/join-party\?r=Zx9$/)).toBeInTheDocument();
    expect(screen.getByTitle("Recruitment link QR code")).toBeInTheDocument();
    expect(screen.getByText("Waiting for a decision").nextSibling.textContent).toBe("4");
  });

  it("gives a coordinator a read-only list of the members in their area, with no export", async () => {
    signIn("coordinator");
    const member = { id: "pm1", full_name: "Achieng Otieno", phone: "+254712345678", status: "approved", ward: "w1", ward_name: "Zimmerman", registration_centre: null, registration_centre_name: "" };
    stubApi(
      dashboardRoutes({
        "GET /site/": { name: "Umoja Party", organisation_type: "party" },
        "GET /campaigns/": [{ ...CAMPAIGN, kind: "party", seat: "National", area_name: "" }],
        "GET /party/workspace/members/": { total: 1, page: 1, page_size: 50, members: [member] },
      }),
    );
    renderApp(<App />, { path: "/campaign/members" });

    const list = await screen.findByRole("region", { name: "Party members" });
    expect(await within(list).findByText("Achieng Otieno")).toBeInTheDocument();
    expect(within(list).getByText("Approved")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Party members" })).toBeInTheDocument();
    expect(within(list).queryAllByRole("button")).toEqual([]);
    expect(screen.queryByRole("button", { name: /export/i })).toBeNull();
  });
});
