import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
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
  const landing = role === "mobilizer" ? "My events" : "Overview";
  await screen.findByRole("button", { name: landing });
  await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
  return { calls, ...rendered };
}

describe("what each role is shown", () => {
  it("gives a campaign manager the full war room", async () => {
    await open("manager");

    expect(screen.getByText(/· Campaign Manager/)).toBeInTheDocument();
    for (const page of [
      "Targets",
      "Wards",
      "Events",
      "Mobilizers",
      "Supporters",
      "Strategy",
    ]) {
      expect(screen.getByRole("button", { name: page })).toBeInTheDocument();
    }
    // Consent is the person's own: the manager shares a link instead of registering people.
    expect(screen.queryByRole("button", { name: "Register supporter" })).toBeNull();
  });

  it("gives a candidate the cockpit and their mobilizers, not the manager's other pages", async () => {
    await open("candidate");

    expect(screen.getByText(/· Candidate/)).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Ward performance" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mobilizers" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Targets" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Supporters" })).toBeNull();
  });

  it("gives a mobilizer only their own three pages", async () => {
    await open("mobilizer");

    expect(screen.getByText(/· Mobilizer/)).toBeInTheDocument();
    for (const page of ["My events", "Register supporter", "My supporters"]) {
      expect(screen.getByRole("button", { name: page })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
  });
});

describe("moving around", () => {
  it("signs the user out", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Sign out" }));

    await waitFor(() => expect(useAuth.getState().token).toBeNull());
  });
});

describe("the forms", () => {
  it("schedules an event with the fields the server expects", async () => {
    const user = userEvent.setup();
    const { calls } = await open("manager", { "POST /events/": { id: "e2" } });

    await user.click(screen.getByRole("button", { name: "Events" }));
    await user.click(
      await screen.findByRole("button", { name: "Schedule event" }),
    );

    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Githurai rally");
    await user.selectOptions(screen.getByRole("combobox"), "w2");
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
      screen.getByRole("button", { name: "Register supporter" }),
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

    await user.click(screen.getByRole("button", { name: "Supporters" }));
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
      screen.getByRole("button", { name: "Register supporter" }),
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
      await screen.findByRole("button", { name: "Register supporter" }),
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
    await user.click(screen.getByRole("button", { name: "Mobilizers" }));
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
      await user.click(screen.getByRole("button", { name: "Save mobilizer" }));

      await waitFor(() => {
        const posted = calls.find((c) => c.path === "/users/");
        expect(posted.body).toMatchObject({
          username: "wanjiku",
          role: "mobilizer",
          first_name: "Wanjiku",
          last_name: "Njeri",
          campaign: "c1",
        });
      });
    });
  }
});
