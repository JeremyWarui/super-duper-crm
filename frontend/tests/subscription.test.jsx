/** A campaign's own subscription: the payment screen while locked, the banner while lapsing. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { CAMPAIGN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const INSTRUCTIONS = "M-Pesa Paybill 247247, account MCA-GITHURAI";

const subscription = (fields) => ({
  state: "active",
  held: false,
  dated_state: "active",
  paid_until: "2025-10-10",
  read_only_from: "2025-10-18",
  locks_on: "2025-10-25",
  payment_instructions: INSTRUCTIONS,
  plan: { name: "Ward monthly", price_kes: 5000, duration_days: 30 },
  last_paid_on: "2025-09-11",
  hold_reason: null,
  ...fields,
});

describe("a campaign's subscription", () => {
  it("shows a locked campaign how to pay instead of the app", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": {
          status: 403,
          body: { detail: "This campaign's subscription is not active.", code: "campaign_locked" },
        },
        "GET /subscription/": subscription({ state: "locked" }),
      }),
    );
    renderApp(<Root />);

    expect(await screen.findByText("This campaign's subscription ended on 10 Oct 2025.")).toBeInTheDocument();
    expect(screen.getByText(INSTRUCTIONS)).toBeInTheDocument();
    expect(screen.getByText(/KES 5,000/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Check again" })).toBeInTheDocument();
  });

  it("tells a campaign the party stopped why, and asks for no payment", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": {
          status: 403,
          body: { detail: "This campaign's subscription is not active.", code: "campaign_locked" },
        },
        "GET /subscription/": subscription({ state: "locked", held: true, dated_state: "active", hold_reason: "Cheque bounced" }),
      }),
    );
    renderApp(<Root />);

    expect(await screen.findByText("The party has stopped this campaign's access.")).toBeInTheDocument();
    expect(screen.getByText("The party's reason: Cheque bounced")).toBeInTheDocument();
    expect(screen.queryByText(INSTRUCTIONS)).toBeNull();
    expect(screen.queryByText(/KES 5,000/)).toBeNull();
  });

  it("asks a stopped campaign for payment too when its paid period has ended", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": {
          status: 403,
          body: { detail: "This campaign's subscription is not active.", code: "campaign_locked" },
        },
        "GET /subscription/": subscription({ state: "locked", held: true, dated_state: "read_only", hold_reason: "Audit" }),
      }),
    );
    renderApp(<Root />);

    expect(await screen.findByText(/it is read-only and locks on 25 Oct 2025; a payment is due/)).toBeInTheDocument();
    expect(screen.getByText(INSTRUCTIONS)).toBeInTheDocument();
  });

  it("warns a read-only campaign on its pages with the day it locks", async () => {
    signIn("manager");
    stubApi(dashboardRoutes({ "GET /subscription/": subscription({ state: "read_only" }) }));
    renderApp(<Root />, { path: "/campaign/overview" });

    const banner = await screen.findByRole("status");
    expect(banner).toHaveTextContent("Read-only since 18 Oct 2025");
    expect(banner).toHaveTextContent("the campaign locks on 25 Oct 2025");
  });

  it("shows the banner as soon as a check finds the campaign reopened read-only", async () => {
    const user = userEvent.setup();
    signIn("manager");
    const routes = dashboardRoutes({
      "GET /campaigns/": {
        status: 403,
        body: { detail: "This campaign's subscription is not active.", code: "campaign_locked" },
      },
      "GET /subscription/": subscription({ state: "locked", held: true, dated_state: "read_only" }),
    });
    stubApi(routes);
    renderApp(<Root />, { appCache: true });
    await screen.findByText("The party has stopped this campaign's access.");

    routes["GET /campaigns/"] = [CAMPAIGN];
    routes["GET /subscription/"] = subscription({ state: "read_only", dated_state: "read_only" });
    await user.click(screen.getByRole("button", { name: "Check again" }));

    expect(await screen.findByText(/Read-only since 18 Oct 2025/)).toBeInTheDocument();
  });
});
