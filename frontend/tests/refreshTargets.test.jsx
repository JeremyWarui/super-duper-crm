import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("refreshing targets", () => {
  it("lets the manager recompute win numbers from the latest register", async () => {
    signIn("manager");
    const calls = stubApi(dashboardRoutes({ "POST /targets/refresh/": { units: 2, win_number: 12001, total_registered: 40000, grain: "ward", note: null } }));
    renderApp(<App />, { path: "/campaign/targets" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Refresh targets" }));

    expect(await screen.findByText(/win number 12,001/)).toBeInTheDocument();
    await waitFor(() => expect(calls.find((c) => c.path === "/targets/refresh/").body).toEqual({ campaign: "c1" }));
  });

});
