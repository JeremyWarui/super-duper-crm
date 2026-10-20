import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import App from "../src/App";
import Join from "../src/components/Join";
import { dashboardRoutes, renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const PAGE = { campaign_title: "Jane for Roysambu", candidate_name: "Jane", event_title: "Zimmerman town hall", ward_name: "Zimmerman", open: true };

describe("signing up from an event's QR code", () => {
  it("sends the name, phone and consent, and thanks them", async () => {
    const calls = stubApi({ "GET /join/abc123/": PAGE, "POST /join/abc123/": { message: "Thank you, you're signed up." } });
    renderApp(<Join code="abc123" />);
    const user = userEvent.setup();

    await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Wanjiku Njeri");
    await user.type(screen.getByRole("textbox", { name: "Phone" }), "0712 345678");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: "Sign up" }));

    expect(await screen.findByText("Thank you, you're signed up.")).toBeInTheDocument();
    expect(calls.find((c) => c.method === "POST").body).toEqual({ full_name: "Wanjiku Njeri", phone: "0712 345678", consent_given: true });
  });

  it("shows the manager the event's sign-up link", async () => {
    signIn("manager");
    stubApi(dashboardRoutes());
    renderApp(<App />);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Events" }));
    await user.click(await screen.findByRole("button", { name: "Sign-up QR" }));

    await waitFor(() => expect(screen.getByText(/\/join\/zimmerman-hall$/)).toBeInTheDocument());
  });
});
