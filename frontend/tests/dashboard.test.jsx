/** The superuser's party dashboard in the portal. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const BOARD = {
  approved_members: 1234,
  pending_applications: 56,
  active_volunteers: 78,
  volunteers_by_county: [{ county_id: "c1", county: "Nakuru", count: 78 }],
  volunteers_by_interest: [{ interest: "events", count: 40 }],
  approved_aspirants: 9,
  active_campaigns: 7,
  active_subscriptions: 6,
  events_from: "2026-11-01",
  events_to: "2026-12-01",
  upcoming_events_by_county: [{ county_id: "c1", county: "Nakuru", count: 3 }],
  upcoming_events_by_seat: [{ seat: "mp", count: 3 }],
  campaigns_by_county_and_seat: [{ county_id: "c1", county: "Nakuru", seat: "mp", count: 2 }],
  revenue: { start: "2026-01-01", end: "2026-12-31", total_kes: 250000, count: 12 },
};

const ROUTES = {
  "GET /party/": { name: "Umoja Party" },
  "GET /party/places/": [{ id: "c1", name: "Nakuru" }],
  "GET /party/aspirants/": { total: 0, items: [] },
  "GET /party/dashboard/": BOARD,
};

function openDashboard() {
  signIn("manager");
  useAuth.setState({ user: { ...useAuth.getState().user, is_superuser: true } });
  const calls = stubApi(ROUTES);
  renderApp(<Root />, { path: "/party" });
  return calls;
}

describe("the party dashboard", () => {
  it("shows the API's figures as tiles", async () => {
    openDashboard();

    const tile = async (label) => (await screen.findByText(label)).nextSibling.textContent;

    expect(await tile("Approved members")).toBe("1,234");
    expect(await tile("Pending applications")).toBe("56");
    expect(await tile("Active campaigns")).toBe("7");
    expect(await tile("Recorded CRM revenue")).toBe("KES 250,000");
  });

  it("asks again with a filter once one is chosen", async () => {
    const user = userEvent.setup();
    const calls = openDashboard();

    await screen.findByText("Approved members");
    await screen.findByRole("option", { name: "Nakuru" });
    await user.selectOptions(screen.getByLabelText("County"), "c1");
    await user.selectOptions(screen.getByLabelText("Seat"), "mp");

    await waitFor(() =>
      expect(calls.map((c) => c.path)).toContain("/party/dashboard/?county=c1&seat=mp"),
    );
  });
});
