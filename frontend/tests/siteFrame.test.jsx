/** The website frame's news sign-up, and the demo Contribute page. */
import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { PARTY, renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const SITE = { ...PARTY, subscribe_consent_wording: "I agree to party news." };

describe("the website frame", () => {
  it("signs a contact up with consent and hands back its unsubscribe link", async () => {
    const calls = stubApi({
      "GET /party/": SITE,
      "GET /party/posts/": [],
      "POST /party/subscribe/": { message: "Thank you.", unsubscribe_url: "/unsubscribe/abc" },
    });
    renderApp(<AppRoutes />, { path: "/about" });
    const user = userEvent.setup();

    await user.type(await screen.findByRole("textbox", { name: "Phone or email" }), "0712345678");
    await user.click(screen.getByRole("checkbox", { name: /I agree to party news/ }));
    await user.click(screen.getByRole("button", { name: "Subscribe" }));

    expect(await screen.findByRole("link", { name: "Keep this unsubscribe link" })).toHaveAttribute("href", "/unsubscribe/abc");
    expect(calls.find((c) => c.method === "POST").body).toEqual({ contact: "0712345678", consent_given: true });
  });

  it("answers a contribution with the demo message", async () => {
    stubApi({
      "GET /party/": SITE,
      "POST /party/contribute/": { demo: true, message: "No money moved." },
    });
    renderApp(<AppRoutes />, { path: "/contribute" });
    const user = userEvent.setup();

    await user.type(await screen.findByRole("textbox", { name: "Full name" }), "Ama Otieno");
    await user.type(screen.getByRole("textbox", { name: "M-Pesa phone number" }), "0712345678");
    await user.click(screen.getByRole("checkbox", { name: /my own money/ }));
    await user.click(screen.getByRole("button", { name: /^Give KES/ }));

    expect(await screen.findByText("No money moved.")).toBeInTheDocument();
    expect(screen.getByText("Demo")).toBeInTheDocument();
  });
});
