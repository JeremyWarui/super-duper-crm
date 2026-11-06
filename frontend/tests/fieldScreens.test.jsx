import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import { TBody, TD, TH, THead, TR, Table } from "../src/components/ui/table";
import { useAuth } from "../src/store/auth";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

/** Stubs the API, with POSTs failing as a dropped connection does while `offline.on` is set. */
function stubField(routes) {
  const calls = stubApi(dashboardRoutes(routes));
  const served = globalThis.fetch;
  const offline = { on: false };
  vi.stubGlobal("fetch", vi.fn((url, options = {}) => (
    offline.on && options.method === "POST" ? Promise.reject(new TypeError("Failed to fetch")) : served(url, options)
  )));
  return { calls, offline };
}

const posts = (calls, path) => calls.filter((c) => c.method === "POST" && c.path === path);

describe("registering a supporter in the field", () => {
  it("keeps what was typed through a reload", async () => {
    signIn("mobilizer");
    stubField({});
    const user = userEvent.setup();
    const first = renderApp(<App />, { path: "/campaign/register" });
    await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
    await user.click(screen.getByRole("button", { name: "Undecided" }));
    first.unmount();

    renderApp(<App />, { path: "/campaign/register" });

    expect(await screen.findByRole("textbox", { name: "Full name" })).toHaveValue("Wanjiku Njeri");
    expect(screen.getByRole("button", { name: "Undecided" })).toHaveAttribute("aria-pressed", "true");
  });

  it("keeps the entry when the network drops, and sends it again on Try again", async () => {
    signIn("mobilizer");
    const { calls, offline } = stubField({ "POST /supporters/": { id: "s1" } });
    const user = userEvent.setup();
    renderApp(<App />, { path: "/campaign/register" });
    await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
    await user.click(screen.getByRole("checkbox"));
    offline.on = true;

    await user.click(screen.getByRole("button", { name: "Register supporter" }));
    expect(await screen.findByText(/Not sent: no network/)).toBeInTheDocument();
    expect(screen.getByRole("textbox", { name: "Full name" })).toHaveValue("Wanjiku Njeri");

    offline.on = false;
    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Registered.")).toBeInTheDocument();
    expect(posts(calls, "/supporters/").at(-1).body).toMatchObject({ full_name: "Wanjiku Njeri", consent_given: true });
    expect(Object.keys(localStorage).filter((k) => k.startsWith("draft:"))).toEqual([]);
  });

  it("keeps the entry for after sign-in when the session expired mid-send", async () => {
    signIn("mobilizer");
    stubField({ "POST /supporters/": { status: 401, body: {} } });
    const user = userEvent.setup();
    renderApp(<App />, { path: "/campaign/register" });
    await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
    await user.click(screen.getByRole("checkbox"));

    await user.click(screen.getByRole("button", { name: "Register supporter" }));

    await waitFor(() => expect(useAuth.getState().token).toBeNull());
    expect(JSON.parse(localStorage.getItem("draft:u1:register:c1"))).toMatchObject({ full_name: "Wanjiku Njeri" });
  });

});

describe("counting an event from My events", () => {
  it("leads with the next event and saves its counts, kept through a reload", async () => {
    signIn("mobilizer");
    const { calls } = stubField({ "POST /events/e1/record/": { id: "e1" } });
    const user = userEvent.setup();
    const first = renderApp(<App />, { path: "/campaign/myevents" });

    const next = await screen.findByRole("region", { name: "Next event" });
    expect(next).toHaveTextContent("Zimmerman town hall");
    for (let i = 0; i < 3; i += 1) await user.click(screen.getByRole("button", { name: "More reached" }));
    await user.click(screen.getByRole("button", { name: "More attended" }));
    first.unmount();

    renderApp(<App />, { path: "/campaign/myevents" });
    expect(await screen.findByRole("textbox", { name: "Reached" })).toHaveValue("3");
    await user.click(screen.getByRole("button", { name: "Save attendance" }));

    await waitFor(() => expect(posts(calls, "/events/e1/record/").at(-1)?.body).toEqual({ number_reached: 3, number_attended: 1 }));
  });
});

describe("drafts on a shared phone", () => {
  it("are removed at sign-out, and kept when the session only expires", () => {
    localStorage.setItem("draft:u1:register:c1", "{}");
    useAuth.getState().expire();
    expect(localStorage.getItem("draft:u1:register:c1")).toBe("{}");

    useAuth.getState().logout();
    expect(localStorage.getItem("draft:u1:register:c1")).toBeNull();
  });
});

describe("a stacked table", () => {
  it("labels each cell with its column and sets no fixed width on phones", () => {
    render(
      <Table stack minWidth={720}>
        <THead><TR><TH>Name</TH><TH>Phone</TH></TR></THead>
        <TBody><TR><TD>Juma</TD><TD>0700</TD></TR></TBody>
      </Table>,
    );

    expect(screen.getByText("0700")).toHaveAttribute("data-label", "Phone");
    expect(screen.getByText("Juma")).not.toHaveAttribute("data-label");
    expect(screen.getByRole("table").className).toContain("sm:min-w-(--table-min)");
    expect(screen.getByRole("table").className).not.toMatch(/(^|\s)min-w-/);
  });
});
