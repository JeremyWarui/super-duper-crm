import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Onboarding from "../src/components/Onboarding";
import { useAuth } from "../src/store/auth";
import { fakeSecret, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const GEOGRAPHY = {
  "GET /counties/": [{ id: "cty1", name: "Nairobi City" }],
  "GET /constituencies/": [{ id: "k1", name: "Roysambu" }],
  "GET /wards/": [{ id: "w1", name: "Zimmerman" }],
};

const SETUP_REPLY = {
  id: "c1",
  title: "Jane for Roysambu",
  setup: {
    grain: "ward",
    units: 5,
    total_registered: 153771,
    win_number: 46136,
    note: null,
  },
};

function start(routes = {}) {
  signIn("candidate");
  const calls = stubApi({ ...GEOGRAPHY, ...routes });
  const onDone = vi.fn();
  return { calls, onDone, ...renderApp(<Onboarding onDone={onDone} />) };
}

/** Walk steps 1-3 and stop on the review screen. */
async function walkToReview(user, { office = "MP", ward = false } = {}) {
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

describe("setting a campaign up", () => {
  it("sends only the area that matches the seat", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/campaigns/setup/");
      expect(posted.body).toEqual({
        title: "Jane for Roysambu",
        seat: "mp",
        election_date: "2027-08-10",
        constituency: "k1",
      });
    });
  });

  it("names a county seat on its own and sends only the county", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user, { office: "Senator" });
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    await waitFor(() =>
      expect(calls.find((c) => c.path === "/campaigns/setup/").body).toEqual({
        title: "Jane for Roysambu",
        seat: "senator",
        election_date: "2027-08-10",
        county: "cty1",
      }),
    );
  });

  it("shows the win number the server worked out", async () => {
    const user = userEvent.setup();
    start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText("YOUR CAMPAIGN IS SET UP"),
    ).toBeInTheDocument();
    expect(screen.getByText("46,136")).toBeInTheDocument();
    expect(screen.getByText(/153,771 registered voters/)).toBeInTheDocument();
  });
});

// A login belongs to one campaign, so there is never an existing aspirant to pick.
describe("a manager naming the aspirant", () => {
  function startWithNoAspirants(routes = {}) {
    signIn("manager");
    const calls = stubApi({ ...GEOGRAPHY, ...routes });
    const onDone = vi.fn();
    return { calls, onDone, ...renderApp(<Onboarding onDone={onDone} />) };
  }

  it("creates the aspirant, the campaign and the area in one call", async () => {
    const user = userEvent.setup();
    const issued = fakeSecret();
    const { calls } = startWithNoAspirants({
      "POST /campaigns/setup/": {
        ...SETUP_REPLY,
        candidate_login: {
          id: "a2",
          username: "peter",
          full_name: "Peter Kimani",
          password: issued,
        },
      },
    });

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.type(screen.getByPlaceholderText("0712 345678"), "0712345678");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.type(
      await screen.findByPlaceholderText(/Jane for Roysambu/),
      "Peter for Roysambu",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByText("MP", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.selectOptions(
      (await screen.findAllByRole("combobox"))[0],
      "cty1",
    );
    await user.selectOptions((await screen.findAllByRole("combobox"))[1], "k1");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    const posted = calls.find((c) => c.path === "/campaigns/setup/");
    expect(posted.body).toMatchObject({
      title: "Peter for Roysambu",
      seat: "mp",
      constituency: "k1",
      new_candidate: { username: "peter", phone: "0712345678" },
    });
    expect(posted.body.candidate).toBeUndefined();
    expect(await screen.findByText(issued)).toBeInTheDocument();
  });
});

describe("signing out of setup", () => {
  it("goes back to signed out", async () => {
    const user = userEvent.setup();
    start();
    await user.click(await screen.findByRole("button", { name: "Sign out" }));

    expect(useAuth.getState().token).toBeNull();
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
