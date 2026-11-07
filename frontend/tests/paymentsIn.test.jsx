/** The office's list of money paid in: confirming a code a payer reported. */
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import PaymentsInTable from "../src/components/PaymentsInTable";
import { renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const ROW = {
  id: "p1", reference: "pin-1", purpose: "contribution", method: "manual", status: "to_confirm", amount_kes: 500,
  reason: "", practice: false, payer_name: "Wanjiru Kamau", payer_phone: "+254712345678", mpesa_code: "SKL7Q2M9XA",
  created_at: "2026-11-08T08:00:00Z", paid_at: null,
};

describe("the contributions list", () => {
  it("shows the codes waiting and confirms one", async () => {
    const user = userEvent.setup();
    signIn("manager");
    const calls = stubApi({
      "GET /campaigns/c1/payments-in/?status=to_confirm": [ROW],
      "POST /campaigns/c1/payments-in/p1/confirm/": { ...ROW, status: "paid" },
    });
    renderApp(<PaymentsInTable campaignId="c1" />);

    expect(await screen.findByText("SKL7Q2M9XA")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Confirm SKL7Q2M9XA" }));

    await waitFor(() => expect(calls.some((c) => c.path === "/campaigns/c1/payments-in/p1/confirm/")).toBe(true));
  });
});
