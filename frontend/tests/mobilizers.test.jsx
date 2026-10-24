import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { CAMPAIGN, TARGETS, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const MOBILIZERS = [
  { id: "m1", full_name: "Juma Otieno", ward: "w1", ward_name: "Zimmerman", registration_centre: null, phone: "" },
  { id: "m2", full_name: "Akinyi Wekesa", ward: null, ward_name: null, registration_centre: null, phone: "" },
];

async function open(page, routes) {
  signIn("manager");
  const calls = stubApi(dashboardRoutes({ "GET /mobilizers/": MOBILIZERS, ...routes }));
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: page }));
  return { calls, user };
}

describe("mobilizers and wards", () => {
  it("assigns a mobilizer without a ward to the ward row that was clicked", async () => {
    const { calls, user } = await open("Wards", { "PATCH /mobilizers/m2/": MOBILIZERS[1] });

    const githurai = (await screen.findByText("Githurai")).closest("tr");
    await user.click(within(githurai).getByRole("button", { name: "Assign" }));
    const picker = screen.getByRole("combobox", { name: "Mobilizer" });
    const offered = within(picker).getAllByRole("option").map((o) => o.textContent);
    await user.click(screen.getAllByRole("button", { name: "Assign" }).at(-1));  // the modal's, drawn last

    expect(offered).toEqual(["Akinyi Wekesa"]);
    await waitFor(() =>
      expect(calls.filter((c) => c.method === "PATCH").map((c) => [c.path, c.body])).toEqual([
        ["/mobilizers/m2/", { ward: "w2", registration_centre: null }],
      ]),
    );
  });

  it("adds a mobilizer with no ward when none is picked", async () => {
    const { calls, user } = await open("Mobilizers", { "POST /mobilizers/": { id: "m3" } });

    await user.click(await screen.findByRole("button", { name: "Add mobilizer" }));
    await user.type(screen.getAllByRole("textbox")[0], "Wanjiku Njeri");
    await user.click(screen.getByRole("button", { name: "Save mobilizer" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "POST" && c.path === "/mobilizers/").body).toEqual({
        campaign: "c1",
        ward: null,
        registration_centre: null,
        full_name: "Wanjiku Njeri",
        phone: "",
      }),
    );
  });
});

describe("editing a mobilizer", () => {
  it("keeps their ward when only the name or phone changes", async () => {
    const { calls, user } = await open("Mobilizers", { "PATCH /mobilizers/m1/": MOBILIZERS[0], "GET /targets/": [] });

    await user.click((await screen.findAllByRole("button", { name: "Edit" }))[0]);
    await user.type(screen.getAllByRole("textbox")[1], "0700");
    await user.click(screen.getByRole("button", { name: "Save mobilizer" }));

    await waitFor(() =>
      expect(calls.find((c) => c.method === "PATCH").body).toEqual({
        full_name: "Juma Otieno", phone: "0700",
      }),
    );
  });
});

describe("an MCA campaign", () => {
  it("places and shows each mobilizer by registration centre, never by ward", async () => {
    const centreTarget = (id, rc, name) => ({ ...TARGETS[0], id, registration_centre: rc, centre_name: name });
    const { user } = await open("Mobilizers", {
      "GET /campaigns/": [{ ...CAMPAIGN, operational_grain: "centre", seat: "MCA seat" }],
      "GET /targets/": [centreTarget("t1", "rc1", "Zimmerman Primary"), centreTarget("t2", "rc2", "Kamae Primary")],
      "GET /mobilizers/": [
        { ...MOBILIZERS[0], registration_centre: "rc1" },
        { ...MOBILIZERS[0], id: "m3", full_name: "Otieno Ouma", registration_centre: "rc9" },
        MOBILIZERS[1],
      ],
    });

    const table = (await screen.findByText("Juma Otieno")).closest("table");
    const places = within(table).getAllByRole("row").slice(1).map((r) => within(r).getAllByRole("cell")[1].textContent);
    await user.click(screen.getByRole("button", { name: "Add mobilizer" }));
    const picker = screen.getByRole("combobox", { name: "Registration centre" });

    expect(within(table).getAllByRole("columnheader")[1].textContent).toBe("Centre");
    expect(places).toEqual(["Zimmerman Primary", "A centre with no target", "No centre yet"]);
    expect(within(picker).getAllByRole("option").map((o) => o.textContent)).toEqual(["No centre yet", "Kamae Primary"]);
  });
});
