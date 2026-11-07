import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App, { PAGES } from "../src/App";
import { NAV, pagesOf } from "../src/pages/campaign/helpers";
import { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import {
  CAMPAIGN,
  dashboardRoutes,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Sign in, render, wait for the first page. */
async function open(role = "manager", routes = {}) {
  signIn(role);
  const calls = stubApi(dashboardRoutes(routes));
  const rendered = renderApp(<App />);
  const landing = { mobilizer: "My events", agent: "My centre", comms: "Events" }[role] ?? "Overview";
  await screen.findByRole("link", { name: landing });
  await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
  return { calls, ...rendered };
}

/** The campaign sidebar's groups, each with its links in order. */
const groups = () =>
  Object.fromEntries(
    within(screen.getByRole("navigation", { name: "Workspace" }))
      .getAllByRole("group")
      .map((g) => [g.getAttribute("aria-label"), within(g).getAllByRole("link").map((a) => a.textContent)]),
  );

const LEAD = {
  Plan: ["Overview", "Strategy", "Targets", "Wards"],
  Field: ["Events", "Mobilizers", "Agents", "Assignments", "Supporters", "Volunteers"],
  "Reach out": ["Messages"],
  People: ["Team", "Sign-ups", "Personal data"],
  Money: ["Payments", "Contributions"],
};

describe("what each role is shown", () => {
  it.each([
    ["candidate", "Candidate", LEAD],
    ["manager", "Campaign Manager", LEAD],
    [
      "coordinator",
      "Coordinator",
      { Plan: ["Overview", "Strategy", "Wards"], Field: LEAD.Field, "Reach out": ["Messages"], People: ["Sign-ups"], Money: ["Payments"] },
    ],
    ["comms", "Comms officer", { Field: ["Events"], "Reach out": ["Messages"] }],
    ["mobilizer", "Mobilizer", { "My work": ["My events", "Register supporter", "My supporters", "My payments"] }],
    ["agent", "Agent", { "My work": ["My centre", "My events", "My payments"] }],
  ])("gives a %s exactly their groups", async (role, label, expected) => {
    await open(role);

    expect(screen.getByRole("button", { name: new RegExp(`${label}$`) })).toBeInTheDocument();
    expect(groups()).toEqual(expected);
  });
});

describe("the page frame", () => {
  it("has a page for every entry a workspace menu offers", () => {
    const wheres = [{}, { aspirant: true }, { partyWorkspace: true }, { hosted: true }];
    const offered = Object.keys(NAV).flatMap((role) => wheres.flatMap((w) => pagesOf(role, w).map(([key]) => key)));

    expect(offered.filter((key) => !PAGES[key])).toEqual([]);
  });
});

describe("an MCA race's menu", () => {
  it("names the units page Centres, and Wards everywhere else", () => {
    const unitsLabel = (where) => pagesOf("manager", where).find(([key]) => key === "units")[1];

    expect(unitsLabel({ byCentre: true })).toBe("Centres");
    expect(unitsLabel({})).toBe("Wards");
  });
});

describe("the seat card and the area picker", () => {
  it("shows the seat and area, and offers only the wards the role reads", async () => {
    await open("coordinator", {
      "GET /targets/": [{ id: "t1", ward: "w2", ward_name: "Githurai", registration_centre: null }],
    });
    const card = screen.getByRole("region", { name: "Campaign" });
    const area = screen.getByRole("combobox", { name: "Area" });

    expect(within(card).getByText("Jane Wanjiku")).toBeInTheDocument();
    expect(within(card).getByText("MP · Roysambu")).toBeInTheDocument();
    expect(within(area).getAllByRole("option").map((o) => o.textContent)).toEqual(["Githurai"]);
    expect(screen.getByText("Limited to Githurai.")).toBeInTheDocument();
  });

  it("shows the party workspace as National, with every ward on the picker", async () => {
    await open("manager", {
      "GET /campaigns/": [{ ...CAMPAIGN, kind: "party", candidate_name: "Umoja Party", seat: "National", area_name: "" }],
    });
    const card = screen.getByRole("region", { name: "Campaign" });
    const area = screen.getByRole("combobox", { name: "Area" });

    expect(within(card).getByText("National")).toBeInTheDocument();
    expect(within(area).getAllByRole("option")[0].textContent).toBe("All wards");
  });

  it("hides the picker from a role that reads no wards", async () => {
    await open("comms");

    expect(screen.queryByRole("combobox", { name: "Area" })).toBeNull();
  });
});

describe("moving around", () => {
  it("signs the user out", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: /Campaign Manager$/ }));
    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(useAuth.getState().token).toBeNull());
  });
});

describe("the phone menu", () => {
  it("opens the sidebar drawer and closes it with Escape", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Open menu" }));
    expect(screen.getByRole("button", { name: "Close menu" })).toBeInTheDocument();
    await user.keyboard("{Escape}");

    expect(screen.queryByRole("button", { name: "Close menu" })).toBeNull();
  });
});

describe("the forms", () => {
  it("schedules an event with the fields the server expects", async () => {
    const user = userEvent.setup();
    const { calls } = await open("manager", { "POST /events/": { id: "e2" } });

    await user.click(screen.getByRole("link", { name: "Events" }));
    await user.click(
      await screen.findByRole("button", { name: "Schedule event" }),
    );

    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Githurai rally");
    await user.selectOptions(screen.getAllByRole("combobox").at(-1), "w2");
    await user.type(boxes[1], "Githurai grounds");
    await user.type(document.querySelector('input[type="date"]'), "2027-06-12");
    await user.click(
      screen.getAllByRole("button", { name: "Schedule event" }).at(-1),
    );

    await waitFor(() => {
      const posted = calls.find(
        (c) => c.method === "POST" && c.path === "/events/",
      );
      expect(posted.body).toEqual({
        campaign: "c1",
        ward: "w2",
        registration_centre: null,
        title: "Githurai rally",
        venue: "Githurai grounds",
        scheduled_date: "2027-06-12",
        status: "planned",
      });
    });
  });

  it("registers a supporter, counted as one unless changed, once consent is ticked", async () => {
    const user = userEvent.setup();
    const { calls } = await open("mobilizer", {
      "POST /supporters/": { id: "s1" },
    });

    await user.click(
      screen.getByRole("link", { name: "Register supporter" }),
    );
    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");
    await user.type(boxes[1], "+254700333444");
    await user.click(screen.getByRole("checkbox"));
    await user.click(
      screen.getAllByRole("button", { name: "Register supporter" }).at(-1),
    );

    await waitFor(() => {
      const posted = calls.find(
        (c) => c.method === "POST" && c.path === "/supporters/",
      );
      expect(posted.body).toEqual({
        campaign: "c1",
        full_name: "Wanjiku Njeri",
        phone: "+254700333444",
        ward: "w1",
        support_level: "supporter",
        consent_given: true,
        registration_centre: null,
      });
    });
  });
});

describe("an MCA race's supporters", () => {
  it("puts a supporter with no centre at the one picked", async () => {
    const user = userEvent.setup();
    const { calls } = await open("manager", {
      "GET /campaigns/": [
        { ...CAMPAIGN, operational_grain: "centre", ward: "w1" },
      ],
      "GET /centres/": [
        { id: "rc1", name: "Zimmerman Primary" },
        { id: "rc3", name: "Late Centre" },
      ],
      "GET /targets/": [{ id: "t1", ward: "w1", registration_centre: "rc1" }],
      "GET /supporters/": [
        {
          id: "s1",
          full_name: "Wanjiku Njeri",
          phone: "",
          support_level: "supporter",
          consent_given: true,
          registration_centre: null,
        },
      ],
      "PATCH /supporters/s1/": { id: "s1" },
    });

    await user.click(screen.getByRole("link", { name: "Supporters" }));
    const picker = await screen.findByRole("combobox", {
      name: "Centre for Wanjiku Njeri",
    });
    await screen.findByRole("option", { name: "Zimmerman Primary" });
    expect(screen.queryByRole("option", { name: "Late Centre" })).toBeNull();
    await user.selectOptions(picker, "rc1");

    await waitFor(() => {
      const placed = calls.find((c) => c.method === "PATCH");
      expect([placed.path, placed.body]).toEqual([
        "/supporters/s1/",
        { registration_centre: "rc1" },
      ]);
    });
  });
});

describe("registering a supporter in an MCA race", () => {
  const MCA_TARGETS = ["rc1", "rc2"].map((centre) => ({
    id: `t-${centre}`,
    ward: "w1",
    ward_name: "Zimmerman",
    registration_centre: centre,
  }));
  const mca = (mobilizer) => ({
    "GET /campaigns/": [
      { ...CAMPAIGN, operational_grain: "centre", ward: "w1" },
    ],
    "GET /centres/": [
      { id: "rc1", name: "Zimmerman Primary" },
      { id: "rc2", name: "Githurai Primary" },
      { id: "rc3", name: "Late Centre" },
    ],
    "GET /mobilizers/": [
      { id: "m1", user: "u1", ward: "w1", registration_centre: mobilizer },
    ],
    "GET /targets/": MCA_TARGETS,
    "POST /supporters/": { id: "s1" },
  });

  async function fill(user) {
    await user.click(
      screen.getByRole("link", { name: "Register supporter" }),
    );
    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");
    await user.click(screen.getByRole("checkbox"));
    await screen.findByRole("option", { name: "Githurai Primary" });
  }

  it("files them at the mobilizer's own centre", async () => {
    const user = userEvent.setup();
    const { calls } = await open("mobilizer", mca("rc2"));
    await fill(user);
    await user.click(
      screen.getAllByRole("button", { name: "Register supporter" }).at(-1),
    );

    await waitFor(() => {
      const posted = calls.find(
        (c) => c.method === "POST" && c.path === "/supporters/",
      );
      expect(posted.body.registration_centre).toBe("rc2");
    });
  });

  it("files them in the ward once it loads after the form opened", async () => {
    const user = userEvent.setup();
    signIn("mobilizer");
    const routes = dashboardRoutes({ ...mca("rc2"), "GET /targets/": [] });
    const calls = stubApi(routes);
    const { queryClient } = renderApp(<App />);
    await user.click(
      await screen.findByRole("link", { name: "Register supporter" }),
    );
    routes["GET /targets/"] = MCA_TARGETS;
    await queryClient.invalidateQueries({ queryKey: ["targets"] });
    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");
    await user.click(screen.getByRole("checkbox"));
    await screen.findByRole("option", { name: "Githurai Primary" });
    await user.click(
      screen.getAllByRole("button", { name: "Register supporter" }).at(-1),
    );

    await waitFor(() => {
      const posted = calls.find(
        (c) => c.method === "POST" && c.path === "/supporters/",
      );
      expect([posted.body.ward, posted.body.registration_centre]).toEqual([
        "w1",
        "rc2",
      ]);
    });
  });

  it("waits for a centre when the mobilizer has none", async () => {
    const user = userEvent.setup();
    await open("mobilizer", mca(null));
    await fill(user);
    const submit = screen
      .getAllByRole("button", { name: "Register supporter" })
      .at(-1);

    expect(submit).toBeDisabled();
    expect(screen.queryByRole("option", { name: "Late Centre" })).toBeNull();
    await user.selectOptions(
      screen.getByRole("combobox", { name: "Registration centre" }),
      "rc1",
    );
    expect(submit).toBeEnabled();
  });
});

describe("adding a mobilizer", () => {
  async function openForm(user) {
    await user.click(screen.getByRole("link", { name: "Mobilizers" }));
    await user.click(
      await screen.findByRole("button", { name: "Add mobilizer" }),
    );
  }

  for (const role of ["manager", "candidate"]) {
    it(`creates a login instead for a ${role}, when one is wanted`, async () => {
      const user = userEvent.setup();
      const { calls } = await open(role);
      await openForm(user);

      const boxes = await screen.findAllByRole("textbox");
      await user.type(boxes[0], "Wanjiku Njeri");
      await user.click(screen.getByRole("checkbox"));
      await user.type(await screen.findByPlaceholderText("juma"), "Wanjiku");
      await user.type(screen.getByRole("textbox", { name: "Email" }), "wanjiku@example.com");
      await user.click(screen.getByRole("button", { name: "Save mobilizer" }));

      await waitFor(() => {
        const posted = calls.find((c) => c.path === "/users/");
        expect(posted.body).toMatchObject({
          username: "wanjiku",
          email: "wanjiku@example.com",
          role: "mobilizer",
          first_name: "Wanjiku",
          last_name: "Njeri",
          campaign: "c1",
        });
      });
    });
  }
});

describe("the routes", () => {
  it("sends a manager who opens a page outside their menu to their first page", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<App />, { path: "/campaign/mypayments" });

    expect(await screen.findByText("Your command view of the seat.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Overview" })).toHaveAttribute("aria-current", "page");
  });

  it("opens the sign-up page at /join/:code without a login", async () => {
    stubApi({
      "GET /join/x/": { campaign_title: "Jane for Roysambu", candidate_name: "Jane", event_title: "Town hall", ward_name: "Zimmerman", open: true, consent_wording: "Consent wording.", place: null, places: [] },
    });
    renderApp(<AppRoutes />, { path: "/join/x" });

    expect(await screen.findByRole("textbox", { name: "Full name" })).toBeInTheDocument();
  });
});
