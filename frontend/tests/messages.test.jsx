import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
  localStorage.clear();
});

const DRAFT = {
  id: "m1", body: "Town hall on Saturday.", wards: [], ward_names: [], status: "draft", drafted_by: "Achieng Comms",
  decided_by: "", created_at: "2026-10-30T09:00:00Z", decided_at: null, note: "", recipients: 0,
  delivery: {}, mine: false,
};
const page = (canSend, messages = []) => ({
  sender_id: "PAMOJA", provider: "console", can_send: canSend, messages,
  wards: [{ id: "w1", name: "Zimmerman", supporters: 2 }, { id: "w2", name: "Kahawa West", supporters: 1 }],
});
const REACH = { recipients: 2, opted_out: 1, no_number: 0, text: "", parts: 1 };

async function openMessages(role, routes) {
  signIn(role);
  const calls = stubApi(dashboardRoutes({ "POST /messages/preview/": REACH, ...routes }));
  renderApp(<App />);
  const user = userEvent.setup();
  await user.click(await screen.findByRole("link", { name: "Messages" }));
  await screen.findByRole("region", { name: "New SMS" });
  return { calls, user };
}

const posted = (calls, path) => calls.find((c) => c.method === "POST" && c.path === path)?.body;

describe("messages", () => {
  it("sends a comms officer's text for approval, never straight out", async () => {
    const { calls, user } = await openMessages("comms", {
      "GET /messages/?campaign=c1": page(false),
      "POST /messages/": { status: 201, body: { ...DRAFT, mine: true } },
    });

    expect(screen.queryByRole("button", { name: "Send SMS" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Kahawa West" }));
    await user.type(screen.getByRole("textbox", { name: /Message/ }), "Town hall on Saturday.");
    await user.click(screen.getByRole("button", { name: "Send for approval" }));

    await waitFor(() => expect(posted(calls, "/messages/")).toEqual({ campaign: "c1", body: "Town hall on Saturday.", wards: ["w2"], send: false }));
    expect(await screen.findByText("Saved. The candidate or manager sends it.")).toBeInTheDocument();
  });

  it("lets the manager approve a draft, and send a new text only after confirming who it reaches", async () => {
    const { calls, user } = await openMessages("manager", {
      "GET /messages/?campaign=c1": page(true, [DRAFT]),
      "POST /messages/m1/send/": { status: 200, body: { ...DRAFT, status: "sent", recipients: 2 } },
      "POST /messages/": { status: 201, body: { ...DRAFT, status: "sent", recipients: 2 } },
    });

    const drafts = screen.getByRole("region", { name: "Waiting for approval" });
    await user.click(within(drafts).getByRole("button", { name: "Approve and send" }));
    await waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/messages/m1/send/")).toBe(true));

    await user.type(screen.getByRole("textbox", { name: /Message/ }), "Polls open at 6.");
    await user.click(await screen.findByRole("button", { name: "Send SMS" }));
    expect(posted(calls, "/messages/")).toBeUndefined();
    await user.click(screen.getByRole("button", { name: "Send to 2 people" }));

    await waitFor(() => expect(posted(calls, "/messages/")).toEqual({ campaign: "c1", body: "Polls open at 6.", wards: [], send: true }));
    expect(await screen.findByText("Sent to 2 supporters.")).toBeInTheDocument();
  });
});
