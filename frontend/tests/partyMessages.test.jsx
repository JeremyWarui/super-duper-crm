/** The party office's texts: the Comms Officer drafts, the Party Super Admin approves others' drafts. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { PARTY, TEST_TOKEN, renderApp, signInAsParty, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const DRAFT = {
  id: "pm1", body: "Branch meeting on Saturday.", audience: "members", place: "Everywhere", status: "draft",
  drafted_by: "Mary Officer", decided_by: "", created_at: "2026-11-06T08:00:00Z", decided_at: null, note: "",
  targeted: 40, recipients: 0, delivery: {}, mine: false,
};

const routes = (overrides = {}) => ({
  "GET /site/": PARTY,
  "GET /party/places/": [{ id: "c1", name: "Nairobi" }],
  "POST /party/messages/preview/": { recipients: 40, opted_out: 2 },
  ...overrides,
});

describe("party messages", () => {
  it("lets the Comms Officer send a draft for approval and offers no way to send it", async () => {
    const user = userEvent.setup();
    signInAsParty(["comms_officer"]);
    const calls = stubApi(routes({
      "GET /party/messages/": { can_send: false, messages: [{ ...DRAFT, mine: true }] },
      "POST /party/messages/": { status: 201, body: { ...DRAFT, id: "pm2", mine: true } },
    }));
    renderApp(<Root />, { path: "/party/messages" });

    expect(await screen.findByText(/40 recipients/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Volunteers" }));
    await user.type(screen.getByRole("textbox", { name: /Message/ }), "Volunteer training on Sunday.");
    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await vi.waitFor(() => expect(calls.find((c) => c.path === "/party/messages/" && c.method === "POST")?.body).toEqual({
      audience: "volunteers", county: null, ward: null, body: "Volunteer training on Sunday.",
    }));
    expect(screen.queryByRole("button", { name: "Approve and send" })).toBeNull();
  });

  it("gives the Super Admin Approve on someone else's draft but not on their own", async () => {
    const user = userEvent.setup();
    useAuth.setState({
      token: TEST_TOKEN,
      user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true, party_roles: [] },
    });
    const calls = stubApi(routes({
      "GET /party/messages/": { can_send: true, messages: [DRAFT, { ...DRAFT, id: "pm3", drafted_by: "The Operator", mine: true }] },
      "POST /party/messages/pm1/send/": { ...DRAFT, status: "sent", recipients: 40 },
    }));
    renderApp(<Root />, { path: "/party/messages" });

    const theirs = await screen.findByRole("article", { name: "Draft by Mary Officer" });
    const mine = screen.getByRole("article", { name: "Draft by The Operator" });
    expect(within(mine).queryByRole("button", { name: "Approve and send" })).toBeNull();
    await user.click(within(theirs).getByRole("button", { name: "Approve and send" }));

    await vi.waitFor(() => expect(calls.some((c) => c.path === "/party/messages/pm1/send/")).toBe(true));
  });
});
