import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const SCHEDULED = {
  id: "p1", campaign: "c1", event: "e1", event_title: "Zimmerman town hall", mobilizer: "m1",
  recipient_name: "Juma Otieno", recipient_phone: "+254700000001", amount_kes: 1500,
  status: "scheduled", reference: "", paid_at: null, created_at: "2026-10-20T09:00:00Z",
};
const MOBILIZERS = [{ id: "m1", full_name: "Juma Otieno", ward: "w1", ward_name: "Zimmerman", registration_centre: null, phone: "" }];

async function openPayments(role, routes = {}) {
  signIn(role);
  const calls = stubApi(dashboardRoutes({ "GET /payments/": [SCHEDULED], "GET /mobilizers/": MOBILIZERS, ...routes }));
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("button", { name: "Payments" }));
  await screen.findByText("Juma Otieno");
  return { calls, user };
}

const posted = (calls, path) => calls.find((c) => c.method === "POST" && c.path === path)?.body;

describe("payments", () => {
  it("schedules a payment for an event, to the mobilizer who ran it", async () => {
    const { calls, user } = await openPayments("manager", { "POST /payments/": SCHEDULED });

    await user.click(screen.getByRole("button", { name: "Schedule payment" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Event" }), "e1");
    await user.type(screen.getByRole("spinbutton", { name: "Amount" }), "1500");
    await user.click(screen.getByRole("button", { name: "Schedule" }));

    await waitFor(() =>
      expect(posted(calls, "/payments/")).toEqual({ campaign: "c1", event: "e1", mobilizer: "m1", amount_kes: 1500 }),
    );
  });

  it("marks a scheduled payment paid under its reference", async () => {
    const { calls, user } = await openPayments("manager", { "POST /payments/p1/paid/": { ...SCHEDULED, status: "paid" } });

    await user.click(screen.getByRole("button", { name: "Mark paid" }));
    await user.type(screen.getByRole("textbox", { name: "Reference" }), "QX12AB34");
    await user.click(screen.getAllByRole("button", { name: "Mark paid" }).at(-1));  // the modal's, drawn last

    await waitFor(() => expect(posted(calls, "/payments/p1/paid/")).toEqual({ reference: "QX12AB34" }));
  });

  it("shows the candidate the register without any way to change it", async () => {
    await openPayments("candidate");

    const row = screen.getByText("Juma Otieno").closest("tr");
    expect(within(row).getByText("KES 1,500")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Schedule payment" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark paid" })).toBeNull();
  });
});
