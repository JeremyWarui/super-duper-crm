import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { useAuth } from "../src/store/auth";
import {
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
        title: "Githurai rally",
        venue: "Githurai grounds",
        scheduled_date: "2027-06-12",
        status: "planned",
      });
    });
  });

  it("registers a supporter once consent is ticked", async () => {
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
        consent_given: true,
      });
    });
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
