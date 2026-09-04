import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Onboarding from "../src/components/Onboarding";
import { renderApp, signIn, stubApi } from "./helpers";

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
  await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane for Roysambu");
  await user.click(screen.getByRole("button", { name: "Next" }));

  await user.click(await screen.findByText(office, { selector: "div" }));
  await user.click(screen.getByRole("button", { name: "Next" }));

  const selects = await screen.findAllByRole("combobox");
  await user.selectOptions(selects[0], "cty1");
  // A county-wide seat needs no constituency, so it has only the one picker.
  if (office !== "Governor / Senator / Woman Rep") {
    await user.selectOptions((await screen.findAllByRole("combobox"))[1], "k1");
  }
  if (ward) {
    await user.selectOptions((await screen.findAllByRole("combobox"))[2], "w1");
  }
  await user.click(screen.getByRole("button", { name: "Next" }));
}

describe("setting a campaign up", () => {
  it("starts on the campaign name and counts the steps", async () => {
    start();
    expect(await screen.findByText(/step 1 of 4/)).toBeInTheDocument();
    expect(screen.getByText("Campaign name")).toBeInTheDocument();
  });

  it("will not move on without a name", async () => {
    start();
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("offers the three seats a campaign can contest", async () => {
    const user = userEvent.setup();
    start();

    await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane for Roysambu");
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("MCA")).toBeInTheDocument();
    expect(screen.getByText("MP")).toBeInTheDocument();
    expect(screen.getByText("Governor / Senator / Woman Rep")).toBeInTheDocument();
  });

  it("asks an MP campaign for a constituency and not a ward", async () => {
    const user = userEvent.setup();
    start();

    await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByText("MP", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("County")).toBeInTheDocument();
    expect(screen.getByText("Constituency")).toBeInTheDocument();
    expect(screen.queryByText("Ward")).toBeNull();
  });

  it("asks an MCA campaign for a ward as well", async () => {
    const user = userEvent.setup();
    start();

    await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByText("MCA", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Ward")).toBeInTheDocument();
  });

  it("keeps the constituency picker shut until a county is chosen", async () => {
    const user = userEvent.setup();
    start();

    await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByText("MP", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect((await screen.findAllByRole("combobox"))[1]).toBeDisabled();
  });

  it("sends only the area that matches the seat", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(await screen.findByRole("button", { name: "Create campaign" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/campaigns/setup/");
      expect(posted.body).toEqual({
        title: "Jane for Roysambu",
        office_level: "constituency",
        election_date: "2027-08-10",
        constituency: "k1",
      });
    });
  });

  it("shows the win number the server worked out", async () => {
    const user = userEvent.setup();
    start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(await screen.findByRole("button", { name: "Create campaign" }));

    expect(await screen.findByText("YOUR CAMPAIGN IS SET UP")).toBeInTheDocument();
    expect(screen.getByText("46,136")).toBeInTheDocument();
    expect(screen.getByText(/153,771 registered voters/)).toBeInTheDocument();
  });

  it("passes the setup on to the dashboard", async () => {
    const user = userEvent.setup();
    const { onDone } = start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(await screen.findByRole("button", { name: "Create campaign" }));
    await user.click(await screen.findByRole("button", { name: /Go to my dashboard/ }));

    expect(onDone).toHaveBeenCalledWith(SETUP_REPLY);
  });

  it("passes on the note when a ward has no centres loaded", async () => {
    const user = userEvent.setup();
    start({
      "POST /campaigns/setup/": {
        ...SETUP_REPLY,
        setup: {
          ...SETUP_REPLY.setup,
          grain: "centre",
          units: 0,
          win_number: 0,
          note: "No registration centres are loaded for Zimmerman yet.",
        },
      },
    });

    await walkToReview(user, { office: "MCA", ward: true });
    await user.click(await screen.findByRole("button", { name: "Create campaign" }));

    expect(
      await screen.findByText(/No registration centres are loaded for Zimmerman yet/),
    ).toBeInTheDocument();
  });

  it("shows the server's refusal rather than a blank screen", async () => {
    const user = userEvent.setup();
    start({
      "POST /campaigns/setup/": {
        status: 400,
        body: { detail: "A Constituency (MP) campaign needs its constituency set." },
      },
    });

    await walkToReview(user);
    await user.click(await screen.findByRole("button", { name: "Create campaign" }));

    expect(
      await screen.findByText("A Constituency (MP) campaign needs its constituency set."),
    ).toBeInTheDocument();
  });

  it("can step back without losing what was typed", async () => {
    const user = userEvent.setup();
    start();

    await user.type(screen.getByPlaceholderText(/Jane for Roysambu/), "Jane for Roysambu");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("button", { name: "Back" }));

    expect(screen.getByPlaceholderText(/Jane for Roysambu/)).toHaveValue("Jane for Roysambu");
  });
});

describe("previewing the units before anything is created", () => {
  const WARDS = [
    { id: "w1", name: "Zimmerman", registered_voters: 30701 },
    { id: "w2", name: "Githurai", registered_voters: 35899 },
  ];
  const CENTRES = [
    { id: "rc1", name: "Zimmerman Primary", registered_voters: 2500 },
    { id: "rc2", name: "Roysambu Social Hall", registered_voters: 1800 },
  ];

  it("lists the wards an MP campaign will target, with the register", async () => {
    const user = userEvent.setup();
    start({ "GET /wards/": WARDS });

    await walkToReview(user);

    expect(await screen.findByText("2 wards")).toBeInTheDocument();
    expect(screen.getByText("66,600 registered voters")).toBeInTheDocument();
    expect(screen.getByText("Zimmerman")).toBeInTheDocument();
    expect(screen.getByText("30,701")).toBeInTheDocument();
  });

  it("lists the registration centres an MCA campaign will target", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": CENTRES });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(await screen.findByText("2 registration centres")).toBeInTheDocument();
    expect(screen.getByText("Zimmerman Primary")).toBeInTheDocument();
    expect(screen.getByText("4,300 registered voters")).toBeInTheDocument();
  });

  it("asks for the centres by the chosen ward", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "GET /centres/": CENTRES });

    await walkToReview(user, { office: "MCA", ward: true });

    await waitFor(() => expect(calls.some((c) => c.path === "/centres/?ward=w1")).toBe(true));
  });

  it("asks for every ward in the county for a county-wide seat", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "GET /wards/": WARDS });

    await walkToReview(user, { office: "Governor / Senator / Woman Rep" });

    await waitFor(() => expect(calls.some((c) => c.path === "/wards/?county=cty1")).toBe(true));
  });

  it("says so when a ward has no centres loaded, rather than looking ready", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": [] });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(await screen.findByText("No registration centres loaded")).toBeInTheDocument();
    expect(screen.getByText(/nothing to target until they are imported/)).toBeInTheDocument();
  });

  it("still lets the campaign be created when there are no centres", async () => {
    /* The campaign is real; only its targets are waiting on data. */
    const user = userEvent.setup();
    start({ "GET /centres/": [] });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(await screen.findByRole("button", { name: "Create campaign" })).toBeEnabled();
  });

  it("names the unit registration centre, not polling station", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": CENTRES });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(await screen.findByText(/registration centre in your ward/)).toBeInTheDocument();
    expect(screen.queryByText(/polling station/)).toBeNull();
  });
});
