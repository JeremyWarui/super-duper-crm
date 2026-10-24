import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Onboarding from "../src/components/Onboarding";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const GEOGRAPHY = {
  "GET /counties/": [{ id: "cty1", name: "Nairobi City" }],
  "GET /constituencies/": [{ id: "k1", name: "Roysambu" }],
  "GET /wards/": [{ id: "w1", name: "Zimmerman" }],
};

const SETUP_REPLY = {
  campaign: { id: "c1", title: "Jane for Roysambu" },
  setup: {
    grain: "ward",
    units: 5,
    total_registered: 153771,
    win_number: 46136,
    note: null,
  },
  logins: [],
};

function start(routes = {}) {
  const calls = stubApi({ ...GEOGRAPHY, ...routes });
  const onDone = vi.fn();
  const onCancel = vi.fn();
  return {
    calls,
    onDone,
    onCancel,
    ...renderApp(<Onboarding onDone={onDone} onCancel={onCancel} />),
  };
}

/** Name the aspirant, skip the manager, and stop on the review screen. */
async function walkToReview(user, { office = "MP", ward = false } = {}) {
  await user.type(screen.getByPlaceholderText("jane"), "jane");
  await user.click(screen.getByRole("button", { name: "Next" }));
  await user.click(screen.getByRole("button", { name: "Skip" }));

  await user.type(
    screen.getByPlaceholderText(/Jane for Roysambu/),
    "Jane for Roysambu",
  );
  await user.click(screen.getByRole("button", { name: "Next" }));

  await user.click(await screen.findByText(office, { selector: "div" }));
  await user.click(screen.getByRole("button", { name: "Next" }));

  const selects = await screen.findAllByRole("combobox");
  await user.selectOptions(selects[0], "cty1");
  // A county-wide seat needs no constituency, so it has only the one picker.
  if (!["Governor", "Senator", "Women Rep"].includes(office)) {
    await user.selectOptions((await screen.findAllByRole("combobox"))[1], "k1");
  }
  if (ward) {
    await user.selectOptions((await screen.findAllByRole("combobox"))[2], "w1");
  }
  await user.click(screen.getByRole("button", { name: "Next" }));
}

const ASPIRANT = {
  username: "jane",
  first_name: "",
  last_name: "",
  phone: "",
  email: "",
};

describe("setting a campaign up from the console", () => {
  it("sends only the area that matches the seat", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "POST /admin/campaigns/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/admin/campaigns/");
      expect(posted.body).toEqual({
        title: "Jane for Roysambu",
        seat: "mp",
        election_date: "2027-08-10",
        constituency: "k1",
        aspirant: ASPIRANT,
        manager: null,
      });
    });
  });

  it("names a county seat on its own and sends only the county", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "POST /admin/campaigns/": SETUP_REPLY });

    await walkToReview(user, { office: "Senator" });
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    await waitFor(() =>
      expect(calls.find((c) => c.path === "/admin/campaigns/").body).toEqual({
        title: "Jane for Roysambu",
        seat: "senator",
        election_date: "2027-08-10",
        county: "cty1",
        aspirant: ASPIRANT,
        manager: null,
      }),
    );
  });

  it("shows the win number the server worked out", async () => {
    const user = userEvent.setup();
    start({ "POST /admin/campaigns/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText("THE CAMPAIGN IS SET UP"),
    ).toBeInTheDocument();
    expect(screen.getByText("46,136")).toBeInTheDocument();
    expect(screen.getByText(/153,771 registered voters/)).toBeInTheDocument();
  });

  it("goes back to the console on Cancel", async () => {
    const user = userEvent.setup();
    const { onCancel } = start();
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    expect(onCancel).toHaveBeenCalled();
  });
});

describe("an MCA seat", () => {
  it("cannot be created in a ward with no registration centres", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": [] });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(
      await screen.findByText(/cannot be set up here until they are/),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Create campaign" }),
    ).toBeDisabled();
  });
});
