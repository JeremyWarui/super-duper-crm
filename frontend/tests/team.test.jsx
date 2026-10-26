import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { dashboardRoutes, fakeSecret, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const TEAM = [
  { id: "u1", username: "jane", full_name: "Jane Wambui", role: "candidate", phone: "", is_active: true },
  { id: "u2", username: "amina", full_name: "Amina Kariuki", role: "manager", phone: "", is_active: true },
  { id: "u3", username: "juma", full_name: "Juma Otieno", role: "mobilizer", phone: "", is_active: true },
];

async function openTeam(role, routes = {}) {
  signIn(role);
  const calls = stubApi(dashboardRoutes({ "GET /campaigns/c1/team/": TEAM, ...routes }));
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Team" }));
  await screen.findByText("Amina Kariuki");
  return { calls, user };
}

describe("the team page", () => {
  it("lets the aspirant replace the manager and keeps the new password on screen", async () => {
    const password = fakeSecret();
    const { calls, user } = await openTeam("candidate", {
      "POST /campaigns/c1/team/manager/": { id: "u4", username: "wanjiru", full_name: "Wanjiru Kamau", password, replaced: "amina" },
    });

    await user.click(screen.getByRole("button", { name: "Replace manager" }));
    await user.type(screen.getByRole("textbox", { name: "Full name" }), "Wanjiru Kamau");
    await user.type(screen.getByRole("textbox", { name: "Username" }), "Wanjiru");
    await user.click(screen.getAllByRole("button", { name: "Replace manager" }).at(-1));

    expect(await screen.findByText(password)).toBeTruthy();
    expect(screen.getByText(/amina is off the campaign/)).toBeTruthy();
    expect(calls.find((c) => c.method === "POST").body).toEqual({
      username: "wanjiru", first_name: "Wanjiru", last_name: "Kamau", phone: "", replace: true,
    });
  });

  it("offers the aspirant Add manager when there is none, and adds without replacing", async () => {
    const { calls, user } = await openTeam("candidate", {
      "GET /campaigns/c1/team/": [TEAM[0], TEAM[2], { ...TEAM[1], role: "mobilizer", username: "amina2" }],
      "POST /campaigns/c1/team/manager/": { id: "u4", username: "wanjiru", full_name: "Wanjiru Kamau", password: fakeSecret(), replaced: null },
    });

    await user.click(screen.getByRole("button", { name: "Add manager" }));
    await user.type(screen.getByRole("textbox", { name: "Full name" }), "Wanjiru");
    await user.type(screen.getByRole("textbox", { name: "Username" }), "wanjiru");
    await user.click(screen.getAllByRole("button", { name: "Add manager" }).at(-1));

    await screen.findByText("Manager added");
    expect(screen.queryByText(/is off the campaign/)).toBeNull();
    expect(calls.find((c) => c.method === "POST").body.replace).toBe(false);
  });

  it("lets the manager reset only the mobilizers' passwords, and set no manager", async () => {
    await openTeam("manager", {
      "GET /campaigns/c1/team/": [...TEAM, { id: "u5", username: "idle", full_name: "Idle Mobilizer", role: "mobilizer", phone: "", is_active: false }],
    });

    const resettable = screen
      .getAllByRole("button", { name: "Reset password" })
      .map((b) => within(b.closest("tr")).getAllByRole("cell")[1].textContent);

    expect(resettable).toEqual(["juma"]);
    expect(screen.queryByRole("button", { name: /manager/i })).toBeNull();
  });
});

describe("resetting a password", () => {
  it("shows the new password once the aspirant confirms", async () => {
    const password = fakeSecret();
    const { calls, user } = await openTeam("candidate", {
      "POST /campaigns/c1/team/u2/reset-password/": { username: "amina", password },
    });

    const row = screen.getByText("Amina Kariuki").closest("tr");
    await user.click(within(row).getByRole("button", { name: "Reset password" }));
    await user.click(screen.getAllByRole("button", { name: "Reset password" }).at(-1));

    expect(await screen.findByText(password)).toBeTruthy();
    await user.click(screen.getByText(password).closest(".modal-backdrop"));
    expect(screen.getByText(password)).toBeTruthy();
    await waitFor(() => expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual([
      "/campaigns/c1/team/u2/reset-password/",
    ]));
  });
});
