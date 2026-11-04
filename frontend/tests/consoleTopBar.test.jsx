/** The party console's top bar: the bell counts what waits, and search opens the record. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { MEMBER, memberRoutes, renderApp, signInAsParty, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the party console top bar", () => {
  it("counts pending applications on the bell and links to them", async () => {
    const user = userEvent.setup();
    signInAsParty(["membership_officer"]);
    stubApi(memberRoutes({ "GET /party/notifications/": [{ key: "pending_members", count: 3 }] }));
    renderApp(<Root />, { path: "/party/members" });

    await user.click(await screen.findByRole("button", { name: "Notifications, 3 waiting" }));

    expect(screen.getByRole("link", { name: "3 membership applications to verify" })).toHaveAttribute(
      "href",
      "/party/members?status=pending",
    );
  });

  it("opens search with Ctrl K and links each hit to its record", async () => {
    const user = userEvent.setup();
    signInAsParty(["membership_officer"]);
    stubApi(memberRoutes({
      "GET /party/notifications/": [],
      "GET /party/search/": [{ kind: "member", id: "pm1", label: MEMBER.full_name, detail: "Pending · +254700000001" }],
    }));
    renderApp(<Root />, { path: "/party/members" });

    await screen.findAllByText(MEMBER.full_name);
    await user.keyboard("{Control>}k{/Control}");
    await user.type(screen.getByLabelText("Search the party registers"), "wa");

    const results = await screen.findByRole("list", { name: "Search results" });
    expect(within(results).getByRole("link")).toHaveAttribute("href", "/party/members?open=pm1");
  });
});
