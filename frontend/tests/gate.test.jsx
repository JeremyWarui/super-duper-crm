/** Which of the three screens you land on. */
import { act, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import Root, { forgetOnSwitch } from "../src/Gate";
import {
  CAMPAIGN,
  dashboardRoutes,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the gate", () => {
  it("asks a signed-out visitor to sign in", () => {
    stubApi({});
    renderApp(<Root />);

    expect(screen.getByText("Sign in to the war room")).toBeInTheDocument();
  });

  it("sends a signed-in user with no campaign to set one up", async () => {
    signIn("candidate");
    stubApi({ ...dashboardRoutes({ "GET /campaigns/": [] }), "GET /counties/": [] });
    renderApp(<Root />);

    expect(await screen.findByText(/Set up your campaign/)).toBeInTheDocument();
  });

  it("sends a signed-in user with a campaign to the dashboard", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<Root />);

    expect(await screen.findByText("VOTES TO WIN THE SEAT")).toBeInTheDocument();
  });

  it("forgets the last user's campaign the moment someone else signs in", async () => {
    signIn("manager");
    stubApi(dashboardRoutes({ "GET /campaigns/": [{ ...CAMPAIGN, title: "Kimani for Kiambu" }] }));
    const { queryClient } = renderApp(<Root />);
    const stop = forgetOnSwitch(queryClient);
    await screen.findAllByText("Kimani for Kiambu");

    act(() => {
      useAuth.getState().logout();
      signIn("candidate");
    });
    stop();

    expect(queryClient.getQueryData(["campaigns"])).toBeUndefined();
  });

  it("does not offer setup to a mobilizer, who is not allowed to run it", async () => {
    signIn("mobilizer");
    stubApi(dashboardRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />);

    expect(await screen.findByText(/No campaign yet/)).toBeInTheDocument();
    expect(screen.queryByText(/Set up your campaign/)).toBeNull();
  });

});

// The half of the reported bug this file can see. That the server stops handing
// a fresh manager somebody else's campaign is a backend test
// (test_campaigns_api.py, test_manager_signup_flow.py); what the gate owes is
// the aspirant question once that list comes back empty.
