/** Personal data in a workspace: requests logged and answered, and people erased on request. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root from "../src/Gate";
import { CAMPAIGN, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const SUPPORTER = { id: "s1", full_name: "Wanjiru Kamau", phone: "+254711000111", support_level: "supporter", consent_given: true, erased_at: null };
const REQUEST = {
  id: "r1", kind: "erasure", requester_name: "Otieno Ouma", requester_contact: "0711000222", details: "", received_on: "2026-11-01",
  due_on: "2026-11-15", status: "open", answer: "", answered_at: null, overdue: true,
};
const CLOSE = { closed_at: null, retention_months: 6, erase_from: null, supporters_erased_at: null, supporters: 1, erased: 0 };

function open(page, routes = {}, campaign = CAMPAIGN) {
  signIn("candidate");
  const calls = stubApi(dashboardRoutes({
    "GET /campaigns/": [campaign],
    "GET /supporters/": [SUPPORTER],
    "GET /campaigns/c1/data/requests/": [REQUEST],
    "POST /campaigns/c1/data/requests/": REQUEST,
    "PATCH /campaigns/c1/data/requests/r1/": { ...REQUEST, status: "done" },
    "GET /campaigns/c1/data/left-team/": [],
    "GET /campaigns/c1/data/close/": CLOSE,
    "POST /campaigns/c1/data/supporters/s1/erase/": null,
    ...routes,
  }));
  renderApp(<Root />, { path: `/campaign/${page}` });
  return calls;
}

describe("personal data", () => {
  it("logs a request with when it came in, and marks one answered with how", async () => {
    const user = userEvent.setup();
    const calls = open("privacy");

    const panel = await screen.findByRole("region", { name: "Data requests" });
    expect(within(panel).getByText("1 overdue")).toBeInTheDocument();
    await user.click(within(panel).getByRole("button", { name: "Log a request" }));
    await user.selectOptions(within(panel).getByRole("combobox", { name: "Request" }), "correction");
    await user.type(within(panel).getByLabelText("Who asked"), "Mary Akinyi");
    await user.type(within(panel).getByLabelText("Phone or email to answer"), "0711000333");
    await user.click(within(panel).getByRole("button", { name: "Log request" }));
    await user.click(within(panel).getByRole("button", { name: "Answer" }));
    await user.type(within(panel).getByLabelText("How it was answered: Otieno Ouma"), "Erased on the Supporters page.");
    await user.click(within(panel).getByRole("button", { name: "Mark answered" }));

    await vi.waitFor(() => expect(calls.find((c) => c.method === "PATCH")?.body).toEqual({ answer: "Erased on the Supporters page.", status: "done" }));
    const logged = calls.find((c) => c.method === "POST").body;
    expect(logged).toMatchObject({ kind: "correction", requester_name: "Mary Akinyi", requester_contact: "0711000333" });
    expect(logged.received_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
  });

  it("erases a supporter only after the second press", async () => {
    const user = userEvent.setup();
    const calls = open("supporters");

    await user.click(await screen.findByRole("button", { name: "Erase Wanjiru Kamau" }));
    expect(calls.some((c) => c.path.endsWith("/erase/"))).toBe(false);
    await user.click(screen.getByRole("button", { name: "Yes, erase Wanjiru Kamau" }));

    await vi.waitFor(() => expect(calls.some((c) => c.method === "POST" && c.path === "/campaigns/c1/data/supporters/s1/erase/")).toBe(true));
  });

  it("tells everyone a closed campaign is read-only", async () => {
    open("supporters", {}, { ...CAMPAIGN, closed_at: "2027-09-01T00:00:00Z" });

    expect(await screen.findByText("This campaign is closed: it is read-only.")).toBeInTheDocument();
  });
});
