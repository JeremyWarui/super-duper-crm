import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import Join from "../src/components/Join";
import Withdraw from "../src/components/Withdraw";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PAGE = { campaign_title: "Jane for Roysambu", candidate_name: "Jane", event_title: "Zimmerman town hall", ward_name: "Zimmerman", open: true, consent_wording: "I agree to the server wording.", place: null, places: [] };
const CAMPAIGN_PAGE = { ...PAGE, event_title: "", ward_name: "Roysambu", place: "ward", places: [{ id: "w2", name: "Githurai" }, { id: "w1", name: "Zimmerman" }] };
const DONE = { message: "Thank you, you're signed up.", withdraw_code: "private-code" };

async function fillIn(user) {
  await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
  await user.type(screen.getByRole("textbox", { name: "Phone" }), "0712 345678");
  await user.click(screen.getByRole("checkbox"));
}

describe("signing up from an event's QR code", () => {
  it("sends the name, phone and consent, and hands back a private withdrawal link", async () => {
    const calls = stubApi({ "GET /join/abc123/": PAGE, "POST /join/abc123/": DONE });
    renderApp(<Join code="abc123" />);
    const user = userEvent.setup();

    await fillIn(user);
    await user.click(screen.getByRole("button", { name: "Sign up" }));

    expect(await screen.findByText("Thank you, you're signed up.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /\/withdraw\/private-code$/ })).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ full_name: "Wanjiku Njeri", phone: "0712 345678", consent_given: true, place: null });
  });

  it("labels the consent box with the wording the server sends", async () => {
    stubApi({ "GET /join/abc123/": PAGE });
    renderApp(<Join code="abc123" />);

    expect(await screen.findByRole("checkbox", { name: "I agree to the server wording." })).toBeInTheDocument();
  });

  it("shows the manager the event's sign-up link, ready to share", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Sign-up QR" }));

    await waitFor(() => expect(screen.getByText(/\/join\/zimmerman-hall$/)).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Share on WhatsApp" }).getAttribute("href")).toContain(encodeURIComponent("/join/zimmerman-hall"));
  });

  it("copies the link, or says so when the browser will not", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    const writeText = vi.fn().mockResolvedValueOnce(undefined).mockRejectedValueOnce(new Error("denied"));
    renderApp(<App />);
    const user = userEvent.setup();
    // After setup, which installs a clipboard of its own.
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    await user.click(await screen.findByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Sign-up QR" }));
    await user.click(await screen.findByRole("button", { name: "Copy link" }));
    await screen.findByRole("button", { name: "Copied" });
    await user.click(screen.getByRole("button", { name: "Copied" }));

    expect(writeText.mock.calls[0][0]).toMatch(/\/join\/zimmerman-hall$/);
    expect(await screen.findByText(/blocked copying/)).toBeInTheDocument();
  });
});

describe("signing up on the campaign's own link", () => {
  it("asks for the ward, and will not send until one is picked", async () => {
    const calls = stubApi({ "GET /join/camp42/": CAMPAIGN_PAGE, "POST /join/camp42/": DONE });
    renderApp(<Join code="camp42" />);
    const user = userEvent.setup();

    await fillIn(user);
    const send = screen.getByRole("button", { name: "Sign up" });
    const blockedWithoutWard = send.disabled;
    await user.selectOptions(screen.getByRole("combobox", { name: "Where you vote" }), "w2");
    await user.click(send);

    expect(blockedWithoutWard).toBe(true);
    await screen.findByText("Thank you, you're signed up.");
    expect(calls.find((c) => c.method === "POST").body.place).toBe("w2");
  });

  it("lets the manager open the link and share it", async () => {
    signIn("manager");
    const link = { code: "camp42", open: false };
    const calls = stubApi(dashboardRoutes({
      "GET /campaigns/c1/signups/": link,
      "POST /campaigns/c1/signups/": { code: "camp42", open: true },
    }));
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Supporters" }));
    await user.click(await screen.findByRole("button", { name: "Sign-up link" }));
    await screen.findByText(/\/join\/camp42$/);
    const shareableWhileClosed = screen.queryByRole("link", { name: "Share on WhatsApp" });
    link.open = true;
    await user.click(screen.getByRole("button", { name: "Open sign-ups" }));

    expect(shareableWhileClosed).toBeNull();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ open: true });
    expect(await screen.findByRole("link", { name: "Share on WhatsApp" })).toBeInTheDocument();
  });
});

describe("withdrawing", () => {
  it("removes the person's details with their private link", async () => {
    const calls = stubApi({ "POST /join/withdraw/private-code/": { message: "Done. If your details were on this campaign's register, they are gone now." } });
    renderApp(<Withdraw code="private-code" />);
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Remove my details" }));

    expect(await screen.findByText(/they are gone now/)).toBeInTheDocument();
    expect(calls.map((c) => [c.method, c.path])).toEqual([["POST", "/join/withdraw/private-code/"]]);
  });
});
