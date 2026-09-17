import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import Onboarding from "../src/components/Onboarding";
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

    await user.type(
      screen.getByPlaceholderText(/Jane for Roysambu/),
      "Jane for Roysambu",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("MCA")).toBeInTheDocument();
    expect(screen.getByText("MP")).toBeInTheDocument();
    expect(
      screen.getByText("Governor / Senator / Woman Rep"),
    ).toBeInTheDocument();
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
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

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
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText("YOUR CAMPAIGN IS SET UP"),
    ).toBeInTheDocument();
    expect(screen.getByText("46,136")).toBeInTheDocument();
    expect(screen.getByText(/153,771 registered voters/)).toBeInTheDocument();
  });

  it("passes the setup on to the dashboard", async () => {
    const user = userEvent.setup();
    const { onDone } = start({ "POST /campaigns/setup/": SETUP_REPLY });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );
    await user.click(
      await screen.findByRole("button", { name: /Go to my dashboard/ }),
    );

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
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText(
        /No registration centres are loaded for Zimmerman yet/,
      ),
    ).toBeInTheDocument();
  });

  it("shows the server's refusal rather than a blank screen", async () => {
    const user = userEvent.setup();
    start({
      "POST /campaigns/setup/": {
        status: 400,
        body: {
          detail: "A Constituency (MP) campaign needs its constituency set.",
        },
      },
    });

    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText(
        "A Constituency (MP) campaign needs its constituency set.",
      ),
    ).toBeInTheDocument();
  });

  it("can step back without losing what was typed", async () => {
    const user = userEvent.setup();
    start();

    await user.type(
      screen.getByPlaceholderText(/Jane for Roysambu/),
      "Jane for Roysambu",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("button", { name: "Back" }));

    expect(screen.getByPlaceholderText(/Jane for Roysambu/)).toHaveValue(
      "Jane for Roysambu",
    );
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

    expect(
      await screen.findByText("2 registration centres"),
    ).toBeInTheDocument();
    expect(screen.getByText("Zimmerman Primary")).toBeInTheDocument();
    expect(screen.getByText("4,300 registered voters")).toBeInTheDocument();
  });

  it("asks for the centres by the chosen ward", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "GET /centres/": CENTRES });

    await walkToReview(user, { office: "MCA", ward: true });

    await waitFor(() =>
      expect(calls.some((c) => c.path === "/centres/?ward=w1")).toBe(true),
    );
  });

  it("asks for every ward in the county for a county-wide seat", async () => {
    const user = userEvent.setup();
    const { calls } = start({ "GET /wards/": WARDS });

    await walkToReview(user, { office: "Governor / Senator / Woman Rep" });

    await waitFor(() =>
      expect(calls.some((c) => c.path === "/wards/?county=cty1")).toBe(true),
    );
  });

  it("says so when a ward has no centres loaded, rather than looking ready", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": [] });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(
      await screen.findByText("No registration centres loaded"),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/nothing to target until they are imported/),
    ).toBeInTheDocument();
  });

  it("still lets the campaign be created when there are no centres", async () => {
    /* The campaign is real; only its targets are waiting on data. */
    const user = userEvent.setup();
    start({ "GET /centres/": [] });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(
      await screen.findByRole("button", { name: "Create campaign" }),
    ).toBeEnabled();
  });

  it("names the unit registration centre, not polling station", async () => {
    const user = userEvent.setup();
    start({ "GET /centres/": CENTRES });

    await walkToReview(user, { office: "MCA", ward: true });

    expect(
      await screen.findByText(/registration centre in your ward/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/polling station/)).toBeNull();
  });
});

describe("adding the team once the campaign exists", () => {
  const CREATED = {
    id: "u9",
    username: "amina",
    full_name: "Amina Kariuki",
    role: "manager",
    phone: "",
    password: fakeSecret(),
    mobilizer: null,
    ward_name: null,
  };

  async function reachTeamStep(user, routes = {}) {
    const started = start({ "POST /campaigns/setup/": SETUP_REPLY, ...routes });
    await walkToReview(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );
    await screen.findByText("YOUR CAMPAIGN IS SET UP");
    return started;
  }

  it("offers the team step on the same screen as the win number", async () => {
    const user = userEvent.setup();
    await reachTeamStep(user);

    expect(screen.getByText("Add your team")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Campaign manager" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Mobilizer" }),
    ).toBeInTheDocument();
  });

  it("creates a campaign manager on this campaign, not on an empty app", async () => {
    const user = userEvent.setup();
    const { calls } = await reachTeamStep(user, { "POST /users/": CREATED });

    await user.type(screen.getByPlaceholderText("amina"), "Amina");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/users/");
      expect(posted.body.username).toBe("amina");
      expect(posted.body.role).toBe("manager");
      expect(posted.body.campaign).toBe("c1");
      expect(posted.body.ward).toBeUndefined();
    });
  });

  it("puts a mobilizer on the campaign and a ward", async () => {
    const user = userEvent.setup();
    const { calls } = await reachTeamStep(user, {
      "POST /users/": { ...CREATED, role: "mobilizer", ward_name: "Zimmerman" },
      "GET /wards/": [
        { id: "w1", name: "Zimmerman", registered_voters: 30701 },
      ],
    });

    await user.click(screen.getByRole("button", { name: "Mobilizer" }));
    await user.type(screen.getByPlaceholderText("amina"), "juma");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/users/");
      expect(posted.body.role).toBe("mobilizer");
      expect(posted.body.campaign).toBe("c1");
      expect(posted.body.ward).toBe("w1");
    });
  });

  it("shows each password once, and says so", async () => {
    const user = userEvent.setup();
    await reachTeamStep(user, { "POST /users/": CREATED });

    await user.type(screen.getByPlaceholderText("amina"), "Amina");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));

    expect(await screen.findByText(CREATED.password)).toBeInTheDocument();
    expect(screen.getByText("Write these down now")).toBeInTheDocument();
    expect(screen.getByText("shown once")).toBeInTheDocument();
  });

  it("clears the form so the next person can be added", async () => {
    const user = userEvent.setup();
    await reachTeamStep(user, { "POST /users/": CREATED });

    await user.type(screen.getByPlaceholderText("amina"), "Amina");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));
    await screen.findByText(CREATED.password);

    expect(screen.getByPlaceholderText("amina")).toHaveValue("");
  });

  it("will not add anyone without a usable username", async () => {
    const user = userEvent.setup();
    await reachTeamStep(user);

    expect(
      screen.getByRole("button", { name: "Add to the team" }),
    ).toBeDisabled();
    await user.type(screen.getByPlaceholderText("amina"), "ab");
    expect(
      screen.getByRole("button", { name: "Add to the team" }),
    ).toBeDisabled();
  });

  it("shows the server's refusal", async () => {
    const user = userEvent.setup();
    await reachTeamStep(user, {
      "POST /users/": {
        status: 400,
        body: { detail: "The username amina is already taken." },
      },
    });

    await user.type(screen.getByPlaceholderText("amina"), "amina");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));

    expect(
      await screen.findByText("The username amina is already taken."),
    ).toBeInTheDocument();
  });

  it("still lets the campaign owner skip straight to the dashboard", async () => {
    const user = userEvent.setup();
    const { onDone } = await reachTeamStep(user);

    await user.click(
      screen.getByRole("button", { name: /Go to my dashboard/ }),
    );

    expect(onDone).toHaveBeenCalled();
  });
});

describe("a manager setting up for an aspirant", () => {
  const REPLY_WITH_LOGIN = {
    ...SETUP_REPLY,
    candidate_login: {
      id: "a2",
      username: "peter",
      full_name: "Peter Kimani",
      password: fakeSecret(),
    },
  };

  function startAsManager(routes = {}) {
    signIn("manager");
    const calls = stubApi({ ...GEOGRAPHY, "GET /users/": [], ...routes });
    const onDone = vi.fn();
    return { calls, onDone, ...renderApp(<Onboarding onDone={onDone} />) };
  }

  async function walk(user) {
    await user.type(await screen.findByPlaceholderText("jane"), "peter");
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
  }

  it("asks who the campaign is for, before anything else", async () => {
    startAsManager();
    expect(
      await screen.findByText(/Who are you running this campaign for/),
    ).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 5/)).toBeInTheDocument();
  });

  it("gives the candidate four steps, not five", async () => {
    signIn("candidate");
    stubApi(GEOGRAPHY);
    renderApp(<Onboarding onDone={vi.fn()} />);

    expect(await screen.findByText(/step 1 of 4/)).toBeInTheDocument();
    expect(
      screen.queryByText(/Who are you running this campaign for/),
    ).toBeNull();
  });

  it("will not move on until the aspirant has a usable username", async () => {
    const user = userEvent.setup();
    startAsManager();

    await user.type(await screen.findByPlaceholderText("jane"), "pe");

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  it("sends the aspirant's name, email and phone with the campaign", async () => {
    const user = userEvent.setup();
    const { calls } = startAsManager({
      "POST /campaigns/setup/": REPLY_WITH_LOGIN,
    });

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.type(
      screen.getByPlaceholderText("jane@example.com"),
      "peter@example.com",
    );
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

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/campaigns/setup/");
      expect(posted.body).toMatchObject({
        title: "Peter for Roysambu",
        office_level: "constituency",
        constituency: "k1",
        new_candidate: {
          username: "peter",
          email: "peter@example.com",
          phone: "0712345678",
        },
      });
      expect(posted.body.candidate).toBeUndefined();
    });
  });

  it("shows the new aspirant's password once", async () => {
    const user = userEvent.setup();
    startAsManager({ "POST /campaigns/setup/": REPLY_WITH_LOGIN });

    await walk(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText(REPLY_WITH_LOGIN.candidate_login.password),
    ).toBeInTheDocument();
    expect(screen.getByText(/shown once/)).toBeInTheDocument();
  });

  it("keeps the campaign name when stepping back from the seat", async () => {
    const user = userEvent.setup();
    startAsManager();

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.type(
      await screen.findByPlaceholderText(/Jane for Roysambu/),
      "Peter",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByRole("button", { name: "Back" }));

    expect(await screen.findByPlaceholderText(/Jane for Roysambu/)).toHaveValue(
      "Peter",
    );
  });

  it("can step back from the campaign name to change the aspirant", async () => {
    const user = userEvent.setup();
    startAsManager();

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(await screen.findByText("Campaign name")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Back" }));

    expect(
      await screen.findByText(/Who are you running this campaign for/),
    ).toBeInTheDocument();
    expect(screen.getByText(/step 1 of 5/)).toBeInTheDocument();
    expect(screen.getByPlaceholderText("jane")).toHaveValue("peter");
  });

  it("does not offer Back on the candidate's first step", async () => {
    const user = userEvent.setup();
    signIn("candidate");
    stubApi(GEOGRAPHY);
    renderApp(<Onboarding onDone={vi.fn()} />);

    await user.type(
      await screen.findByPlaceholderText(/Jane for Roysambu/),
      "Jane",
    );

    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
  });

  it("shows the server's refusal", async () => {
    const user = userEvent.setup();
    startAsManager({
      "POST /campaigns/setup/": {
        status: 400,
        body: { detail: "peter is already taken." },
      },
    });

    await walk(user);
    await user.click(
      await screen.findByRole("button", { name: "Create campaign" }),
    );

    expect(
      await screen.findByText("peter is already taken."),
    ).toBeInTheDocument();
  });
});

describe("a manager with no aspirants of their own yet", () => {
  function startWithNoAspirants(routes = {}) {
    signIn("manager");
    const calls = stubApi({ ...GEOGRAPHY, "GET /users/": [], ...routes });
    const onDone = vi.fn();
    return { calls, onDone, ...renderApp(<Onboarding onDone={onDone} />) };
  }

  it("goes straight to naming a new aspirant, with no picker to choose from", async () => {
    startWithNoAspirants();

    expect(
      await screen.findByText(/Who are you running this campaign for/),
    ).toBeInTheDocument();
    expect(await screen.findByPlaceholderText("jane")).toBeInTheDocument();
    expect(screen.queryByText("An aspirant already here")).toBeNull();
    expect(screen.queryByRole("combobox")).toBeNull();
  });

  it("lets the manager past the step once the aspirant is named", async () => {
    const user = userEvent.setup();
    startWithNoAspirants();

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.click(screen.getByRole("button", { name: "Next" }));

    expect(await screen.findByText("Campaign name")).toBeInTheDocument();
  });

  it("keeps the manager on the step until the aspirant has a usable username", async () => {
    const user = userEvent.setup();
    startWithNoAspirants();

    await user.type(await screen.findByPlaceholderText("jane"), "pe");

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

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
      office_level: "constituency",
      constituency: "k1",
      new_candidate: { username: "peter", phone: "0712345678" },
    });
    expect(posted.body.candidate).toBeUndefined();
    expect(await screen.findByText(issued)).toBeInTheDocument();
  });
});

// Creating a login for somebody else is the most consequential thing this flow
// does, so the review screen has to say it is about to happen.
describe("the review screen says who the campaign is for", () => {
  async function reachReview(user, routes = {}) {
    signIn("manager");
    const calls = stubApi({ ...GEOGRAPHY, "GET /users/": [], ...routes });
    renderApp(<Onboarding onDone={vi.fn()} />);

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
    await user.type(screen.getAllByRole("textbox")[0], "Peter");
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
    return calls;
  }

  it("warns that a new login is about to be created, and for whom", async () => {
    const user = userEvent.setup();
    await reachReview(user);

    expect(
      await screen.findByText(/creates a new login for/),
    ).toBeInTheDocument();
    expect(screen.getByText("Peter")).toBeInTheDocument();
    expect(screen.getByText(/password is shown once/)).toBeInTheDocument();
  });

  it("says nothing about an aspirant when the candidate sets their own up", async () => {
    const user = userEvent.setup();
    signIn("candidate");
    stubApi(GEOGRAPHY);
    renderApp(<Onboarding onDone={vi.fn()} />);

    await user.type(
      await screen.findByPlaceholderText(/Jane for Roysambu/),
      "Jane for Roysambu",
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

    expect(await screen.findByText(/We'll pull in every/)).toBeInTheDocument();
    expect(screen.queryByText(/creates a new login/)).toBeNull();
    expect(screen.queryByText(/already has a login/)).toBeNull();
  });
});

// The success screen is shared by both flows, and its copy was written for a
// candidate. A manager's campaign already has a manager: them.
describe("the team step after a manager sets a campaign up", () => {
  async function finishAsManager() {
    const user = userEvent.setup();
    signIn("manager");
    const calls = stubApi({
      ...GEOGRAPHY,
      "GET /users/": [],
      "POST /campaigns/setup/": SETUP_REPLY,
    });
    renderApp(<Onboarding onDone={vi.fn()} />);

    await user.type(await screen.findByPlaceholderText("jane"), "peter");
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
    await screen.findByText("Add your team");
    return { user, calls };
  }

  it("does not tell the manager they are the candidate", async () => {
    await finishAsManager();

    expect(screen.getByText(/You run this campaign/)).toBeInTheDocument();
    expect(screen.queryByText(/You are the candidate/)).toBeNull();
  });

  it("offers only mobilizers, since the campaign already has its manager", async () => {
    await finishAsManager();

    expect(
      screen.getByRole("button", { name: "Mobilizer" }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: "Campaign manager" }),
    ).toBeNull();
  });

  it("adds a mobilizer rather than defaulting to a manager the API refuses", async () => {
    const { user, calls } = await finishAsManager();

    await user.type(screen.getByPlaceholderText("amina"), "wanjiku");
    await user.click(screen.getByRole("button", { name: "Add to the team" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.path === "/users/");
      expect(posted.body.role).toBe("mobilizer");
      expect(posted.body.campaign).toBe("c1");
    });
  });
});

// A lookup that fails is not the same as "nobody is here", and the difference
// decides whether a new login gets created.
describe("when the aspirant lookup fails", () => {
  it("says so instead of silently offering the new-aspirant form", async () => {
    signIn("manager");
    stubApi({
      ...GEOGRAPHY,
      "GET /users/": { status: 500, body: { detail: "Database is down." } },
    });
    renderApp(<Onboarding onDone={vi.fn()} />);

    expect(await screen.findByText(/Database is down./)).toBeInTheDocument();
    expect(screen.queryByPlaceholderText("jane")).toBeNull();
  });

  it("will not let the manager past the step", async () => {
    signIn("manager");
    stubApi({
      ...GEOGRAPHY,
      "GET /users/": { status: 500, body: { detail: "Database is down." } },
    });
    renderApp(<Onboarding onDone={vi.fn()} />);

    await screen.findByText(/Database is down./);

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
});

describe("a manager who already set an aspirant up", () => {
  const KNOWN = [
    {
      id: "u-jane",
      username: "jane",
      full_name: "Jane Wanjiku",
      role: "candidate",
    },
    {
      id: "u-peter",
      username: "peter",
      full_name: "Peter Kim",
      role: "candidate",
    },
  ];

  function startWithAspirants(routes = {}) {
    signIn("manager");
    const calls = stubApi({ ...GEOGRAPHY, "GET /users/": KNOWN, ...routes });
    const onDone = vi.fn();
    return { calls, onDone, ...renderApp(<Onboarding onDone={onDone} />) };
  }

  it("offers the aspirants it already has, rather than only a blank form", async () => {
    startWithAspirants();

    expect(
      await screen.findByText("An aspirant already here"),
    ).toBeInTheDocument();
    const options = [...(await screen.findByRole("combobox")).options].map(
      (o) => o.value,
    );
    expect(options).toEqual(["", "u-jane", "u-peter"]);
  });

  it("sends the chosen aspirant instead of creating a second login for them", async () => {
    const user = userEvent.setup();
    const { calls } = startWithAspirants({
      "POST /campaigns/setup/": SETUP_REPLY,
    });

    await user.selectOptions(await screen.findByRole("combobox"), "u-jane");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await walkToReview(user);
    await user.click(screen.getByRole("button", { name: /Create/ }));

    await waitFor(() => {
      const sent = calls.find((c) => c.path === "/campaigns/setup/");
      expect(sent.body.candidate).toBe("u-jane");
      expect(sent.body.new_candidate).toBeUndefined();
    });
  });

  it("still creates a login when the manager fills the form instead", async () => {
    const user = userEvent.setup();
    const { calls } = startWithAspirants({
      "POST /campaigns/setup/": SETUP_REPLY,
    });

    await user.type(await screen.findByPlaceholderText("jane"), "brandnew");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await walkToReview(user);
    await user.click(screen.getByRole("button", { name: /Create/ }));

    await waitFor(() => {
      const sent = calls.find((c) => c.path === "/campaigns/setup/");
      expect(sent.body.new_candidate.username).toBe("brandnew");
      expect(sent.body.candidate).toBeUndefined();
    });
  });

  it("hides the new-aspirant form once one is chosen", async () => {
    const user = userEvent.setup();
    startWithAspirants();

    expect(await screen.findByPlaceholderText("jane")).toBeInTheDocument();
    await user.selectOptions(await screen.findByRole("combobox"), "u-peter");

    expect(screen.queryByPlaceholderText("jane")).toBeNull();
    expect(
      screen.getByText("They keep the login they already have."),
    ).toBeInTheDocument();
  });

  it("says the campaign is theirs, not that a login is about to be made", async () => {
    const user = userEvent.setup();
    startWithAspirants();

    await user.selectOptions(await screen.findByRole("combobox"), "u-jane");
    await user.click(screen.getByRole("button", { name: "Next" }));
    await walkToReview(user);

    expect(
      await screen.findByText(/signs in with the login they already have/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/This creates a new login/)).toBeNull();
  });

  it("lets the choice be undone, putting the form back", async () => {
    const user = userEvent.setup();
    startWithAspirants();

    await user.selectOptions(await screen.findByRole("combobox"), "u-jane");
    await user.selectOptions(screen.getByRole("combobox"), "");

    expect(await screen.findByPlaceholderText("jane")).toBeInTheDocument();
  });
});

describe("the username the server will accept", () => {
  it("keeps the manager on the step until the username is a shape the API takes", async () => {
    const user = userEvent.setup();
    signIn("manager");
    stubApi({ ...GEOGRAPHY, "GET /users/": [] });
    renderApp(<Onboarding onDone={vi.fn()} />);

    const field = await screen.findByPlaceholderText("jane");
    await user.type(field, "jane doe");

    // The server takes ^[A-Za-z0-9._-]+$, so a space is refused on this step
    // rather than four steps later on the review screen.
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();

    await user.clear(field);
    await user.type(field, "jane.doe");
    expect(screen.getByRole("button", { name: "Next" })).toBeEnabled();
  });
});

describe("changing the seat after the area is picked", () => {
  it("keeps the area when the seat already chosen is clicked again", async () => {
    const user = userEvent.setup();
    start();

    await user.type(
      screen.getByPlaceholderText(/Jane for Roysambu/),
      "Jane for Roysambu",
    );
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(await screen.findByText("MP", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.selectOptions(
      (await screen.findAllByRole("combobox"))[0],
      "cty1",
    );
    await user.selectOptions((await screen.findAllByRole("combobox"))[1], "k1");

    await user.click(screen.getByRole("button", { name: "Back" }));
    await user.click(await screen.findByText("MP", { selector: "div" }));
    await user.click(screen.getByRole("button", { name: "Next" }));

    const selects = await screen.findAllByRole("combobox");
    expect(selects[1].value).toBe("k1");
  });
});
