/** Nominations in the party portal, the closed-campaign screen, and the console's member link. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import Root from "../src/Gate";
import {
  ADMIN_TOTALS,
  ADMIN_USERS,
  TEST_TOKEN,
  WORKSPACE_SECRET,
  aspirantRoutes,
  dashboardRoutes,
  renderApp,
  signIn,
  signInAsParty,
  stubApi,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function signInAsAdmin() {
  useAuth.setState({
    token: TEST_TOKEN,
    user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true, party_roles: [] },
  });
}

describe("the aspirants page", () => {
  it("shows a nominations officer Aspirants and not the member register", async () => {
    signInAsParty(["nominations_officer"]);
    stubApi(aspirantRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party" });

    expect(await screen.findByRole("button", { name: "Achieng Otieno" })).toBeInTheDocument();
    expect(screen.queryByText("Members")).toBeNull();
  });

  it("gives the superuser every party page", async () => {
    signInAsAdmin();
    stubApi(aspirantRoutes());
    renderApp(<Root />, { path: "/party/aspirants" });

    expect(await screen.findByRole("button", { name: "Achieng Otieno" })).toBeInTheDocument();
    for (const page of ["Members", "Volunteers", "Aspirants", "Console"]) {
      expect(screen.getAllByText(page).length).toBeGreaterThan(0);
    }
  });

  it("creates an approved aspirant's workspace and shows the password once", async () => {
    const user = userEvent.setup();
    signInAsParty(["nominations_officer"]);
    const calls = stubApi(aspirantRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party/aspirants" });

    await user.click(await screen.findByRole("button", { name: "Achieng Otieno" }));
    await user.type(await screen.findByLabelText("Aspirant's username"), "achieng");
    await user.type(screen.getByLabelText("Aspirant's email"), "achieng@example.com");
    await user.click(screen.getByRole("button", { name: "Create workspace" }));

    expect(await screen.findByText(WORKSPACE_SECRET)).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST")).toMatchObject({
      path: "/party/aspirants/as1/workspace/",
      body: { candidate: { username: "achieng", email: "achieng@example.com" } },
    });
  });
});

describe("a closed campaign", () => {
  it("shows its logins why, and lets them sign out", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": {
          status: 403,
          body: { detail: "This campaign is suspended by the party.", code: "campaign_suspended" },
        },
      }),
    );
    renderApp(<Root />);

    expect(await screen.findByText("This campaign is suspended by the party.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Sign out" })).toBeInTheDocument();
  });
});

describe("the console's member link", () => {
  it("links a staff login to an approved party member", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi({
      "GET /admin/overview/": { totals: ADMIN_TOTALS, campaigns: [] },
      "GET /admin/users/": ADMIN_USERS,
      "GET /party/members/": {
        total: 1,
        items: [{ id: "pm7", full_name: "Wafula Otieno", status: "approved" }],
      },
      "PUT /admin/users/u-wafula/party-member/": { ...ADMIN_USERS[3] },
    });
    renderApp(<Root />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await user.type(await screen.findByLabelText("Party member for wafula"), "Wafula");
    await user.click(await screen.findByRole("button", { name: "Wafula Otieno" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PUT")).toMatchObject({
        path: "/admin/users/u-wafula/party-member/",
        body: { member: "pm7" },
      }),
    );
  });
});

describe("the nominate dialog", () => {
  it("drops a refusal once another member is chosen", async () => {
    const user = userEvent.setup();
    signInAsParty(["nominations_officer"]);
    stubApi(
      aspirantRoutes({
        "GET /campaigns/": [],
        "GET /party/aspirants/candidates/": [
          { id: "pm1", full_name: "Achieng Otieno", ward: { id: "w1", name: "Githurai" } },
        ],
        "GET /party/places/": [{ id: "k1", name: "Nairobi City" }],
        "POST /party/aspirants/": {
          status: 403,
          body: { detail: "You cannot act on your own party record." },
        },
      }),
    );
    renderApp(<Root />, { path: "/party/aspirants" });

    await user.click(await screen.findByRole("button", { name: "Nominate a member" }));
    await user.type(screen.getByLabelText("Find a member"), "Achieng");
    await user.click(await screen.findByRole("button", { name: "Achieng Otieno · Githurai" }));
    await user.selectOptions(screen.getByLabelText("Seat"), "governor");
    await user.selectOptions(await screen.findByLabelText("County"), "k1");
    await user.click(screen.getByRole("button", { name: "Nominate" }));
    expect(await screen.findByText("You cannot act on your own party record.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Choose someone else" }));

    expect(screen.queryByText("You cannot act on your own party record.")).toBeNull();
  });
});
