/** The admin console: what it shows, and who is shown it. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useAuth } from "../src/store/auth";
import Admin from "../src/components/Admin";
import Root from "../src/Gate";
import {
  ADMIN_CAMPAIGN,
  ADMIN_ORPHAN,
  ADMIN_TOTALS,
  ADMIN_USERS,
  TEST_TOKEN,
  dashboardRoutes,
  renderApp,
  signIn,
  stubApi,
} from "./helpers";

const TOTALS = ADMIN_TOTALS;
const STAFFED = ADMIN_CAMPAIGN;
const ORPHAN = ADMIN_ORPHAN;
const USERS = ADMIN_USERS;

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
      "GET /site/": { name: "Jane for Kasarani" },
    });
    renderApp(<Root />);

    expect(
      within(await screen.findByRole("navigation", { name: "Breadcrumb" })).getByText("Console"),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Set up your campaign/)).toBeNull();
  });

  it("never shows the console to a campaign manager", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<Root />);

    expect(
      await screen.findByRole("region", { name: "Win number" }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Console" })).toBeNull();
  });
});

describe("what the console can repair", () => {
  it("emails a login a reset link and says it went", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      adminRoutes({
        "POST /admin/users/u-jane/reset-password/": { username: "jane", sent: "email" },
      }),
    );
    renderApp(<Admin />);

    await user.click(await screen.findByRole("button", { name: /Logins/ }));
    const rows = await screen.findAllByRole("button", {
      name: "Send reset link",
    });
    await user.click(rows[1]);
    await user.click(await screen.findByRole("button", { name: "Yes" }));

    expect(await screen.findByText("Link emailed")).toBeInTheDocument();
    const posted = calls.find((c) => c.path.includes("reset-password"));
    expect([posted.method, posted.body ?? null]).toEqual(["POST", null]);
  });
});

describe("changing a login's email", () => {
  it("saves the new email from the login's row", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(adminRoutes({
      "PUT /admin/users/u-amina/email/": { ...USERS[0], email: "amina.k@example.com" },
    }));
    renderApp(<Admin />);
    await user.click(await screen.findByRole("button", { name: /Logins/ }));

    await user.click(await screen.findByRole("button", { name: "Change email for amina" }));
    const field = screen.getByRole("textbox", { name: "Email for amina" });
    await user.clear(field);
    await user.type(field, "amina.k@example.com");
    await user.click(screen.getByRole("button", { name: "Save email" }));

    await vi.waitFor(() =>
      expect(calls.find((c) => c.method === "PUT").body).toEqual({ email: "amina.k@example.com" }),
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

  it("creates a manager on a campaign and says their invite was emailed", async () => {
    const user = userEvent.setup();
    signInAsAdmin();
    const calls = stubApi(
      adminRoutes({
        "POST /admin/users/": {
          id: "u-new",
          username: "newmgr",
          full_name: "New Manager",
          role: "manager",
          invite: "email",
        },
      }),
    );
    renderApp(<Admin />);

    await openForm(user);
    await user.type(screen.getByRole("textbox", { name: "Username" }), "newmgr");
    await user.type(screen.getByRole("textbox", { name: "Email" }), "newmgr@example.com");
    await user.selectOptions(screen.getByRole("combobox", { name: /^Campaign/ }), "c1");
    await user.click(screen.getByRole("button", { name: "Create the login" }));

    expect(await screen.findByText("Link emailed")).toBeInTheDocument();
    // GET /admin/users/ shares the path, so the method has to be matched too.
    const posted = calls.find(
      (c) => c.path === "/admin/users/" && c.method === "POST",
    );
    expect(posted.body.username).toBe("newmgr");
    expect(posted.body.role).toBe("manager");
    expect(posted.body.campaign).toBe("c1");
  });
});

describe("reference data imports", () => {
  it("checks a boundary file, shows what it would change, then imports it", async () => {
    signInAsAdmin();
    const report = (applied) => ({
      kind: "boundaries", rows: 2, applied, counts: { renamed: 1, retired: 1 },
      changes: [
        { level: "ward", code: "1391", change: "renamed", detail: "Githurai -> Githurai West" },
        { level: "ward", code: "1393", change: "retired", detail: "Zimmerman" },
      ],
    });
    const calls = stubApi(adminRoutes({ "GET /admin/imports/": [], "POST /admin/imports/boundaries/": report(false) }));
    renderApp(<Admin />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Areas and register" }));
    const card = screen.getByRole("region", { name: "Boundaries" });
    const csv = "county_code,county_name\n47,Nairobi City\n";
    await user.upload(within(card).getByLabelText("CSV file"), new File([csv], "nairobi.csv", { type: "text/csv" }));
    const checkFile = within(card).getByRole("button", { name: "Check file" });
    await vi.waitFor(() => expect(checkFile).toBeEnabled());
    await user.click(checkFile);

    expect(await within(card).findByText(/This file would make: 1 renamed, 1 retired/)).toBeInTheDocument();
    expect(within(card).getByText("Zimmerman")).toBeInTheDocument();
    const posts = () => calls.filter((c) => c.path === "/admin/imports/boundaries/");
    expect(posts()[0].body).toEqual({ filename: "nairobi.csv", csv, dry_run: true });

    await user.click(within(card).getByRole("button", { name: "Import boundaries" }));
    await vi.waitFor(() => expect(posts().at(-1).body.dry_run).toBe(false));
  });
});

describe("the console's health and audit", () => {
  const HEALTH = {
    version: "0.1.0",
    migration: { current: "backup_runs", head: "backup_runs", up_to_date: true },
    database: { reachable: true, detail: "", size_bytes: 52428800 },
    services: [
      { key: "email", label: "Email", mode: "practice", configured: false },
      { key: "sms", label: "SMS", mode: "console", configured: false },
    ],
    last_backup: null,
    disks: [{ label: "Uploads", path: "/srv/uploads", free_bytes: 10737418240, total_bytes: 21474836480 }],
  };

  it("shows a service with no key as not configured, and runs a practice payout", async () => {
    signInAsAdmin();
    const calls = stubApi(adminRoutes({
      "GET /admin/health/": HEALTH,
      "GET /admin/backups/": [],
      "POST /admin/test/payout/": { message: "Practice payout paid under PRACTICE-1; no money moved." },
    }));
    renderApp(<Admin />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Health" }));
    const services = await screen.findByRole("region", { name: "Outside services" });
    expect(within(services).getAllByText("Not configured")).toHaveLength(2);
    expect(screen.getByText(/Last backup:/)).toHaveTextContent("never");

    await user.type(within(services).getByRole("textbox", { name: /Make a practice payout/ }), "0712345678");
    await user.click(within(services).getByRole("button", { name: "Make a practice payout" }));

    expect(await within(services).findByText(/no money moved/)).toBeInTheDocument();
    expect(calls.find((c) => c.path === "/admin/test/payout/").body).toEqual({ phone: "0712345678" });
  });

  it("filters the audit trail by action and who", async () => {
    signInAsAdmin();
    const calls = stubApi(adminRoutes({
      "GET /admin/audit/": [{ id: "a1", created_at: "2026-11-06T10:00:00Z", actor_name: "root", action: "import.boundaries", subject_type: "import_run", detail: { rows: 133 } }],
    }));
    renderApp(<Admin />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Audit" }));
    await user.type(screen.getByRole("textbox", { name: /Action/ }), "import");
    await user.type(screen.getByRole("textbox", { name: "Who" }), "root");

    expect(await screen.findByText("import.boundaries")).toBeInTheDocument();
    const lastAudit = () => calls.filter((c) => c.path.startsWith("/admin/audit/")).at(-1).path;
    await vi.waitFor(() => expect(lastAudit()).toBe("/admin/audit/?action=import&actor=root&limit=50&offset=0"), { timeout: 5000 });
  });
});
