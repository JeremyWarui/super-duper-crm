/** Giving on the website by M-Pesa: a Paybill payment reported by its code. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { PARTY, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("contributing by M-Pesa", () => {
  it("opens with the chip-in amount, shows the Paybill and sends the payer's code", async () => {
    const user = userEvent.setup();
    const calls = stubApi({
      "GET /site/": { ...PARTY, payment_instructions: "" },
      "GET /party/posts/": [],
      "GET /pay/options/": { prompt: true, practice: false, paybill: "123456", account: "DONATE", till: "", instructions: "" },
      "POST /pay/contribution/": { status: 201, body: { reference: "pin-2", status: "to_confirm", amount_kes: 500 } },
      "GET /pay/pin-2/": { reference: "pin-2", status: "to_confirm", amount_kes: 500, reason: "", practice: false },
    });
    renderApp(<AppRoutes />, { path: "/contribute?amount=500" });

    expect(await screen.findByRole("button", { name: "KES 500", pressed: true })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "I paid by Paybill" }));
    expect(screen.getByText("123456")).toBeInTheDocument();
    expect(screen.getByText("DONATE")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: "Your name" }), "Wanjiru Kamau");
    await user.type(screen.getByRole("textbox", { name: "M-Pesa phone number" }), "0712345678");
    await user.type(screen.getByRole("textbox", { name: "M-Pesa code" }), "skl7q2m9xa");
    await user.click(screen.getByRole("button", { name: "Send my code" }));

    expect(await screen.findByText("Thank you, we have your code")).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/pay/contribution/").body).toEqual({
      method: "manual", phone: "0712345678", mpesa_code: "SKL7Q2M9XA", amount_kes: 500, name: "Wanjiru Kamau", email: "",
    });
  });
});
