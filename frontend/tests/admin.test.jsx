/** The admin console: what it shows, and who is shown it. */
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import { useCampaigns } from "../src/api/hooks";
import Admin from "../src/components/Admin";
import App from "../src/App";
import Login from "../src/components/Login";
import Onboarding from "../src/components/Onboarding";
import {
  ADMIN_CAMPAIGN,
  ADMIN_ORPHAN,
  ADMIN_TOTALS,
  ADMIN_USERS,
  API,
  TEST_TOKEN,
  dashboardRoutes,
  fakeSecret,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

const TOTALS = ADMIN_TOTALS;
const STAFFED = ADMIN_CAMPAIGN;
const ORPHAN = ADMIN_ORPHAN;
const USERS = ADMIN_USERS;

// Logins on no campaign, the only ones the console may put on one.
const FREE = {
  id: "u-peter",
  username: "peter",
  full_name: "Peter K",
  email: "",
  phone: "",
  role: "manager",
  is_active: true,
  is_superuser: false,
  last_login_at: null,
  campaign: null,
};
const FREE_BUT_DISABLED = {
  ...FREE,
  id: "u-otieno",
  username: "otieno",
  full_name: "Otieno O",
  is_active: false,
};

// The gate from src/main.jsx.
function SignedIn() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const needsSetup =
    campaigns.isSuccess && campaigns.data.length === 0 && role !== "mobilizer";
  return needsSetup ? (
    <Onboarding onDone={() => campaigns.refetch()} />
  ) : (
    <App />
  );
}

function Inside() {
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  return isSuperuser ? <Admin /> : <SignedIn />;
}

function Root() {
  const token = useAuth((s) => s.token);
  return token ? <Inside /> : <Login />;
}

function signInAsAdmin() {
  useAuth.setState({
    token: TEST_TOKEN,
    user: {
      id: "root",
      username: "root",
      full_name: "The Operator",
      role: "manager",
      is_superuser: true,
    },
  });
}

function adminRoutes(extra = {}) {
  return {
    "GET /admin/overview/": { totals: TOTALS, campaigns: [STAFFED, ORPHAN] },
    "GET /admin/users/": USERS,
    ...extra,
  };
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("who reaches the console", () => {
  it("sends a superuser to the console, not to campaign setup", async () => {
    signInAsAdmin();
    stubApi({
      ...adminRoutes(),
      ...dashboardRoutes({ "GET /campaigns/": [] }),
    });
    renderApp(<Root />);

    expect(
      await screen.findByText(/every campaign on this deployment/),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Set up your campaign/)).toBeNull();
  });

  it("never shows the console to a campaign manager", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<Root />);

    expect(
      await screen.findByText("VOTES TO WIN THE SEAT"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/every campaign on this deployment/)).toBeNull();
  });

  it("never shows the console to a candidate", async () => {
    signIn("candidate");
    stubApi(dashboardRoutes());
    renderApp(<Root />);

    await screen.findByText("VOTES TO WIN THE SEAT");
    expect(screen.queryByText(/every campaign on this deployment/)).toBeNull();
  });

  it("shows the server's refusal rather than an empty console", async () => {
    signInAsAdmin();
    stubApi({
      "GET /admin/overview/": {
        status: 403,
        body: { detail: "This is not yours to see." },
      },
      "GET /admin/users/": [],
    });
    renderApp(<Admin />);

    expect(
      await screen.findByText("This is not yours to see."),
    ).toBeInTheDocument();
  });
});

describe("what the console shows", () => {
  it("counts every table across the deployment", async () => {
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    expect(await screen.findByText("Campaigns")).toBeInTheDocument();
    expect(screen.getByText("41")).toBeInTheDocument();
    expect(screen.getByText("Supporters")).toBeInTheDocument();
  });

  it("lists every campaign with its team and its size", async () => {
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    expect(await screen.findByText("Jane for Roysambu")).toBeInTheDocument();
    expect(screen.getByText("Peter for Juja")).toBeInTheDocument();
    expect(screen.getByText("amina")).toBeInTheDocument();
    // The votes line is "<b>1,200</b> / 43,050 votes", so match across the nodes.
    expect(
      screen.getByText((_, el) => el?.textContent === "1,200 / 43,050 votes"),
    ).toBeInTheDocument();
  });

  it("calls out a campaign nobody is on, which nobody can see", async () => {
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    expect(
      await screen.findByText(/1 campaign with nobody on it/),
    ).toBeInTheDocument();
    expect(
      screen.getByText(/Nobody is on this campaign, so nobody can see it/),
    ).toBeInTheDocument();
  });

  it("lists every login, where it reaches, and whether it works", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));

    expect(await screen.findByText("superuser")).toBeInTheDocument();
    expect(screen.getByText("disabled")).toBeInTheDocument();
    expect(screen.getAllByText(/· Jane for Roysambu/)).toHaveLength(2);
    expect(screen.getByText(/on no campaign/)).toBeInTheDocument();
  });
});

describe("what the console can repair", () => {
  it("resets a password and shows it once", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const issued = fakeSecret();
    const calls = stubApi(
      adminRoutes({
        "POST /admin/users/u-jane/reset-password/": {
          username: "jane",
          password: issued,
        },
      }),
    );
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    const rows = await screen.findAllByRole("button", {
      name: "Reset password",
    });
    await user.click(rows[1]);
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    expect(await screen.findByText(issued)).toBeInTheDocument();
    expect(
      screen.getByText(/shown once, never fetchable again/),
    ).toBeInTheDocument();
    const posted = calls.find((c) => c.path.includes("reset-password"));
    expect(posted.method).toBe("POST");
  });

  it("disables a login", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      adminRoutes({
        "POST /admin/users/u-amina/active/": { ...USERS[0], is_active: false },
      }),
    );
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await user.click(
      (await screen.findAllByRole("button", { name: "Disable" }))[0],
    );
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    await waitFor(() => {
      const posted = calls.find((c) => c.path.includes("/active/"));
      expect(posted.body).toEqual({ active: false });
    });
  });

  it("will not let the operator disable themselves", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    const buttons = await screen.findAllByRole("button", { name: "Disable" });

    expect(buttons[buttons.length - 1]).toBeDisabled();
  });

  it("puts somebody onto a campaign nobody is on", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      adminRoutes({
        "GET /admin/users/": [...USERS, FREE],
        "POST /admin/campaigns/c2/members/": {
          ...ORPHAN,
          members: [
            {
              user_id: "u-peter",
              username: "peter",
              full_name: "Peter K",
              role: "manager",
            },
          ],
        },
      }),
    );
    renderApp(<Admin />);

    const add = await screen.findAllByRole("button", { name: "Add somebody" });
    await user.click(add[1]);
    await user.selectOptions(
      (await screen.findAllByRole("combobox"))[0],
      "u-peter",
    );
    await user.click(screen.getByRole("button", { name: "Put them on" }));

    await waitFor(() => {
      const posted = calls.find(
        (c) => c.path === "/admin/campaigns/c2/members/",
      );
      // No role: the server takes it from the login, so the console cannot
      // offer a place the person does not actually hold.
      expect(posted.body).toEqual({ user: "u-peter" });
    });
  });

  it("takes somebody off a campaign", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      // 204, the way the route really answers: no body to read.
      adminRoutes({
        "DELETE /admin/campaigns/c1/members/u-amina/": {
          status: 204,
          body: null,
        },
      }),
    );
    renderApp(<Admin />);

    const off = await screen.findAllByRole("button", { name: "Take off" });
    await user.click(off[1]);
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    await waitFor(() => {
      const sent = calls.find(
        (c) => c.path === "/admin/campaigns/c1/members/u-amina/",
      );
      expect(sent.method).toBe("DELETE");
    });
  });

  it("shows the server's refusal to take the candidate off", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(
      adminRoutes({
        "DELETE /admin/campaigns/c1/members/u-jane/": {
          status: 400,
          body: { detail: "That is the candidate this campaign is for." },
        },
      }),
    );
    renderApp(<Admin />);

    const off = await screen.findAllByRole("button", { name: "Take off" });
    await user.click(off[0]);
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    expect(
      await screen.findByText("That is the candidate this campaign is for."),
    ).toBeInTheDocument();
  });
});

describe("what the console refuses to lose", () => {
  it("keeps the new password when the row it came from has gone", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const issued = fakeSecret();
    let release;
    const held = new Promise((r) => {
      release = r;
    });
    const routes = adminRoutes();
    const fetchMock = vi.fn(async (url, options = {}) => {
      const method = options.method || "GET";
      const path = String(url).replace(API, "");
      if (path.includes("reset-password")) {
        await held;
        return {
          ok: true,
          status: 200,
          json: async () => ({ username: "jane", password: issued }),
        };
      }
      const match =
        routes[`${method} ${path}`] ??
        routes[`${method} ${path.split("?")[0]}`];
      return { ok: true, status: 200, json: async () => match ?? [] };
    });
    vi.stubGlobal("fetch", fetchMock);
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await user.click(
      (await screen.findAllByRole("button", { name: "Reset password" }))[1],
    );
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    // The row unmounts under the request, which is what drops a per-call
    // callback's result.
    await user.click(screen.getByRole("button", { name: /Campaigns/ }));
    release();

    expect(await screen.findByText(issued)).toBeInTheDocument();
  });

  it("shows one password per login, not a stack of stale ones", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    let nth = 0;
    const issued = [fakeSecret(), fakeSecret()];
    const routes = adminRoutes();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url, options = {}) => {
        const method = options.method || "GET";
        const path = String(url).replace(API, "");
        if (path.includes("reset-password")) {
          nth += 1;
          return {
            ok: true,
            status: 200,
            json: async () => ({ username: "jane", password: issued[nth - 1] }),
          };
        }
        const match =
          routes[`${method} ${path}`] ??
          routes[`${method} ${path.split("?")[0]}`];
        return { ok: true, status: 200, json: async () => match ?? [] };
      }),
    );
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    for (const _ of [1, 2]) {
      await user.click(
        (await screen.findAllByRole("button", { name: "Reset password" }))[1],
      );
      await user.click(await screen.findByRole("button", { name: "Yes" }));
      await waitFor(() =>
        expect(screen.getByText(issued[nth - 1])).toBeInTheDocument(),
      );
    }

    expect(screen.getByText(issued[1])).toBeInTheDocument();
    expect(screen.queryByText(issued[0])).toBeNull();
  });

  it("will not let the operator reset their own password", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    const buttons = await screen.findAllByRole("button", {
      name: "Reset password",
    });

    // root is the last row, and resetting it would sign the operator out
    // before the password reached the screen.
    expect(buttons[buttons.length - 1]).toBeDisabled();
  });

  it("asks before taking somebody off, and names them", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Take off" }))[1],
    );

    expect(
      screen.getByText("Take amina off Jane for Roysambu?"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });
});

describe("deleting a campaign", () => {
  const QUESTION =
    "Delete Jane for Roysambu with its 5 targets, 2 mobilizers, 4 events and 30 supporters, and the login of everyone on it except a superuser? This cannot be undone.";

  it("asks first, naming the campaign and what goes with it", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Delete campaign" }))[0],
    );

    expect(screen.getByText(QUESTION)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("deletes it once confirmed, and the card leaves with it", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const routes = adminRoutes();
    // Reading the DELETE stub is the delete: the overview answers without it after.
    Object.defineProperty(routes, "DELETE /admin/campaigns/c1/", {
      get() {
        routes["GET /admin/overview/"] = { totals: TOTALS, campaigns: [ORPHAN] };
        return { status: 204, body: null };
      },
    });
    const calls = stubApi(routes);
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Delete campaign" }))[0],
    );
    await user.click(screen.getByRole("button", { name: "Yes" }));

    await waitFor(() => {
      const sent = calls.find((c) => c.path === "/admin/campaigns/c1/");
      expect(sent.method).toBe("DELETE");
    });
    await waitFor(() =>
      expect(screen.queryByText("Jane for Roysambu")).toBeNull(),
    );
  });

  it("shows the server's refusal", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(
      adminRoutes({
        "DELETE /admin/campaigns/c1/": {
          status: 404,
          body: { detail: "No such campaign." },
        },
      }),
    );
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Delete campaign" }))[0],
    );
    await user.click(screen.getByRole("button", { name: "Yes" }));

    expect(await screen.findByText("No such campaign.")).toBeInTheDocument();
  });
});

describe("what the console says while it waits", () => {
  it("does not claim nobody matches while the logins are still loading", async () => {
    signInAsAdmin();
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url) => {
        const path = String(url).replace(API, "");
        if (path.startsWith("/admin/users")) return new Promise(() => {});
        return {
          ok: true,
          status: 200,
          json: async () => ({ totals: TOTALS, campaigns: [STAFFED, ORPHAN] }),
        };
      }),
    );
    renderApp(<Admin />);

    await userEvent
      .setup()
      .click(await screen.findByRole("button", { name: /Logins/ }));

    expect(await screen.findByText("Loading the logins…")).toBeInTheDocument();
    expect(screen.queryByText("Nobody matches that.")).toBeNull();
  });

  it("leaves a way out when the overview will not load", async () => {
    signInAsAdmin();
    stubApi({
      "GET /admin/overview/": {
        status: 403,
        body: { detail: "This is not yours to see." },
      },
      "GET /admin/users/": [],
    });
    renderApp(<Admin />);

    await screen.findByText("This is not yours to see.");
    expect(
      screen.getByRole("button", { name: "Sign out" }),
    ).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: "Try again" }),
    ).toBeInTheDocument();
  });
});

describe("who the console offers to staff a campaign with", () => {
  it("does not offer the operator, who reads every campaign already", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Add somebody" }))[1],
    );
    const options = [
      ...(await screen.findAllByRole("combobox"))[0].options,
    ].map((o) => o.value);

    expect(options).not.toContain("root");
  });

  it("does not offer a login that has been disabled", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(
      adminRoutes({ "GET /admin/users/": [...USERS, FREE, FREE_BUT_DISABLED] }),
    );
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Add somebody" }))[1],
    );
    const options = [
      ...(await screen.findAllByRole("combobox"))[0].options,
    ].map((o) => o.value);

    // otieno is disabled; staffing a campaign with them leaves it unmanned.
    expect(options).not.toContain("u-otieno");
    expect(options).toContain("u-peter");
  });

  it("does not offer a login already on a campaign, which belongs to that one", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes({ "GET /admin/users/": [...USERS, FREE] }));
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Add somebody" }))[1],
    );
    const options = [
      ...(await screen.findAllByRole("combobox"))[0].options,
    ].map((o) => o.value);

    expect(options).not.toContain("u-amina");
    expect(options).toEqual(["", "u-peter"]);
  });
});

describe("two resets at once", () => {
  /** A stub whose reset-password replies are released by hand, per user. */
  function heldResets(routes) {
    const gates = {};
    const release = (id, reply) => gates[id]?.(reply);
    const fetchMock = vi.fn(async (url, options = {}) => {
      const method = options.method || "GET";
      const path = String(url).replace(API, "");
      const reset = path.match(/^\/admin\/users\/([^/]+)\/reset-password\/$/);
      if (reset) {
        const reply = await new Promise((r) => {
          gates[reset[1]] = r;
        });
        return {
          ok: reply.status < 300,
          status: reply.status,
          json: async () => reply.body,
        };
      }
      const match =
        routes[`${method} ${path}`] ??
        routes[`${method} ${path.split("?")[0]}`];
      return { ok: true, status: 200, json: async () => match ?? [] };
    });
    vi.stubGlobal("fetch", fetchMock);
    return release;
  }

  async function resetRow(user, username) {
    const row = within(await screen.findByTestId(`login-${username}`));
    await user.click(row.getByRole("button", { name: "Reset password" }));
    await user.click(row.getByRole("button", { name: "Yes" }));
  }

  it("does not swallow one login's refusal because another reset started", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const release = heldResets(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await resetRow(user, "amina");
    await resetRow(user, "jane"); // while amina is still in flight

    const issued = fakeSecret();
    release("u-jane", {
      status: 200,
      body: { username: "jane", password: issued },
    });
    expect(await screen.findByText(issued)).toBeInTheDocument();

    release("u-amina", {
      status: 400,
      body: { detail: "That login is disabled." },
    });

    // The operator must not walk away believing both were rotated.
    expect(
      await screen.findByText("That login is disabled."),
    ).toBeInTheDocument();
  });

  it("keeps each row's own pending state while both are in flight", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const release = heldResets(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await resetRow(user, "amina");
    await resetRow(user, "jane");

    const working = await screen.findAllByRole("button", { name: "Working…" });
    expect(working).toHaveLength(2);
    expect(working.every((b) => b.disabled)).toBe(true);

    const issued = fakeSecret();
    release("u-amina", {
      status: 200,
      body: { username: "amina", password: issued },
    });
    await screen.findByText(issued);

    // jane is still going, and says so; amina is done and offers the button again.
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Working…" })).toHaveLength(
        1,
      ),
    );
  });

  it("does not carry a refusal across to another filter's list", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const release = heldResets(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await resetRow(user, "amina");
    release("u-amina", {
      status: 400,
      body: { detail: "That login is disabled." },
    });
    expect(
      await screen.findByText("That login is disabled."),
    ).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Aspirants" }));
    await user.click(screen.getByRole("button", { name: "Everyone" }));

    // Nothing was retried, so nothing should still be refusing.
    await waitFor(() =>
      expect(screen.queryByText("That login is disabled.")).toBeNull(),
    );
  });

  it("clears a row's old refusal when it is tried again", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const release = heldResets(adminRoutes());
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await resetRow(user, "amina");
    release("u-amina", {
      status: 400,
      body: { detail: "That login is disabled." },
    });
    expect(
      await screen.findByText("That login is disabled."),
    ).toBeInTheDocument();

    await resetRow(user, "amina");

    await waitFor(() =>
      expect(screen.queryByText("That login is disabled.")).toBeNull(),
    );
  });
});

describe("creating a login from the console", () => {
  async function openForm(user) {
    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    await user.click(
      await screen.findByRole("button", { name: "Add a login" }),
    );
  }

  it("creates a manager on a campaign and shows the password once", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const issued = fakeSecret();
    const calls = stubApi(
      adminRoutes({
        "POST /admin/users/": {
          id: "u-new",
          username: "newmgr",
          full_name: "New Manager",
          role: "manager",
          password: issued,
        },
      }),
    );
    renderApp(<Admin />);

    await openForm(user);
    await user.type(screen.getByPlaceholderText("jane.wanjiku"), "newmgr");
    await user.selectOptions(screen.getByLabelText(/Campaign/), "c1");
    await user.click(screen.getByRole("button", { name: "Create the login" }));

    expect(await screen.findByText(issued)).toBeInTheDocument();
    // GET /admin/users/ shares the path, so the method has to be matched too.
    const posted = calls.find(
      (c) => c.path === "/admin/users/" && c.method === "POST",
    );
    expect(posted.body.username).toBe("newmgr");
    expect(posted.body.role).toBe("manager");
    expect(posted.body.campaign).toBe("c1");
  });

  it("asks a mobilizer for a ward, from the campaign that was picked", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await openForm(user);
    await user.selectOptions(screen.getByLabelText("They are a"), "mobilizer");
    await user.selectOptions(screen.getByLabelText("Campaign"), "c1");

    const wards = [...screen.getByLabelText("Ward").options].map(
      (o) => o.textContent,
    );
    expect(wards).toEqual(["Choose a ward…", "Zimmerman", "Githurai"]);
  });

  it("will not create a mobilizer until a ward is chosen", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await openForm(user);
    await user.type(screen.getByPlaceholderText("jane.wanjiku"), "newboots");
    await user.selectOptions(screen.getByLabelText("They are a"), "mobilizer");
    await user.selectOptions(screen.getByLabelText("Campaign"), "c1");

    expect(
      screen.getByRole("button", { name: "Create the login" }),
    ).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Ward"), "w2");
    expect(
      screen.getByRole("button", { name: "Create the login" }),
    ).toBeEnabled();
  });

  it("does not offer an aspirant a campaign, because one is set up for them after", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await openForm(user);
    await user.selectOptions(screen.getByLabelText("They are a"), "candidate");

    expect(screen.queryByLabelText(/Campaign/)).toBeNull();
    expect(
      screen.getByText(/campaign is set up for them afterwards/),
    ).toBeInTheDocument();
  });

  it("refuses a username the server would refuse", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await openForm(user);
    const field = screen.getByPlaceholderText("jane.wanjiku");
    await user.type(field, "jane doe");

    expect(
      screen.getByRole("button", { name: "Create the login" }),
    ).toBeDisabled();

    await user.clear(field);
    await user.type(field, "jane.doe");
    expect(
      screen.getByRole("button", { name: "Create the login" }),
    ).toBeEnabled();
  });

  it("shows the server's refusal rather than pretending it worked", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(
      adminRoutes({
        "POST /admin/users/": {
          status: 400,
          body: { detail: "The username amina is already taken." },
        },
      }),
    );
    renderApp(<Admin />);

    await openForm(user);
    await user.type(screen.getByPlaceholderText("jane.wanjiku"), "amina");
    await user.click(screen.getByRole("button", { name: "Create the login" }));

    expect(
      await screen.findByText("The username amina is already taken."),
    ).toBeInTheDocument();
  });
});

describe("renaming a campaign", () => {
  it("renames it and sends only the new name", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      adminRoutes({
        "PATCH /admin/campaigns/c1/": {
          ...STAFFED,
          title: "Jane for Roysambu 2027",
        },
      }),
    );
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );
    const field = screen.getByLabelText("Campaign name");
    await user.clear(field);
    await user.type(field, "Jane for Roysambu 2027");
    await user.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => {
      const sent = calls.find((c) => c.path === "/admin/campaigns/c1/");
      expect(sent.method).toBe("PATCH");
      expect(sent.body).toEqual({ title: "Jane for Roysambu 2027" });
    });
  });

  it("starts from the name it already has", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );

    expect(screen.getByLabelText("Campaign name")).toHaveValue(
      "Jane for Roysambu",
    );
  });

  it("will not save an empty name", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );
    await user.clear(screen.getByLabelText("Campaign name"));

    expect(screen.getByRole("button", { name: "Save" })).toBeDisabled();
  });

  it("puts the old name back on cancel", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(adminRoutes());
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );
    await user.clear(screen.getByLabelText("Campaign name"));
    await user.type(screen.getByLabelText("Campaign name"), "Nope");
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(screen.getByText("Jane for Roysambu")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);

    // Reopening must not bring the abandoned text back.
    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );
    expect(screen.getByLabelText("Campaign name")).toHaveValue(
      "Jane for Roysambu",
    );
  });

  it("shows the server's refusal rather than the name it wanted", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    stubApi(
      adminRoutes({
        "PATCH /admin/campaigns/c1/": {
          status: 400,
          body: { detail: "A campaign needs a name." },
        },
      }),
    );
    renderApp(<Admin />);

    await user.click(
      (await screen.findAllByRole("button", { name: "Rename" }))[0],
    );
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(
      await screen.findByText("A campaign needs a name."),
    ).toBeInTheDocument();
  });
});
