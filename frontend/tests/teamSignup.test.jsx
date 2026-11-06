import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { AppRoutes } from "../src/Gate";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PAGE = {
  campaign_title: "Jane for Roysambu", seat_label: "MP seat", open: true,
  consent_wording: "I agree to be vetted.", mobilizer_place: "ward",
  wards: [{ id: "w1", name: "Zimmerman", county_name: "Nairobi City" }, { id: "w2", name: "Githurai", county_name: "Nairobi City" }],
};
const PENDING = {
  id: "r1", role: "agent", full_name: "Achieng Otieno", phone: "+254712345001", email: "achieng@example.com",
  id_number: "12345678", ward_name: "Zimmerman", centre_name: "Zimmerman Primary", status: "pending", reason: "",
  created_at: "2026-11-06T09:00:00Z",
};
const AGENT = {
  id: "a1", full_name: "Achieng Otieno", phone: "+254712345001", id_number: null, registration_centre: "rc1",
  centre_name: "Zimmerman Primary", ward_name: "Zimmerman", status: "applied", training_date: null,
};

const posted = (calls, method = "POST") => calls.find((c) => c.method === method);

describe("the public team sign-up", () => {
  it("signs an agent up at the centre they pick in their ward", async () => {
    const calls = stubApi({
      "GET /site/": { name: "Umoja Party", organisation_type: "party" },
      "GET /team-signup/t1/": PAGE,
      "GET /team-signup/t1/centres/?ward=w1": [{ id: "rc1", name: "Zimmerman Primary" }],
      "POST /team-signup/t1/": { message: "Thank you. The campaign will review your sign-up." },
    });
    renderApp(<AppRoutes />, { path: "/team/t1" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("radio", { name: /Agent/ }));
    await user.type(screen.getByRole("textbox", { name: "First name" }), "Achieng");
    await user.type(screen.getByRole("textbox", { name: "Phone" }), "0712 345001");
    await user.type(screen.getByRole("textbox", { name: /^Email/ }), "achieng@example.com");
    await user.type(screen.getByRole("textbox", { name: /^ID number/ }), "12345678");
    await user.selectOptions(screen.getByRole("combobox", { name: "Ward" }), "w1");
    await user.selectOptions(await screen.findByRole("combobox", { name: "Registration centre" }), "rc1");
    await user.click(screen.getByRole("checkbox", { name: "I agree to be vetted." }));
    await user.click(screen.getByRole("button", { name: "Sign up" }));

    expect(await screen.findByText(/campaign will review your sign-up/)).toBeInTheDocument();
    expect(posted(calls).body).toEqual({
      role: "agent", first_name: "Achieng", last_name: "", phone: "0712 345001", email: "achieng@example.com",
      id_number: "12345678", consent_given: true, ward: null, registration_centre: "rc1",
    });
  });
});

describe("the sign-up queue", () => {
  async function openQueue(routes = {}) {
    signIn("manager");
    const calls = stubApi(dashboardRoutes({
      "GET /campaigns/c1/team-link/": { code: "t1" },
      "GET /campaigns/c1/registrations/?status=pending": [PENDING],
      ...routes,
    }));
    renderApp(<App />);
    const user = userEvent.setup();
    await user.click(await screen.findByRole("link", { name: "Sign-ups" }));
    await screen.findByText("Achieng Otieno");
    return { calls, user };
  }

  it("approves a sign-up and says the invite went by email", async () => {
    const { calls, user } = await openQueue({
      "POST /campaigns/c1/registrations/r1/approve/": { registration: { ...PENDING, status: "approved" }, invite: "email", placed: true },
    });

    expect(screen.getByText(/\/team\/t1$/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Approve Achieng Otieno" }));

    expect(await screen.findByText(/Achieng Otieno is approved\. We emailed them a link/)).toBeInTheDocument();
    expect(posted(calls).path).toBe("/campaigns/c1/registrations/r1/approve/");
  });

  it("rejects a sign-up only once a reason is given", async () => {
    const { calls, user } = await openQueue({
      "POST /campaigns/c1/registrations/r1/reject/": { ...PENDING, status: "rejected", reason: "Unknown to us" },
    });

    await user.click(screen.getByRole("button", { name: "Reject Achieng Otieno" }));
    const confirm = screen.getByRole("button", { name: "Reject with this reason" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByRole("textbox", { name: "Reason for not approving Achieng Otieno" }), "Unknown to us");
    await user.click(confirm);

    await waitFor(() => expect(posted(calls).body).toEqual({ reason: "Unknown to us" }));
  });
});

describe("the agents page", () => {
  it("lists the centres with no agent and saves an agent's status", async () => {
    signIn("manager");
    const calls = stubApi(dashboardRoutes({
      "GET /agents/?campaign=c1": [AGENT],
      "GET /agents/coverage/?campaign=c1": { centres: 2, covered: 1, uncovered: [{ id: "rc2", name: "Githurai Primary", ward_name: "Githurai" }], more_uncovered: 0 },
      "PATCH /agents/a1/": { ...AGENT, status: "vetted" },
    }));
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("link", { name: "Agents" }));
    const coverage = within(await screen.findByRole("region", { name: "Coverage" }));
    expect(coverage.getByText("Githurai Primary")).toBeInTheDocument();
    await user.selectOptions(screen.getByRole("combobox", { name: "Status of Achieng Otieno" }), "vetted");

    await waitFor(() => expect(posted(calls, "PATCH").body).toEqual({ status: "vetted" }));
  });
});

describe("an agent's own view", () => {
  it("shows their centre and where they stand", async () => {
    signIn("agent");
    stubApi(dashboardRoutes({ "GET /agents/?campaign=c1": [{ ...AGENT, status: "vetted", id_number: "12345678" }] }));
    renderApp(<App />);

    const centre = within(await screen.findByRole("region", { name: "Your centre" }));
    expect(centre.getByText("Zimmerman Primary")).toBeInTheDocument();
    expect(screen.getByText(/ID 12345678/)).toBeInTheDocument();
    const progress = within(screen.getByRole("region", { name: "Your progress" }));
    expect(progress.getAllByText("Done")).toHaveLength(2);
  });
});
