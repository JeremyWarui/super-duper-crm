/** The party portal's members page. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { memberRoutes, renderApp, signIn, signInAsParty, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the members page", () => {
  it("lets a membership officer approve a pending member and refreshes the list", async () => {
    const user = userEvent.setup();
    signInAsParty(["membership_officer"]);
    const calls = stubApi(memberRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party/members" });

    await user.click(await screen.findByRole("button", { name: "Achieng Otieno" }));
    const lists = () => calls.filter((c) => c.method === "GET" && c.path.startsWith("/party/members/?")).length;
    const before = lists();
    await user.click(await screen.findByRole("button", { name: "Approve" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST")).toMatchObject({
        path: "/party/members/pm1/status/",
        body: { status: "approved" },
      }),
    );
    await waitFor(() => expect(lists()).toBeGreaterThan(before));
  });

  it("never shows the register to a login with no party role and no campaign", async () => {
    signIn("manager");
    const calls = stubApi(memberRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party/members" });

    expect(await screen.findByText("You are not on a campaign yet")).toBeInTheDocument();
    expect(screen.queryByText("Members")).toBeNull();
    expect(calls.some((c) => c.path.startsWith("/party/members"))).toBe(false);
  });
});
