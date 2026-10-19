import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { TARGETS, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

async function openTargets(routes) {
  signIn("manager");
  const calls = stubApi(dashboardRoutes(routes));
  renderApp(<App />);
  await screen.findByRole("button", { name: "Overview" });
  await userEvent.setup().click(screen.getByRole("button", { name: "Targets" }));
  await screen.findByText("Targets — the win number");
  return calls;
}

const zimmerman = () => screen.getByRole("slider", { name: "Turnout for Zimmerman" });
const row = () => zimmerman().closest("tr");

describe("the turnout slider", () => {
  it("saves only the last number when let go, and says it saved", async () => {
    const saved = { ...TARGETS[0], projected_turnout_pct: "70.00", votes_needed: 10746 };
    const calls = await openTargets({ "PATCH /targets/t1/": saved });

    fireEvent.input(zimmerman(), { target: { value: "65" } });
    fireEvent.input(zimmerman(), { target: { value: "70" } });
    fireEvent.change(zimmerman(), { target: { value: "70" } });

    expect(await within(row()).findByText("Saved")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "PATCH").map((c) => c.body)).toEqual([
      { projected_turnout_pct: 70 },
    ]);
  });

  it("puts the original number back when the save fails", async () => {
    await openTargets({ "PATCH /targets/t1/": { status: 500, body: { detail: "Down." } } });

    fireEvent.input(zimmerman(), { target: { value: "70" } });
    fireEvent.change(zimmerman(), { target: { value: "70" } });

    expect(await within(row()).findByText("Not saved, try again")).toBeInTheDocument();
    await waitFor(() => expect(zimmerman()).toHaveValue("60"));
  });
});
