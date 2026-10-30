/** Which screen you land on. */
import { act, screen } from "@testing-library/react";
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

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the gate", () => {
  it("asks a signed-out visitor to sign in", () => {
    stubApi({});
    renderApp(<Root />);

    expect(screen.getByText("Sign in to the war room")).toBeInTheDocument();
  });

  it("shows the sign-in screen at / when signed out", () => {
    stubApi({});
    renderApp(<AppRoutes />);

    expect(screen.getByText("Sign in to the war room")).toBeInTheDocument();
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
      await screen.findByText("VOTES TO WIN THE SEAT"),
    ).toBeInTheDocument();
  });

  it("forgets the last user's campaign the moment someone else signs in", async () => {
    signIn("manager");
    stubApi(
      dashboardRoutes({
        "GET /campaigns/": [{ ...CAMPAIGN, title: "Kimani for Kiambu" }],
      }),
    );
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
});
