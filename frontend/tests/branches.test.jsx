/** County branches: the party office's page, its officials, and the public branch page. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root, { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { PARTY, TEST_TOKEN, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const NAKURU = { id: "n32", name: "Nakuru" };
const NO_OFFICIALS = { current: [], upcoming: [], history: [] };

function signInAs(user) {
  useAuth.setState({ token: TEST_TOKEN, user: { id: "u1", username: "u1", full_name: "Office Holder", role: null, party_roles: [], ...user } });
}

describe("county branches", () => {
  it("lets the superuser write a county's branch office and publish it", async () => {
    const user = userEvent.setup();
    signInAs({ is_superuser: true });
    const calls = stubApi({
      "GET /site/": PARTY,
      "GET /party/office/branches/": [{ county: NAKURU, branch: null }],
      "GET /party/office/branches/n32/officials/": NO_OFFICIALS,
      "PUT /admin/party/branches/n32/": { county: NAKURU, officials: [], published: true },
    });
    renderApp(<Root />, { path: "/party/branches" });

    await user.click(await screen.findByRole("button", { name: "Nakuru" }));
    await user.type(screen.getByRole("textbox", { name: "Office address" }), "Kenyatta Avenue");
    await user.click(screen.getByRole("checkbox", { name: "Show this branch on the website" }));
    await user.click(screen.getByRole("button", { name: "Save branch" }));

    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({ office_address: "Kenyatta Avenue", published: true, next_meeting_on: null }));
  });

  it("lets the Membership Officer appoint an approved member as chairperson", async () => {
    const user = userEvent.setup();
    signInAs({ is_superuser: false, party_roles: ["membership_officer"] });
    const calls = stubApi({
      "GET /site/": PARTY,
      "GET /party/office/branches/": [{ county: NAKURU, branch: null }],
      "GET /party/office/branches/n32/officials/": NO_OFFICIALS,
      "GET /party/members/?q=wa&status=approved&county=n32": { total: 1, items: [{ id: "m1", full_name: "Wanjiru Kamau", phone: "+254700000001", ward: { name: "Biashara" } }] },
      "GET /party/members/?q=w&status=approved&county=n32": { total: 0, items: [] },
      "POST /party/office/branches/n32/officials/": { id: "t1" },
    });
    renderApp(<Root />, { path: "/party/branches" });

    await user.click(await screen.findByRole("button", { name: "Nakuru" }));
    const officials = await screen.findByRole("region", { name: "Officials" });
    expect(within(officials).getByRole("group", { name: "Chairperson" })).toHaveTextContent("Vacant");
    expect(screen.queryByRole("button", { name: "Save branch" })).toBeNull();

    await user.type(within(officials).getByRole("textbox", { name: /^Member/ }), "wa");
    await user.click(await within(officials).findByRole("button", { name: /Wanjiru Kamau/ }));
    await user.click(within(officials).getByRole("button", { name: "Appoint" }));

    await waitFor(() => expect(calls.find((c) => c.method === "POST")?.body).toMatchObject({ office: "chair", member: "m1", start_reason: "elected", minutes_file: null }));
  });

  it("shows a branch's officials, office and sub-branches", async () => {
    stubApi({
      "GET /site/": PARTY,
      "GET /party/branches/n32/": {
        county: NAKURU,
        officials: [{ office: "chair", label: "Chairperson", name: "Wanjiru Kamau" }],
        office_address: "Kenyatta Avenue, Nakuru",
        phone: "0700 111222",
        email: "",
        next_meeting_on: null,
        next_meeting_venue: "",
        constituencies: [{ id: "k1", name: "Naivasha", wards: [{ id: "w1", name: "Hells Gate" }] }],
      },
    });
    renderApp(<AppRoutes />, { path: "/counties/n32" });

    expect(await screen.findByRole("heading", { level: 1, name: "Nakuru County branch" })).toBeInTheDocument();
    expect(screen.getByText("Wanjiru Kamau")).toBeInTheDocument();
    expect(screen.getByText("Chairperson")).toBeInTheDocument();
    expect(screen.getByText("Hells Gate")).toBeInTheDocument();
    expect(screen.getByText("Kenyatta Avenue, Nakuru")).toBeInTheDocument();
  });
});
