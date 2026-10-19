/** Which of the three screens you land on. */
import { screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import { useCampaigns } from "../src/api/hooks";
import App from "../src/App";
import Login from "../src/components/Login";
import Onboarding from "../src/components/Onboarding";
import {
  dashboardRoutes,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

// The gate from src/main.jsx.
function SignedIn() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const needsSetup =
    campaigns.isSuccess && campaigns.data.length === 0 && role !== "mobilizer";
  return needsSetup ? <Onboarding onDone={() => campaigns.refetch()} /> : <App />;
}

function Root() {
  const token = useAuth((s) => s.token);
  return token ? <SignedIn /> : <Login />;
}

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
