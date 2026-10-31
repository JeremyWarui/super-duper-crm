import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import JoinParty from "../src/pages/public/JoinParty";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PARTY = { name: "Umoja Party", logo_url: "", primary_colour: "#112233", secondary_colour: "#445566", description: "One country.", consent_wording: "Umoja may keep my details." };
const ROUTES = {
  "GET /party/": PARTY,
  "GET /party/places/": [{ id: "c1", name: "Nairobi" }],
  "GET /party/places/?county=c1": [{ id: "k1", name: "Roysambu" }],
  "GET /party/places/?constituency=k1": [{ id: "w1", name: "Githurai" }],
  "POST /party/join/": { withdraw_url: "/party/withdraw/private-code" },
};

async function fillIn(user) {
  await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
  await user.type(screen.getByRole("textbox", { name: "Phone" }), "0712 345678");
  await screen.findByRole("option", { name: "Nairobi" });
  await user.selectOptions(screen.getByRole("combobox", { name: "County" }), "c1");
  await screen.findByRole("option", { name: "Roysambu" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Constituency" }), "k1");
  await screen.findByRole("option", { name: "Githurai" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Ward" }), "w1");
}

describe("applying to join the party", () => {
  it("keeps the submit button off until consent is ticked", async () => {
    stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();

    await fillIn(user);
    const send = screen.getByRole("button", { name: "Join the party" });
    const offWithoutConsent = send.disabled;
    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));

    expect(offWithoutConsent).toBe(true);
    expect(send.disabled).toBe(false);
  });

  it("thanks the applicant and shows the withdrawal link in full", async () => {
    const calls = stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();

    await fillIn(user);
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Join the party" }));

    expect(await screen.findByText(/pending review/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: `${window.location.origin}/party/withdraw/private-code` })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ full_name: "Wanjiku Njeri", phone: "0712 345678", email: null, ward: "w1", consent_given: true });
  });
});
