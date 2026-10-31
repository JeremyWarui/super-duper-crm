/** The party portal's volunteers page. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { renderApp, signInAsParty, stubApi, volunteerRoutes } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("the volunteers page", () => {
  it("lets a membership officer filter by interest and activate a volunteer", async () => {
    const user = userEvent.setup();
    signInAsParty(["membership_officer"]);
    const calls = stubApi(volunteerRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party/volunteers" });

    await user.selectOptions(await screen.findByRole("combobox", { name: "Interest" }), "events");
    await waitFor(() =>
      expect(calls.some((c) => c.path.startsWith("/party/volunteers/?") && c.path.includes("interest=events"))).toBe(true),
    );
    await user.click(await screen.findByRole("button", { name: "Achieng Otieno" }));
    await user.click(await screen.findByRole("button", { name: "Activate" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")).toMatchObject({
        path: "/party/volunteers/vp1/",
        body: { status: "active" },
      }),
    );
  });
});
