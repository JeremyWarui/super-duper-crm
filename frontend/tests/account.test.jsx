/** Where a login lands after sign-in, and the member's own account page. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { PARTY, TEST_TOKEN, dashboardRoutes, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PLACE = { id: "w1", name: "Zimmerman" };
const ACCOUNT = {
  first_name: "Achieng",
  full_name: "Achieng Otieno",
  phone: "07•• ••• 678",
  email: "achieng@example.com",
  status: "approved",
  ward: PLACE,
  constituency: { id: "k1", name: "Roysambu" },
  county: { id: "n1", name: "Nairobi" },
  registration_centre: { id: "c1", name: "Zimmerman Primary" },
  member_since: "2026-10-01T08:00:00Z",
  consent_wording: "I agree to membership.",
  consent_at: "2026-10-01T08:00:00Z",
  volunteer: {
    status: "active",
    profession: "teacher",
    profession_other: "",
    areas: ["fundraising"],
    area_other: "",
    preferred_contact: "sms",
    consent_wording: "I agree to volunteer contact.",
    consent_at: "2026-10-01T08:00:00Z",
  },
};

function signInAs(user) {
  useAuth.setState({
    token: TEST_TOKEN,
    user: { id: "u1", username: "achieng", full_name: "Achieng Otieno", role: null, is_superuser: false, party_roles: [], kind: "member", member_account: true, ...user },
  });
}

const routes = (overrides = {}) => ({
  "GET /site/": { ...PARTY, volunteer_consent_wording: "I agree to volunteer contact." },
  "GET /account/": ACCOUNT,
  "GET /party/posts/": [],
  ...overrides,
});

describe("after sign-in", () => {
  it("opens a member login's account", async () => {
    signInAs({});
    stubApi(routes());
    renderApp(<AppRoutes />, { path: "/signin" });

    expect(await screen.findByRole("heading", { name: "Habari, Achieng" })).toBeInTheDocument();
  });

  it("asks a campaign login linked to a member where to go", async () => {
    signInAs({ kind: "campaign", role: "manager" });
    stubApi({ ...routes(), ...dashboardRoutes() });
    renderApp(<AppRoutes />, { path: "/signin" });

    expect(await screen.findByRole("heading", { name: /Where to\?/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /My membership/ })).toHaveAttribute("href", "/account");
    expect(screen.getByRole("link", { name: /Campaign workspace/ })).toHaveAttribute("href", "/campaign");
  });
});

describe("the member's account", () => {
  it("shows the card, the volunteer details, the empty tasks state and party events", async () => {
    signInAs({});
    stubApi(routes({ "GET /party/posts/": [{ id: "e1", kind: "event", title: "Nairobi town hall", event_date: "2026-11-20", venue: "KICC" }] }));
    renderApp(<AppRoutes />, { path: "/account" });

    expect(await screen.findByRole("region", { name: "Member card" })).toHaveTextContent("Zimmerman, Nairobi");
    expect(screen.getByText("Fundraising Support")).toBeInTheDocument();
    expect(screen.getByText(/No tasks yet/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: "Party events" }));
    expect(await screen.findByRole("link", { name: "Nairobi town hall" })).toBeInTheDocument();
  });

  it("changes the volunteer details, then stops and is offered the form again", async () => {
    const user = userEvent.setup();
    signInAs({});
    const changed = { ...ACCOUNT, volunteer: { ...ACCOUNT.volunteer, areas: ["fundraising", "door_to_door"] } };
    const calls = stubApi(routes({
      "PUT /account/volunteer/": changed,
      "POST /account/volunteer/stop/": { ...ACCOUNT, volunteer: null },
    }));
    renderApp(<AppRoutes />, { path: "/account" });

    await user.click(await screen.findByRole("button", { name: "Change my volunteer details" }));
    await user.click(screen.getByRole("checkbox", { name: "Door-to-door Campaign" }));
    await user.click(screen.getByRole("button", { name: "Save my volunteer details" }));
    expect(await screen.findByText("Fundraising Support, Door-to-door Campaign")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "My data & privacy" }));
    await user.click(screen.getByRole("button", { name: "Stop volunteering" }));
    await user.click(screen.getByRole("tab", { name: "Volunteering" }));

    expect(await screen.findByRole("button", { name: "Volunteer for events" })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "PUT").body.areas).toEqual(["fundraising", "door_to_door"]);
  });

  it("offers a member who does not volunteer the volunteer form", async () => {
    signInAs({});
    stubApi(routes({ "GET /account/": { ...ACCOUNT, volunteer: null } }));
    renderApp(<AppRoutes />, { path: "/account" });

    expect(await screen.findByRole("button", { name: "Volunteer for events" })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Profession" })).toBeInTheDocument();
  });

  it("returns to sign-in when the session is refused", async () => {
    signInAs({});
    stubApi(routes({ "GET /account/": { status: 401, body: { detail: "Invalid token." } } }));
    renderApp(<AppRoutes />, { path: "/account" });

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
  });

  it("leaves the party and ends the session", async () => {
    const user = userEvent.setup();
    signInAs({});
    const calls = stubApi(routes({ "POST /account/leave/": { status: 204, body: null } }));
    renderApp(<AppRoutes />, { path: "/account" });

    await user.click(await screen.findByRole("tab", { name: "My data & privacy" }));
    await user.click(screen.getByRole("button", { name: "Leave the party" }));
    await user.click(screen.getByRole("button", { name: "Yes, leave the party" }));

    await waitFor(() => expect(useAuth.getState().token).toBeNull());
    expect(calls.some((c) => c.method === "POST" && c.path === "/account/leave/")).toBe(true);
  });
});

describe("applying to vie", () => {
  const NOTICE = { title: "Nominations 2027", opens_on: "2026-10-25", closes_on: "2026-11-10", requirements: "", open: true, seats: [] };
  const APPLICATION = {
    id: "as1", seat: "mca", area: "Zimmerman", status: "draft", status_reason: null, fee_kes: 5000, fee_paid: false,
    declared_at: null, from_window: true, documents: [],
  };

  it("starts an application for the chosen seat and holds submission until the fee is marked paid", async () => {
    const user = userEvent.setup();
    signInAs({});
    const calls = stubApi(routes({
      "GET /party/nominations/mine/": { window: NOTICE, choices: [{ seat: "mca", fee_kes: 5000, area: "Zimmerman" }, { seat: "mp", fee_kes: 0, area: "Roysambu" }], application: null },
      "POST /party/nominations/mine/": { status: 201, body: { window: NOTICE, choices: [], application: APPLICATION } },
    }));
    renderApp(<AppRoutes />, { path: "/account" });

    await user.click(await screen.findByRole("tab", { name: "My nomination" }));
    await user.click(await screen.findByRole("radio", { name: /Member of County Assembly|MCA/ }));
    await user.click(screen.getByRole("button", { name: "Start application" }));
    await user.click(await screen.findByRole("checkbox", { name: /I confirm the information/ }));

    expect(calls.find((c) => c.method === "POST").body).toEqual({ seat: "mca" });
    expect(screen.getByText(/KES 5,000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Submit application" })).toBeDisabled();
  });
});
