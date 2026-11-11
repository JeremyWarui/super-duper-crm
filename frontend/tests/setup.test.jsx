import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { fakeSecret, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const NOT_SET_UP = { status: 503, body: { detail: "Not set up.", code: "not_set_up" } };
const TOKEN = fakeSecret();

async function openWizard(user, routes = {}) {
  const stubbed = { "GET /site/": NOT_SET_UP, "POST /setup/check/": { status: 204, body: null }, ...routes };
  const calls = stubApi(stubbed);
  calls.routes = stubbed;
  renderApp(<AppRoutes />, { path: "/campaign/overview" });
  await user.type(await screen.findByRole("textbox", { name: "Setup token" }), TOKEN);
  await user.click(screen.getByRole("button", { name: "Start setup" }));
  await screen.findByRole("list", { name: "Steps" });
  return calls;
}

describe("first-run setup", () => {
  it("sends every page to /setup and refuses a wrong token", async () => {
    const user = userEvent.setup();
    stubApi({ "GET /site/": NOT_SET_UP, "POST /setup/check/": { status: 403, body: { detail: "That setup token is wrong." } } });
    renderApp(<AppRoutes />, { path: "/news" });

    await user.type(await screen.findByRole("textbox", { name: "Setup token" }), "wrong");
    await user.click(screen.getByRole("button", { name: "Start setup" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("That setup token is wrong.");
    expect(screen.queryByRole("list", { name: "Steps" })).toBeNull();
  });

  it("sets up an aspirant installation with its seat and candidate in one request", async () => {
    const user = userEvent.setup();
    const password = fakeSecret();
    const calls = await openWizard(user, {
      "GET /setup/areas/?level=county": [{ id: "k1", name: "Nairobi" }],
      "GET /setup/areas/?level=constituency&parent=k1": [{ id: "c1", name: "Westlands" }],
      "GET /setup/areas/?level=ward&parent=c1": [{ id: "w1", name: "Parklands" }],
      "POST /setup/": { organisation_type: "aspirant", superuser: "owner", workspace: "x", invites: ["email"], services: [] },
    });
    const next = () => user.click(screen.getByRole("button", { name: "Next" }));

    await user.click(screen.getByRole("button", { name: /An aspirant/ }));
    await next();
    await user.type(screen.getByRole("textbox", { name: "Name" }), "Jane for Parklands");
    await next();
    await next();
    await user.type(screen.getByRole("textbox", { name: "Username" }), "owner");
    await user.type(screen.getByRole("textbox", { name: "Email" }), "owner@example.com");
    await user.type(screen.getByLabelText(/^Password(?! again)/), password);
    await user.type(screen.getByLabelText("Password again"), password);
    await next();
    await user.type(screen.getByRole("textbox", { name: /^Campaign name/ }), "Jane for Parklands");
    await user.selectOptions(screen.getByRole("combobox", { name: "County" }), await screen.findByRole("option", { name: "Nairobi" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Constituency" }), await screen.findByRole("option", { name: "Westlands" }));
    await user.selectOptions(screen.getByRole("combobox", { name: "Ward" }), await screen.findByRole("option", { name: "Parklands" }));
    await user.type(screen.getByRole("textbox", { name: "Candidate username" }), "jane");
    await user.type(screen.getByRole("textbox", { name: /^Candidate email/ }), "jane@example.com");
    await next();
    calls.routes["GET /site/"] = { organisation_type: "aspirant", name: "Jane for Parklands" };
    await user.click(screen.getByRole("button", { name: "Finish setup" }));

    expect(await screen.findByText("Set up.")).toBeInTheDocument();
    // The site now answers set up; the summary stays for the service tests.
    await waitFor(() => expect(calls.filter((c) => c.path === "/site/").length).toBeGreaterThan(1));
    expect(screen.getByRole("region", { name: "Outside services" })).toBeInTheDocument();
    const sent = calls.find((c) => c.method === "POST" && c.path === "/setup/").body;
    expect(sent).toMatchObject({
      token: TOKEN,
      organisation_type: "aspirant",
      site: { name: "Jane for Parklands", primary_colour: "#0B5D3B" },
      superuser: { username: "owner", email: "owner@example.com", password },
      aspirant: { title: "Jane for Parklands", seat: "mca", ward: "w1", candidate: { username: "jane", email: "jane@example.com" } },
    });
    expect(sent.party_workspace).toBeUndefined();
  });
});

describe("a set-up installation", () => {
  it("sends /setup home", async () => {
    stubApi({ "GET /site/": { organisation_type: "party", name: "Party" } });
    renderApp(<AppRoutes />, { path: "/setup" });

    await waitFor(() => expect(screen.queryByRole("textbox", { name: "Setup token" })).toBeNull());
  });
});
