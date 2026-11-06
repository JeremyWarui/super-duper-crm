/** A party nominee's workspace: the party feed, and the counts its candidate shares back. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { CAMPAIGN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const OFF = { event_reach: false, ward_coverage: false, supporter_counts: false };
const FEED = {
  events: [{ id: "p1", title: "Party rally in Zimmerman", body: "", event_date: "2026-11-20", venue: "Grounds", published_on: "2026-11-01" }],
  notices: [],
  members_by_ward: [{ ward_id: "w1", ward: "Zimmerman", count: 40 }],
  sharing: OFF,
  can_change: true,
  history: [],
};

function open(role, feed = FEED, kind = "hosted") {
  signIn(role);
  const calls = stubApi(dashboardRoutes({
    "GET /campaigns/": [{ ...CAMPAIGN, kind }],
    "GET /party-feed/": feed,
    "PUT /party-feed/sharing/": { ...OFF, supporter_counts: true },
  }));
  renderApp(<Root />, { path: "/campaign/party" });
  return calls;
}

describe("the party feed", () => {
  it("shows the candidate the party's events and member counts, and shares supporter counts on a switch", async () => {
    const user = userEvent.setup();
    const calls = open("candidate");

    const feed = await screen.findByRole("region", { name: "From the party" });
    expect(within(feed).getByText("Party rally in Zimmerman")).toBeInTheDocument();
    expect(within(feed).getByText("40 approved party members in your area")).toBeInTheDocument();
    await user.click(screen.getByRole("switch", { name: "Supporter counts by ward" }));

    await vi.waitFor(() => expect(calls.find((c) => c.method === "PUT")?.body).toEqual({ ...OFF, supporter_counts: true }));
    expect(screen.getByRole("switch", { name: "Supporter list" })).toBeDisabled();
  });

  it("lets the manager read the switches but not change them", async () => {
    open("manager", { ...FEED, can_change: false });

    expect(await screen.findByRole("switch", { name: "Event reach summary" })).toBeDisabled();
    expect(screen.getByText("Only the candidate changes what the campaign shares.")).toBeInTheDocument();
  });

  it("is not in a workspace the party does not host", async () => {
    open("candidate", FEED, "standalone");

    expect(await screen.findByRole("link", { name: "Messages" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Party feed" })).toBeNull();
  });
});
