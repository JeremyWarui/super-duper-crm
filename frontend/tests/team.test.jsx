import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { CAMPAIGN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

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
  await user.click(await screen.findByRole("link", { name: "Team" }));
  await screen.findByText("Amina Kariuki");
  return { calls, user };
}

describe("the team page", () => {
  it("lets the aspirant replace the manager, who is emailed an invite", async () => {
    const { calls, user } = await openTeam("candidate", {
      "POST /campaigns/c1/team/manager/": { id: "u4", username: "wanjiru", full_name: "Wanjiru Kamau", invite: "email", replaced: "amina" },
    });

    await user.click(screen.getByRole("button", { name: "Replace manager" }));
    await user.type(screen.getByRole("textbox", { name: "Full name" }), "Wanjiru Kamau");
    await user.type(screen.getByRole("textbox", { name: "Username" }), "Wanjiru");
    await user.type(screen.getByRole("textbox", { name: "Email" }), "wanjiru@example.com");
    await user.click(screen.getAllByRole("button", { name: "Replace manager" }).at(-1));

    expect(await screen.findByText("We emailed wanjiru a link to choose their password.")).toBeTruthy();
    expect(screen.getByText(/amina is off the campaign/)).toBeTruthy();
    expect(calls.find((c) => c.method === "POST").body).toEqual({
      username: "wanjiru", first_name: "Wanjiru", last_name: "Kamau", phone: "", email: "wanjiru@example.com", replace: true,
    });
  });

  it("offers the aspirant Add manager when there is none, and adds without replacing", async () => {
    const { calls, user } = await openTeam("candidate", {
      "GET /campaigns/c1/team/": [TEAM[0], TEAM[2], { ...TEAM[1], role: "mobilizer", username: "amina2" }],
      "POST /campaigns/c1/team/manager/": { id: "u4", username: "wanjiru", full_name: "Wanjiru Kamau", invite: "email", replaced: null },
    });

    await user.click(screen.getByRole("button", { name: "Add manager" }));
    await user.type(screen.getByRole("textbox", { name: "Full name" }), "Wanjiru");
    await user.type(screen.getByRole("textbox", { name: "Username" }), "wanjiru");
    await user.type(screen.getByRole("textbox", { name: "Email" }), "wanjiru@example.com");
    await user.click(screen.getAllByRole("button", { name: "Add manager" }).at(-1));

    await screen.findByText("Manager added");
    expect(screen.queryByText(/is off the campaign/)).toBeNull();
    expect(calls.find((c) => c.method === "POST").body.replace).toBe(false);
  });

  it.each(["candidate", "manager"])("offers the %s no password reset", async (role) => {
    await openTeam(role);

    expect(screen.queryByRole("button", { name: "Reset password" })).toBeNull();
    expect(screen.queryAllByRole("button", { name: /(add|replace) manager/i }).length).toBe(role === "candidate" ? 1 : 0);
  });

  it("adds a coordinator, then gives them wards from the campaign's targets", async () => {
    const coordinator = { id: "u5", username: "otieno", full_name: "Otieno Ouma", role: "coordinator", phone: "", is_active: true };
    const { calls, user } = await openTeam("manager", {
      "GET /campaigns/c1/team/": [...TEAM, coordinator],
      "POST /campaigns/c1/team/": { id: "u5", username: "otieno", full_name: "Otieno Ouma", invite: "email", role: "coordinator" },
      "GET /campaigns/c1/team/u5/area/": { wards: ["w1"], registration_centres: [] },
      "PUT /campaigns/c1/team/u5/area/": { wards: ["w1", "w2"], registration_centres: [] },
    });

    await user.click(screen.getByRole("button", { name: "Add coordinator" }));
    await user.type(screen.getByRole("textbox", { name: "Full name" }), "Otieno Ouma");
    await user.type(screen.getByRole("textbox", { name: "Username" }), "otieno");
    await user.type(screen.getByRole("textbox", { name: "Email" }), "otieno@example.com");
    await user.click(screen.getAllByRole("button", { name: "Add coordinator" }).at(-1));
    await user.click(await screen.findByRole("button", { name: "Done" }));
    expect(calls.find((c) => c.method === "POST").body).toEqual({
      role: "coordinator", username: "otieno", first_name: "Otieno", last_name: "Ouma", phone: "", email: "otieno@example.com",
    });

    await user.click(screen.getByRole("button", { name: "Area for Otieno Ouma" }));
    expect(await screen.findByRole("checkbox", { name: "Zimmerman" })).toBeChecked();
    await user.click(screen.getByRole("checkbox", { name: "Githurai" }));
    await user.click(screen.getByRole("button", { name: "Save 2 wards" }));

    await waitFor(() => expect(calls.find((c) => c.method === "PUT").body).toEqual({ wards: ["w1", "w2"], registration_centres: [] }));
  });

  it("offers centres, not wards, in an MCA race", async () => {
    const coordinator = { id: "u5", username: "otieno", full_name: "Otieno Ouma", role: "coordinator", phone: "", is_active: true };
    const { user } = await openTeam("manager", {
      "GET /campaigns/": [{ ...CAMPAIGN, operational_grain: "centre", ward: "w1" }],
      "GET /targets/": [{ id: "t1", ward: "w1", ward_name: "Zimmerman", registration_centre: "rc1", centre_name: "Zimmerman Primary" }],
      "GET /campaigns/c1/team/": [...TEAM, coordinator],
      "GET /campaigns/c1/team/u5/area/": { wards: [], registration_centres: [] },
    });

    await user.click(screen.getByRole("button", { name: "Area for Otieno Ouma" }));

    expect(await screen.findByRole("checkbox", { name: "Zimmerman Primary" })).not.toBeChecked();
    expect(screen.getByRole("button", { name: "Save 0 centres" })).toBeInTheDocument();
  });
});
