import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import JoinParty from "../src/pages/public/JoinParty";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PARTY = { name: "Umoja Party", logo_url: "", primary_colour: "#112233", secondary_colour: "#445566", description: "One country.", consent_wording: "Umoja may keep my details.", volunteer_consent_wording: "Umoja may contact me about volunteering." };
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

  it("requires the volunteer consent only when the volunteer section is ticked", async () => {
    const calls = stubApi({ ...ROUTES, "POST /party/join/": { withdraw_url: "/party/withdraw/a", volunteer_withdraw_url: "/party/volunteer/withdraw/b" } });
    renderApp(<JoinParty />);
    const user = userEvent.setup();
    await fillIn(user);
    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));
    const send = screen.getByRole("button", { name: "Join the party" });
    const offered = send.disabled;

    await user.click(screen.getByRole("checkbox", { name: "I would like to volunteer for the party" }));
    const offWithoutVolunteerDetails = send.disabled;
    await user.click(screen.getByRole("checkbox", { name: "Events" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Preferred contact" }), "sms");
    const offWithoutVolunteerConsent = send.disabled;
    await user.click(screen.getByRole("checkbox", { name: PARTY.volunteer_consent_wording }));
    await user.click(send);

    expect(offered).toBe(false);
    expect(offWithoutVolunteerDetails).toBe(true);
    expect(offWithoutVolunteerConsent).toBe(true);
    expect(calls.find((c) => c.method === "POST").body.volunteer).toEqual({ interests: ["events"], preferred_contact: "sms", consent_given: true });
    const stop = `${window.location.origin}/party/volunteer/withdraw/b`;
    expect(await screen.findByRole("link", { name: stop })).toHaveAttribute("href", stop);
  });

  it("thanks the applicant and shows the withdrawal link in full", async () => {
    const calls = stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();

    await fillIn(user);
    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));
    await user.click(screen.getByRole("button", { name: "Join the party" }));

    expect(await screen.findByText(/pending review/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: `${window.location.origin}/party/withdraw/private-code` })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ full_name: "Wanjiku Njeri", phone: "0712 345678", email: null, ward: "w1", consent_given: true });
  });
});
