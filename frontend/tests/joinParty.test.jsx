import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import JoinParty from "../src/pages/public/JoinParty";
import { fakeSecret, renderApp, stubApi } from "./helpers";

const PASSWORD = fakeSecret();

afterEach(() => {
  vi.unstubAllGlobals();
});

const PARTY = { name: "Umoja Party", logo_url: "", primary_colour: "#112233", secondary_colour: "#445566", description: "One country.", consent_wording: "Umoja may keep my details.", volunteer_consent_wording: "Umoja may contact me about volunteering." };
const ROUTES = {
  "GET /site/": PARTY,
  "GET /party/": { consent_wording: PARTY.consent_wording, sms_consent_wording: "Send me party updates by SMS." },
  "GET /party/places/": [{ id: "c1", name: "Nairobi" }],
  "GET /party/places/?county=c1": [{ id: "k1", name: "Roysambu" }],
  "GET /party/places/?constituency=k1": [{ id: "w1", name: "Githurai" }],
  "GET /party/places/?ward=w1": [{ id: "rc1", name: "Githurai Primary" }],
  "POST /party/join/": { withdraw_url: "/party/withdraw/private-code" },
};

async function fillDetails(user) {
  await user.type(await screen.findByRole("textbox", { name: "First name" }), "Wanjiku");
  await user.type(screen.getByRole("textbox", { name: "Surname" }), "Njeri");
  await user.type(screen.getByRole("textbox", { name: "Phone" }), "0712 345678");
  await user.type(screen.getByRole("textbox", { name: "Email" }), "wanjiku@example.com");
  await user.type(screen.getByLabelText("Password"), PASSWORD);
  await user.click(screen.getByRole("button", { name: "Continue" }));
}

async function fillBranch(user) {
  await screen.findByRole("option", { name: "Nairobi" });
  await user.selectOptions(screen.getByRole("combobox", { name: "County" }), "c1");
  await screen.findByRole("option", { name: "Roysambu" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Constituency" }), "k1");
  await screen.findByRole("option", { name: "Githurai" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Ward" }), "w1");
  await screen.findByRole("option", { name: "Githurai Primary" });
  await user.selectOptions(screen.getByRole("combobox", { name: "Polling station" }), "rc1");
}

describe("applying to join the party", () => {
  it("needs a polling station in the chosen ward before it moves on", async () => {
    stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();
    await fillDetails(user);
    await screen.findByRole("option", { name: "Nairobi" });
    await user.selectOptions(screen.getByRole("combobox", { name: "County" }), "c1");
    await screen.findByRole("option", { name: "Roysambu" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Constituency" }), "k1");
    await screen.findByRole("option", { name: "Githurai" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Ward" }), "w1");
    const offWithoutStation = screen.getByRole("button", { name: "Continue" }).disabled;

    await screen.findByRole("option", { name: "Githurai Primary" });
    await user.selectOptions(screen.getByRole("combobox", { name: "Polling station" }), "rc1");

    expect(offWithoutStation).toBe(true);
    expect(screen.getByRole("button", { name: "Continue" }).disabled).toBe(false);
  });

  it("asks the volunteer's fields only with the tick, and sends them", async () => {
    const calls = stubApi({ ...ROUTES, "POST /party/join/": { withdraw_url: "/party/withdraw/a", volunteer_withdraw_url: "/party/volunteer/withdraw/b" } });
    renderApp(<JoinParty />);
    const user = userEvent.setup();
    await fillDetails(user);
    await fillBranch(user);
    const askedWithoutTick = screen.queryByRole("combobox", { name: "Profession" });

    await user.click(screen.getByRole("checkbox", { name: "Volunteer for events" }));
    const offWithoutVolunteerDetails = screen.getByRole("button", { name: "Continue" }).disabled;
    await user.selectOptions(screen.getByRole("combobox", { name: "Profession" }), "other");
    await user.type(screen.getByRole("textbox", { name: "Your profession" }), "Boda rider");
    await user.click(screen.getByRole("checkbox", { name: "Holding Barazas & Household Meetings" }));
    await user.click(screen.getByRole("checkbox", { name: "Other" }));
    const offWithoutOtherText = screen.getByRole("button", { name: "Continue" }).disabled;
    await user.type(screen.getByRole("textbox", { name: "Other ways to help" }), "Music");
    await user.selectOptions(screen.getByRole("combobox", { name: "Preferred contact" }), "sms");
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));
    const offWithoutVolunteerConsent = screen.getByRole("button", { name: "Join the party" }).disabled;
    await user.click(screen.getByRole("checkbox", { name: PARTY.volunteer_consent_wording }));
    await user.click(screen.getByRole("button", { name: "Join the party" }));

    expect(askedWithoutTick).toBeNull();
    expect([offWithoutVolunteerDetails, offWithoutOtherText, offWithoutVolunteerConsent]).toEqual([true, true, true]);
    expect(calls.find((c) => c.method === "POST").body.volunteer).toEqual({
      profession: "other",
      profession_other: "Boda rider",
      areas: ["barazas", "other"],
      area_other: "Music",
      preferred_contact: "sms",
      consent_given: true,
    });
    const stop = `${window.location.origin}/party/volunteer/withdraw/b`;
    expect(await screen.findByRole("link", { name: stop })).toHaveAttribute("href", stop);
  });

  it("thanks the applicant, sends the details and shows the withdrawal link in full", async () => {
    const calls = stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();
    await fillDetails(user);
    await fillBranch(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));
    const offWithoutConsent = screen.getByRole("button", { name: "Join the party" }).disabled;

    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));
    await user.click(screen.getByRole("button", { name: "Join the party" }));

    expect(offWithoutConsent).toBe(true);
    expect(await screen.findByText(/pending review/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: `${window.location.origin}/party/withdraw/private-code` })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({
      first_name: "Wanjiku",
      surname: "Njeri",
      phone: "0712 345678",
      email: "wanjiku@example.com",
      password: PASSWORD,
      ward: "w1",
      registration_centre: "rc1",
      consent_given: true,
      sms_updates: false,
    });
  });

  it("sends the SMS updates choice only when the optional box is ticked", async () => {
    const calls = stubApi(ROUTES);
    renderApp(<JoinParty />);
    const user = userEvent.setup();
    await fillDetails(user);
    await fillBranch(user);
    await user.click(screen.getByRole("button", { name: "Continue" }));

    await user.click(screen.getByRole("checkbox", { name: PARTY.consent_wording }));
    await user.click(screen.getByRole("checkbox", { name: /Send me party updates by SMS/ }));
    await user.click(screen.getByRole("button", { name: "Join the party" }));

    await screen.findByText(/pending review/);
    expect(calls.find((c) => c.method === "POST").body.sms_updates).toBe(true);
  });
});
