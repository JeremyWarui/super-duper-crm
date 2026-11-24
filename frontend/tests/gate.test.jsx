/** Which screen you land on. */
import { act, screen, waitFor } from "@testing-library/react";
import { useLocation } from "react-router-dom";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import Root, { AppRoutes, forgetOnSwitch } from "../src/Gate";
import {
  CAMPAIGN,
  dashboardRoutes,
  fakeSecret,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

const SIGN_IN_LINE = "Use the email and password of your campaign account.";
const SITE = { "GET /site/": { name: "Jane for Kasarani" } };

function Where() {
  return <div data-testid="where">{useLocation().pathname}</div>;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the gate", () => {
  it("asks a signed-out visitor to sign in", async () => {
    stubApi(SITE);
    renderApp(<Root />);

    expect(await screen.findByText(SIGN_IN_LINE)).toBeInTheDocument();
  });

  it.each([false, true])("shows the public home at /, signed in: %s", async (signedIn) => {
    if (signedIn) signIn("manager");
    stubApi(SITE);
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("heading", { name: "Coming soon" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: signedIn ? /My account$/ : "Sign in" })).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: signedIn ? "Sign in" : /My account$/ })).toBeNull();
  });

  it.each([
    [{ role: "manager", is_superuser: false }, "/campaign"],
    [{ role: "manager", is_superuser: true }, "/console"],
  ])("sends a signed-in %o from /signin to %s", async (user, home) => {
    signIn(user.role);
    useAuth.setState({ user: { ...useAuth.getState().user, ...user } });
    stubApi({});
    renderApp(<><AppRoutes /><Where /></>, { path: "/signin" });

    await waitFor(() => expect(screen.getByTestId("where")).toHaveTextContent(home));
  });

  it("sends a signed-out visit to /console to /signin", async () => {
    stubApi(SITE);
    renderApp(<><AppRoutes /><Where /></>, { path: "/console" });

    expect(await screen.findByText(SIGN_IN_LINE)).toBeInTheDocument();
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
      await screen.findByRole("region", { name: "Seat target" }),
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

  it("keeps the public site settings and drops the staff's site drafts when someone else signs in", () => {
    signIn("manager");
    const { queryClient } = renderApp(<span />);
    queryClient.setQueryData(["site"], { name: "Jane for Kasarani" });
    queryClient.setQueryData(["site", "posts"], [{ id: "draft" }]);
    const stop = forgetOnSwitch(queryClient);

    act(() => {
      useAuth.getState().logout();
      signIn("candidate");
    });
    stop();

    expect(queryClient.getQueryData(["site"])).toEqual({ name: "Jane for Kasarani" });
    expect(queryClient.getQueryData(["site", "posts"])).toBeUndefined();
  });

  it("keeps cached reads when the same user gets a new token", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": [{ ...CAMPAIGN, candidate_name: "Kimani Njoroge" }],
      }),
    );
    const { queryClient } = renderApp(<Root />);
    const stop = forgetOnSwitch(queryClient);
    await screen.findAllByText("Kimani Njoroge");

    act(() => useAuth.setState({ token: fakeSecret() }));
    stop();

    expect(queryClient.getQueryData(["campaigns"])).toBeDefined();
  });
});
