/** County branches: the superuser's console page and the public branch page. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root, { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { PARTY, TEST_TOKEN, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const NAKURU = { id: "n32", name: "Nakuru" };

describe("county branches", () => {
  it("lets the superuser write a county's branch and publish it", async () => {
    const user = userEvent.setup();
    useAuth.setState({ token: TEST_TOKEN, user: { id: "root", username: "root", full_name: "The Operator", role: null, is_superuser: true, party_roles: [] } });
    const calls = stubApi({
      "GET /site/": PARTY,
      "GET /admin/party/branches/": [{ county: NAKURU, branch: null }],
      "PUT /admin/party/branches/n32/": { county: NAKURU, chairperson: "Wanjiru Kamau", published: true },
    });
    renderApp(<Root />, { path: "/party/branches" });

    await user.click(await screen.findByRole("button", { name: "Nakuru" }));
    await user.type(screen.getByRole("textbox", { name: "Chairperson" }), "Wanjiru Kamau");
    await user.click(screen.getByRole("checkbox", { name: "Show this branch on the website" }));
    await user.click(screen.getByRole("button", { name: "Save branch" }));

    await waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toMatchObject({ chairperson: "Wanjiru Kamau", published: true, next_meeting_on: null }));
  });

  it("shows a branch's officials, office and sub-branches", async () => {
    stubApi({
      "GET /site/": PARTY,
      "GET /party/branches/n32/": {
        county: NAKURU,
        chairperson: "Wanjiru Kamau",
        secretary: "",
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
    expect(screen.getByText("Hells Gate")).toBeInTheDocument();
    expect(screen.getByText("Kenyatta Avenue, Nakuru")).toBeInTheDocument();
  });
});
