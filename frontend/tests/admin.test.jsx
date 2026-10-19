/** The admin console: what it shows, and who is shown it. */
import { screen } from "@testing-library/react";
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

});
