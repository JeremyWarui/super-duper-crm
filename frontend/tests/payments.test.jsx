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
  await user.click(await screen.findByRole("link", { name: "Payments" }));
  await screen.findByText("Juma Otieno");
  return { calls, user };
}

const posted = (calls, path) => calls.find((c) => c.method === "POST" && c.path === path)?.body;

describe("payments", () => {
  it("schedules a payment for work marked done, and only work not yet paid", async () => {
    const work = (id, label) => ({ id, kind: "event", label, member_name: "Juma Otieno", member_role: "mobilizer", ward_name: "Zimmerman", centre_name: null, amount_kes: 1500, status: "done" });
    const { calls, user } = await openPayments("manager", {
      "GET /payments/": [{ ...SCHEDULED, assignment: "a0" }],
      "GET /assignments/?campaign=c1&status=done": [work("a0", "Already paid"), work("a1", "Githurai rally")],
      "POST /payments/": SCHEDULED,
    });

    await user.click(screen.getByRole("button", { name: "Schedule payment" }));
    const picker = screen.getByRole("combobox", { name: "Work done" });
    await screen.findByRole("option", { name: /Githurai rally/ });
    expect(within(picker).queryByRole("option", { name: /Already paid/ })).toBeNull();
    await user.selectOptions(picker, "a1");
    await user.click(screen.getByRole("button", { name: "Schedule" }));

    await waitFor(() => expect(posted(calls, "/payments/")).toEqual({ assignment: "a1" }));
  });

  it("lets the candidate approve a payment the manager scheduled, and not the manager", async () => {
    const byManager = { ...SCHEDULED, scheduled_by: "u-manager", approver_role: "candidate" };
    await openPayments("candidate", { "GET /payments/": [byManager] });
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Awaiting my approval" }));
    const row = screen.getByText("Juma Otieno").closest("tr");
    expect(within(row).getByRole("button", { name: "Approve" })).toBeInTheDocument();
  });

  it("shows the manager their own scheduled payment as awaiting the candidate", async () => {
    await openPayments("manager", { "GET /payments/": [{ ...SCHEDULED, scheduled_by: "u1", approver_role: "candidate" }] });

    const row = screen.getByText("Juma Otieno").closest("tr");
    expect(within(row).queryByRole("button", { name: "Approve" })).toBeNull();
    expect(within(row).getByText("Awaiting the candidate")).toBeInTheDocument();
  });

  it("declines a payment only with a reason", async () => {
    const { calls, user } = await openPayments("manager", { "POST /payments/p1/decline/": { ...SCHEDULED, status: "cancelled" } });

    await user.click(screen.getByRole("button", { name: "Decline" }));
    const confirm = screen.getByRole("button", { name: "Decline payment" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Reason" }), "Not done properly");
    await user.click(confirm);

    await waitFor(() => expect(posted(calls, "/payments/p1/decline/")).toEqual({ reason: "Not done properly" }));
  });

  it("marks a scheduled payment paid under its reference", async () => {
    const { calls, user } = await openPayments("manager", { "POST /payments/p1/paid/": { ...SCHEDULED, status: "paid" } });

    await user.click(screen.getByRole("button", { name: "Mark paid" }));
    await user.type(screen.getByRole("textbox", { name: "Reference" }), "QX12AB34");
    await user.click(screen.getAllByRole("button", { name: "Mark paid" }).at(-1));  // the modal's, drawn last

    await waitFor(() => expect(posted(calls, "/payments/p1/paid/")).toEqual({ reference: "QX12AB34" }));
  });

  it("releases a payment after showing that practice mode moves no money", async () => {
    const { calls, user } = await openPayments("manager", {
      "GET /payments/payout-mode/": { mode: "practice", moves_money: false },
      "POST /payments/p1/release/": { ...SCHEDULED, status: "paid", reference: "PRACTICE-0A1B2C3D4E" },
    });

    await user.click(screen.getByRole("button", { name: "Approve" }));
    expect(await screen.findByText(/Practice mode: no money moves/)).toBeInTheDocument();
    await user.click(screen.getAllByRole("button", { name: "Release" }).at(-1));  // the modal's, drawn last

    expect(await screen.findByText("Paid · PRACTICE-0A1B2C3D4E")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST").map((c) => c.path)).toEqual(["/payments/p1/release/"]);
  });

  it("shows the candidate the register without any way to change it", async () => {
    await openPayments("candidate");

    const row = screen.getByText("Juma Otieno").closest("tr");
    expect(within(row).getByText("KES 1,500")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Schedule payment" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mark paid" })).toBeNull();
  });

  it("lets a coordinator schedule a payment but leaves releasing to the manager", async () => {
    await openPayments("coordinator");

    expect(screen.getByRole("button", { name: "Schedule payment" })).toBeInTheDocument();
    for (const name of ["Approve", "Approve all awaiting me", "Mark paid", "Decline"]) {
      expect(screen.queryByRole("button", { name })).toBeNull();
    }
  });

  it("shows the practice-mode banner when releases move no money", async () => {
    await openPayments("manager", { "GET /payments/payout-mode/": { mode: "practice", moves_money: false } });

    expect(await screen.findByText("Practice mode.")).toBeInTheDocument();
  });

  it("shows no banner once releases move real money", async () => {
    const { calls } = await openPayments("manager", { "GET /payments/payout-mode/": { mode: "live", moves_money: true } });

    await waitFor(() => expect(calls.some((c) => c.path === "/payments/payout-mode/")).toBe(true));
    await new Promise((r) => setTimeout(r, 50));
    expect(screen.queryByText("Practice mode.")).toBeNull();
  });

  it("counts failed payments and ones stuck while sending as needing attention", async () => {
    await openPayments("manager", { "GET /payments/": [
      SCHEDULED,
      { ...SCHEDULED, id: "p2", recipient_name: "Akinyi Wekesa", status: "failed", failure_reason: "Wrong number." },
      { ...SCHEDULED, id: "p3", recipient_name: "Otieno Ouma", status: "sending", stuck: true },
      { ...SCHEDULED, id: "p4", recipient_name: "Wanjiku Njeri", status: "sending", stuck: false },
    ] });

    const tile = within(screen.getByRole("region", { name: "Summary" })).getByText("Needs attention").parentElement;
    expect(within(tile).getByText("2")).toBeInTheDocument();
  });

});

describe("assignments", () => {
  const ASSIGNED = { id: "a1", kind: "activity", label: "Agent training", member_name: "Juma Otieno", member_role: "mobilizer", ward_name: "Zimmerman", centre_name: null, amount_kes: 800, status: "assigned" };

  it("marks assigned work done", async () => {
    signIn("manager");
    const calls = stubApi(dashboardRoutes({
      "GET /assignments/?campaign=c1&status=assigned": [ASSIGNED],
      "POST /assignments/a1/done/": { ...ASSIGNED, status: "done" },
    }));
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("link", { name: "Assignments" }));
    await user.click(await screen.findByRole("button", { name: "Mark Agent training done" }));

    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/assignments/a1/done/")).toBe(true));
  });

  it("assigns an event to a mobilizer from its card", async () => {
    signIn("manager");
    const calls = stubApi(dashboardRoutes({ "GET /mobilizers/": MOBILIZERS, "GET /agents/?campaign=c1": [], "POST /assignments/": { id: "a2" } }));
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("link", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Assign Zimmerman town hall" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Who" }), "mobilizer:m1");
    await user.type(screen.getByRole("spinbutton", { name: "Amount" }), "1200");
    await user.click(screen.getByRole("button", { name: "Assign" }));

    await waitFor(() => expect(posted(calls, "/assignments/")).toEqual({
      campaign: "c1", mobilizer: "m1", kind: "event", event: "e1", ward: null, description: "", amount_kes: 1200,
    }));
  });
});
