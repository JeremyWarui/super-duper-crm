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
  it("lets a membership officer filter by area, see the polling station and activate a volunteer", async () => {
    const user = userEvent.setup();
    signInAsParty(["membership_officer"]);
    const calls = stubApi(volunteerRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party/volunteers" });

    await user.selectOptions(await screen.findByRole("combobox", { name: "Area" }), "barazas");
    await waitFor(() =>
      expect(calls.some((c) => c.path.startsWith("/party/volunteers/?") && c.path.includes("area=barazas"))).toBe(true),
    );
    await user.click(await screen.findByRole("button", { name: "Achieng Otieno" }));
    expect(await screen.findByText("Polling station: Githurai Primary")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Activate" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH")).toMatchObject({
        path: "/party/volunteers/vp1/",
        body: { status: "active" },
      }),
    );
  });
});
