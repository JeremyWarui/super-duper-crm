import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { AppRoutes } from "../src/Gate";
import { CAMPAIGN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

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

const ROUTES = {
  "GET /site/": SITE,
  "GET /site/candidate/": PAGE,
  "GET /party/posts/?kind=news&offset=0": [],
  "GET /party/posts/?kind=event&offset=0": [],
  "GET /party/places/": [],
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
  it("shows the candidate page at / and the volunteer form at /volunteer", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("heading", { name: "Jane Wanjiku" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Support Jane" })).toBeInTheDocument();
  });

  it.each(["/join-party", "/candidates", "/counties", "/vie", "/about", "/results"])(
    "sends the party-only %s home",
    async (path) => {
      stubApi(ROUTES);
      renderApp(<AppRoutes />, { path });

      expect(await screen.findByRole("heading", { name: "Jane Wanjiku" })).toBeInTheDocument();
    },
  );

  it.each([
    ["/", "Jane Wanjiku", "A teacher for twenty years."],
    ["/volunteer", "Volunteer", "Support Jane"],
    ["/contribute", "Contribute", "M-Pesa paybill 123456"],
    ["/privacy", "Privacy notice", "We keep your data safe."],
    ["/news", "News", null],
    ["/events", /Events/, null],
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
});
