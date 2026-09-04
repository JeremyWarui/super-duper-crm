import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { useAuth } from "../src/store/auth";
import { STRATEGY, dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Sign in, render, and wait for the first page to finish loading. */
async function open(role = "manager", routes = {}) {
  signIn(role);
  const calls = stubApi(dashboardRoutes(routes));
  const rendered = renderApp(<App />);
  const landing = role === "mobilizer" ? "My events" : "Overview";
  await screen.findByRole("button", { name: landing });
  await waitFor(() => expect(screen.queryByText("Loading…")).toBeNull());
  return { calls, ...rendered };
}

describe("the dashboard", () => {
  it("shows the campaign it is working on", async () => {
    await open();
    expect(screen.getAllByText("Jane for Roysambu").length).toBeGreaterThan(0);
  });

  it("says there is nothing to work on when no campaign came back", async () => {
    signIn("mobilizer");
    stubApi(dashboardRoutes({ "GET /campaigns/": [] }));
    renderApp(<App />);

    expect(await screen.findByText(/No campaign yet/)).toBeInTheDocument();
  });

  it("leads with the votes needed to win the seat", async () => {
    await open();

    expect(screen.getByText("VOTES TO WIN THE SEAT")).toBeInTheDocument();
    expect(screen.getByText("19,981")).toBeInTheDocument();
    expect(screen.getByText("9,211 committed")).toBeInTheDocument();
    expect(screen.getByText(/46\.1% there/)).toBeInTheDocument();
  });

  it("counts coverage out of the units the server reported", async () => {
    await open();

    expect(screen.getByText("Registered voters")).toBeInTheDocument();
    expect(screen.getByText("66,600")).toBeInTheDocument();
    expect(screen.getByText("Units covered")).toBeInTheDocument();
    // One of the two units has an event, and one of the two has an organiser.
    expect(screen.getAllByText("1 / 2")).toHaveLength(2);
    expect(screen.getByText("Units behind")).toBeInTheDocument();
  });

  it("colours a unit by how far along it is", async () => {
    await open();

    expect(screen.getByText("Target met")).toBeInTheDocument();
    expect(screen.getByText("Behind")).toBeInTheDocument();
  });

  it("shows the strategy read the server computed", async () => {
    await open();
    expect(screen.getByText("Go next: Githurai")).toBeInTheDocument();
  });

  it("says coverage looks balanced when there is nothing to flag", async () => {
    await open("manager", { "GET /strategy/": { ...STRATEGY, notes: [] } });
    expect(screen.getByText(/coverage looks balanced/)).toBeInTheDocument();
  });

  it("asks the server only for this campaign's data", async () => {
    const { calls } = await open();
    const strategy = calls.find((c) => c.path.startsWith("/strategy/"));
    expect(strategy.path).toBe("/strategy/?campaign=c1");
  });
});

describe("what each role is shown", () => {
  it("gives a campaign manager the full war room", async () => {
    await open("manager");

    expect(screen.getByText(/· Campaign Manager/)).toBeInTheDocument();
    for (const page of ["Targets", "Wards", "Events", "Mobilizers", "Supporters", "Strategy"]) {
      expect(screen.getByRole("button", { name: page })).toBeInTheDocument();
    }
  });

  it("gives a candidate a read-only cockpit", async () => {
    await open("candidate");

    expect(screen.getByText(/· Candidate/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Ward performance" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Targets" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Mobilizers" })).toBeNull();
  });

  it("gives a candidate no way to assign a mobilizer", async () => {
    await open("candidate");

    expect(screen.getByText("Unassigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign" })).toBeNull();
  });

  it("gives a manager the assign button the candidate does not get", async () => {
    await open("manager");
    expect(screen.getByRole("button", { name: "Assign" })).toBeInTheDocument();
  });

  it("gives a mobilizer only their own three pages", async () => {
    await open("mobilizer");

    expect(screen.getByText(/· Mobilizer/)).toBeInTheDocument();
    for (const page of ["My events", "Register supporter", "My supporters"]) {
      expect(screen.getByRole("button", { name: page })).toBeInTheDocument();
    }
    expect(screen.queryByRole("button", { name: "Overview" })).toBeNull();
  });

  it("opens a mobilizer straight onto their events", async () => {
    await open("mobilizer");
    expect(screen.getByText("Zimmerman town hall")).toBeInTheDocument();
  });
});

describe("moving around", () => {
  it("switches page when a nav item is clicked", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Targets" }));

    expect(await screen.findByText("Targets — the win number")).toBeInTheDocument();
    expect(screen.getByText("TOTAL WIN NUMBER")).toBeInTheDocument();
  });

  it("names a ward target by its ward", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Targets" }));

    expect(await screen.findByText("30,701")).toBeInTheDocument();
    expect(screen.getAllByText("Zimmerman").length).toBeGreaterThan(0);
  });

  it("names a centre target by its centre", async () => {
    const user = userEvent.setup();
    await open("manager", {
      "GET /targets/": [
        {
          id: "t3",
          campaign: "c1",
          ward: "w1",
          ward_name: "Zimmerman",
          registration_centre: "rc1",
          centre_name: "Zimmerman Primary",
          registered_voters: 2500,
          projected_turnout_pct: "60.00",
          votes_needed: 751,
          votes_committed: 0,
          votes_remaining: 751,
          progress_pct: 0,
        },
      ],
    });

    await user.click(screen.getByRole("button", { name: "Targets" }));

    expect(await screen.findByText("Zimmerman Primary")).toBeInTheDocument();
  });

  it("lists events with their status and venue", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Events" }));

    expect(await screen.findByText("Zimmerman town hall")).toBeInTheDocument();
    expect(screen.getByText("Social hall")).toBeInTheDocument();
    expect(screen.getByText("Planned")).toBeInTheDocument();
  });

  it("says so plainly when a list is empty", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Mobilizers" }));

    expect(await screen.findByText("No mobilizers yet.")).toBeInTheDocument();
  });

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
    await user.click(await screen.findByRole("button", { name: "Schedule event" }));

    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Githurai rally");
    await user.selectOptions(screen.getByRole("combobox"), "w2");
    await user.type(boxes[1], "Githurai grounds");
    await user.type(document.querySelector('input[type="date"]'), "2027-06-12");
    await user.click(screen.getAllByRole("button", { name: "Schedule event" }).at(-1));

    await waitFor(() => {
      const posted = calls.find((c) => c.method === "POST" && c.path === "/events/");
      expect(posted.body).toEqual({
        campaign: "c1",
        ward: "w2",
        title: "Githurai rally",
        venue: "Githurai grounds",
        scheduled_date: "2027-06-12",
        status: "planned",
      });
    });
  });

  it("adds a mobilizer against a ward", async () => {
    const user = userEvent.setup();
    const { calls } = await open("manager", { "POST /mobilizers/": { id: "m2" } });

    await user.click(screen.getByRole("button", { name: "Mobilizers" }));
    await user.click(await screen.findByRole("button", { name: "Add mobilizer" }));

    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");
    await user.type(boxes[1], "+254700111222");
    await user.click(screen.getByRole("button", { name: "Save mobilizer" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.method === "POST" && c.path === "/mobilizers/");
      expect(posted.body).toEqual({
        campaign: "c1",
        ward: "w1",
        full_name: "Wanjiku Njeri",
        phone: "+254700111222",
      });
    });
  });

  it("will not register a supporter without consent", async () => {
    const user = userEvent.setup();
    await open("mobilizer");

    await user.click(screen.getByRole("button", { name: "Register supporter" }));
    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");

    // The nav item keeps the same name; the form's own button is the last one.
    expect(screen.getAllByRole("button", { name: "Register supporter" }).at(-1)).toBeDisabled();
  });

  it("registers a supporter once consent is ticked", async () => {
    const user = userEvent.setup();
    const { calls } = await open("mobilizer", { "POST /supporters/": { id: "s1" } });

    await user.click(screen.getByRole("button", { name: "Register supporter" }));
    const boxes = await screen.findAllByRole("textbox");
    await user.type(boxes[0], "Wanjiku Njeri");
    await user.type(boxes[1], "+254700333444");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getAllByRole("button", { name: "Register supporter" }).at(-1));

    await waitFor(() => {
      const posted = calls.find((c) => c.method === "POST" && c.path === "/supporters/");
      expect(posted.body).toEqual({
        campaign: "c1",
        full_name: "Wanjiku Njeri",
        phone: "+254700333444",
        ward: "w1",
        consent_given: true,
      });
    });
  });

  it("records attendance against the event it was opened from", async () => {
    const user = userEvent.setup();
    const { calls } = await open("manager", { "POST /events/e1/record/": { id: "e1" } });

    await user.click(screen.getByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Record" }));

    const numbers = document.querySelectorAll('input[type="number"]');
    await user.type(numbers[0], "400");
    await user.type(numbers[1], "300");
    await user.click(screen.getByRole("button", { name: "Save & mark done" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.method === "POST" && c.path === "/events/e1/record/");
      expect(posted.body).toEqual({ number_reached: 400, number_attended: 300 });
    });
  });

  it("refuses attendance above the number reached, before it is sent", async () => {
    const user = userEvent.setup();
    await open("manager");

    await user.click(screen.getByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Record" }));

    const numbers = document.querySelectorAll('input[type="number"]');
    await user.type(numbers[0], "100");
    await user.type(numbers[1], "200");

    expect(screen.getByText("Attendance can't exceed those reached.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save & mark done" })).toBeDisabled();
  });
});
