/** The finance officer's page in the party portal. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { nairobiDate } from "../src/lib/format";
import { financeRoutes, renderApp, signInAsParty, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const sent = (calls, method, path) => calls.find((c) => c.method === method && c.path === path);

describe("the finance page", () => {
  it("shows a finance officer Finance and not the member register", async () => {
    signInAsParty(["finance_officer"]);
    stubApi(financeRoutes({ "GET /campaigns/": [] }));
    renderApp(<Root />, { path: "/party" });

    expect((await screen.findAllByRole("button", { name: "Jane for Roysambu" })).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: "Finance" })).toHaveAttribute("aria-current", "page");
    expect(screen.queryByRole("link", { name: "Members" })).toBeNull();
  });

  it("records a payment whose amount defaults to the plan's price", async () => {
    const user = userEvent.setup();
    signInAsParty(["finance_officer"]);
    const calls = stubApi(financeRoutes());
    renderApp(<Root />, { path: "/party/finance" });

    const [pay] = await screen.findAllByRole("button", { name: "Record payment for Jane for Roysambu" });
    await user.click(pay);
    expect(screen.getByLabelText("Amount received (KES)")).toHaveValue("2500");
    await user.type(screen.getByLabelText("Reference"), "QX99ZZ11");
    await user.click(screen.getByRole("button", { name: "Record payment" }));

    expect(await screen.findByText("KES 2,500 recorded for Jane for Roysambu")).toBeInTheDocument();
    expect(sent(calls, "POST", "/party/finance/subscriptions/s1/payments/").body).toEqual({
      amount_kes: 2500,
      method: "mpesa",
      reference: "QX99ZZ11",
      received_on: nairobiDate(),
      note: "",
    });
  });

  it("voids the latest live entry with the reason", async () => {
    const user = userEvent.setup();
    signInAsParty(["finance_officer"]);
    const calls = stubApi(financeRoutes());
    renderApp(<Root />, { path: "/party/finance?subscription=s1" });

    const offered = await screen.findAllByRole("button", { name: "Void" });
    expect(offered).toHaveLength(1);
    await user.click(offered[0]);
    await user.type(screen.getByLabelText("Reason"), "Recorded twice");
    await user.click(screen.getAllByRole("button", { name: "Void" }).at(-1));

    await waitFor(() =>
      expect(sent(calls, "POST", "/party/finance/subscriptions/s1/entries/en2/void/")?.body).toEqual({
        reason: "Recorded twice",
      }),
    );
  });

  it("suspends a campaign's access with the reason", async () => {
    const user = userEvent.setup();
    signInAsParty(["finance_officer"]);
    const calls = stubApi(financeRoutes());
    renderApp(<Root />, { path: "/party/finance?subscription=s1" });

    await user.click(await screen.findByRole("button", { name: "Stop access" }));
    await user.type(screen.getByLabelText("Reason"), "Cheque bounced");
    await user.click(screen.getByRole("button", { name: "Suspend" }));

    await waitFor(() =>
      expect(sent(calls, "PUT", "/party/finance/subscriptions/s1/hold/")?.body).toEqual({
        hold: "suspended",
        reason: "Cheque bounced",
      }),
    );
  });

  it("keeps the keyboard inside a dialog, closes it on Escape, and gives the focus back", async () => {
    const user = userEvent.setup();
    signInAsParty(["finance_officer"]);
    stubApi(financeRoutes());
    renderApp(<Root />, { path: "/party/finance" });

    const [pay] = await screen.findAllByRole("button", { name: "Record payment for Jane for Roysambu" });
    await user.click(pay);
    const dialog = screen.getByRole("dialog", { name: "Record payment" });
    expect(dialog).toHaveFocus();
    await user.tab({ shift: true });
    expect(dialog).toContainElement(document.activeElement);
    expect(document.activeElement).not.toBe(dialog);
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(pay).toHaveFocus();
  });
});

describe("party payouts", () => {
  it("schedules a typed-in polling agent for a campaign, in practice mode", async () => {
    const user = userEvent.setup();
    signInAsParty(["finance_officer"]);
    const calls = stubApi(financeRoutes({
      "GET /party/finance/payouts/": [],
      "GET /party/finance/payouts/spend/": { rows: [], paid_kes: 0, owed_kes: 0 },
      "GET /party/finance/payouts/campaigns/": [{ aspirant: "a1", label: "Achieng Otieno · MCA · Githurai" }],
      "GET /payments/payout-mode/": { mode: "practice", moves_money: false },
      "GET /party/places/": [],
      "POST /party/finance/payouts/": { id: "pp1" },
    }));
    renderApp(<Root />, { path: "/party/finance?tab=payouts" });

    expect(await screen.findByText(/Practice mode: releasing a payment moves no money/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Schedule payment" }));
    await user.type(screen.getByLabelText("Name"), "Wanjiru Kamau");
    await user.type(screen.getByLabelText("M-Pesa phone"), "0712 345678");
    await user.selectOptions(screen.getByLabelText("For"), "a1");
    await user.type(screen.getByLabelText("What for"), "Polling day");
    await user.type(screen.getByLabelText("Amount (KES)"), "1500");
    await user.click(screen.getByRole("button", { name: "Schedule" }));

    await waitFor(() =>
      expect(sent(calls, "POST", "/party/finance/payouts/")?.body).toEqual({
        payee_kind: "polling_agent",
        name: "Wanjiru Kamau",
        phone: "0712 345678",
        centre: null,
        aspirant: "a1",
        purpose: "Polling day",
        amount_kes: 1500,
      }),
    );
  });
});
