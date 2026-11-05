/** Which screen you land on. */
import { act, screen } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import Root, { AppRoutes, forgetOnSwitch } from "../src/Gate";
import {
  CAMPAIGN,
  dashboardRoutes,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

const SIGN_IN_LINE = "Use the email and password of your party account.";

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the gate", () => {
  it("asks a signed-out visitor to sign in", () => {
    stubApi({});
    renderApp(<Root />);

    expect(screen.getByText(SIGN_IN_LINE)).toBeInTheDocument();
  });

  it.each([false, true])("shows the public home at /, signed in: %s", async (signedIn) => {
    if (signedIn) signIn("manager");
    stubApi({ "GET /site/": { name: "Umoja Party", description: "For every ward." } });
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("heading", { name: "Umoja Party" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: signedIn ? /My account$/ : "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: signedIn ? "Sign in" : /My account$/ })).toBeNull();
  });

  it.each([
    [{ role: "manager", is_superuser: false, party_roles: [] }, "/campaign"],
    [{ role: null, is_superuser: false, party_roles: ["membership_officer"] }, "/party"],
    [{ role: "manager", is_superuser: true, party_roles: [] }, "/console"],
  ])("sends a signed-in %o from /signin to %s", (user, home) => {
    signIn(user.role);
    useAuth.setState({ user: { ...useAuth.getState().user, ...user } });
    stubApi({});
    renderApp(<><AppRoutes /><Where /></>, { path: "/signin" });

    expect(screen.getByTestId("where")).toHaveTextContent(home);
  });

  it("sends a signed-out visit to /console to /signin", () => {
    stubApi({});
    renderApp(<><AppRoutes /><Where /></>, { path: "/console" });

    expect(screen.getByText(SIGN_IN_LINE)).toBeInTheDocument();
    expect(screen.getByTestId("where")).toHaveTextContent("/signin");
  });

  it.each(["candidate", "manager", "mobilizer"])(
    "tells a %s on no campaign so, offers no setup, and lets them sign out",
    async (role) => {
      const user = userEvent.setup();
      signIn(role);
      stubApi(dashboardRoutes({ "GET /campaigns/": [] }));
      renderApp(<Root />);

      expect(
        await screen.findByText("You are not on a campaign yet"),
      ).toBeInTheDocument();
      expect(
        screen.queryByText(/New campaign|Set up your campaign/),
      ).toBeNull();
      await user.click(screen.getByRole("button", { name: "Sign out" }));
      expect(useAuth.getState().token).toBeNull();
    },
  );

  it("sends a signed-in user with a campaign to the dashboard", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<Root />);

    expect(
      await screen.findByRole("region", { name: "Win number" }),
    ).toBeInTheDocument();
  });

  it("forgets the last user's campaign the moment someone else signs in", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": [{ ...CAMPAIGN, candidate_name: "Kimani Njoroge" }],
      }),
    );
    const { queryClient } = renderApp(<Root />);
    const stop = forgetOnSwitch(queryClient);
    await screen.findAllByText("Kimani Njoroge");

    act(() => {
      useAuth.getState().logout();
      signIn("candidate");
    });
    stop();

    expect(queryClient.getQueryData(["campaigns"])).toBeUndefined();
  });
});
