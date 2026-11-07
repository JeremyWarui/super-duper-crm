/** The published nominations timetable on the website, and the officer drafting it. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root, { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { PARTY, TEST_TOKEN, aspirantRoutes, renderApp, signInAsParty, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const WINDOW = {
  id: "nw1", title: "Nominations 2027", opens_on: "2026-10-25", closes_on: "2026-11-10",
  requirements: "A registered voter in the area.", status: "draft", published_at: null,
  seats: [{ seat: "mca", fee_kes: 5000 }], mine: false,
};

describe("the nominations timetable", () => {
  it("shows the public the published seats, fees and requirements with a way to apply", async () => {
    stubApi({
      "GET /site/": PARTY,
      "GET /party/": {},
      "GET /party/nominations/current/": { ...WINDOW, open: true },
    });
    renderApp(<AppRoutes />, { path: "/vie" });

    const timetable = await screen.findByRole("region", { name: "Nominations 2027" });
    expect(within(timetable).getByText("KES 5,000")).toBeInTheDocument();
    expect(within(timetable).getByText("A registered voter in the area.")).toBeInTheDocument();
    expect(within(timetable).getByRole("link", { name: "Apply from your member account" })).toHaveAttribute("href", "/account");
  });

  it("lets the officer draft a timetable with seat fees, and offers no publish on their own draft", async () => {
    const user = userEvent.setup();
    signInAsParty(["nominations_officer"]);
    const calls = stubApi(aspirantRoutes({
      "GET /party/nominations/windows/": [{ ...WINDOW, mine: true }],
      "POST /party/nominations/windows/": { status: 201, body: { ...WINDOW, id: "nw2", mine: true } },
    }));
    renderApp(<Root />, { path: "/party/aspirants" });

    expect(await screen.findByText("The Party Super Admin publishes it.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
    await user.click(screen.getByRole("button", { name: "Draft a timetable" }));
    await user.type(screen.getByLabelText("Title"), "By-election 2027");
    await user.type(screen.getByLabelText("Opens"), "2027-02-01");
    await user.type(screen.getByLabelText("Closes"), "2027-02-14");
    await user.click(screen.getAllByRole("checkbox")[0]);
    await user.clear(screen.getAllByRole("spinbutton")[0]);
    await user.type(screen.getAllByRole("spinbutton")[0], "2000");
    await user.click(screen.getByRole("button", { name: "Save draft" }));

    await vi.waitFor(() => expect(calls.find((c) => c.method === "POST")).toBeTruthy());
    expect(calls.find((c) => c.method === "POST").body).toMatchObject({
      title: "By-election 2027", opens_on: "2027-02-01", closes_on: "2027-02-14", seats: [{ fee_kes: 2000 }],
    });
  });

  it("tells a Super Admin who drafted a timetable how it gets published", async () => {
    useAuth.setState({
      token: TEST_TOKEN,
      user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true, party_roles: [] },
    });
    stubApi(aspirantRoutes({ "GET /party/nominations/windows/": [{ ...WINDOW, mine: true }] }));
    renderApp(<Root />, { path: "/party/aspirants" });

    expect(await screen.findByText(/A Nominations Officer opens Edit and saves it, then you publish/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).toBeNull();
  });

  it("gives the Super Admin Publish on someone else's draft", async () => {
    const user = userEvent.setup();
    useAuth.setState({
      token: TEST_TOKEN,
      user: { id: "root", username: "root", full_name: "The Operator", role: "manager", is_superuser: true, party_roles: [] },
    });
    const calls = stubApi(aspirantRoutes({
      "GET /party/nominations/windows/": [WINDOW],
      "POST /party/nominations/windows/nw1/publish/": { ...WINDOW, status: "published" },
    }));
    renderApp(<Root />, { path: "/party/aspirants" });

    await user.click(await screen.findByRole("button", { name: "Publish" }));

    await vi.waitFor(() => expect(calls.some((c) => c.path === "/party/nominations/windows/nw1/publish/")).toBe(true));
  });
});
