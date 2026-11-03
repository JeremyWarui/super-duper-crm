/** The party's public site: what the pages show and how they link. */
import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { Carousel } from "../src/pages/public/Home";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

const PARTY = {
  name: "Umoja Party",
  short_name: "Umoja",
  logo_url: "",
  primary_colour: "#112233",
  secondary_colour: "#445566",
  description: "One country.",
  contact_email: "info@umoja.ke",
  contact_phone: "",
  address: "",
  manifesto_text: "Jobs for the youth.",
  manifesto_url: "",
  social_links: {},
  consent_wording: "Umoja may keep my details.",
  volunteer_consent_wording: "Umoja may contact me.",
};

const post = (id, kind, title, extra = {}) => ({
  id,
  kind,
  title,
  body: "",
  image_url: "",
  event_date: null,
  venue: "",
  published_on: "2026-11-01",
  ...extra,
});

const ROUTES = {
  "GET /party/": PARTY,
  "GET /party/places/": [],
  "GET /party/posts/?kind=news&offset=0": [post("n1", "news", "Party congress opens")],
  "GET /party/posts/?kind=event&offset=0": [
    post("e1", "event", "Nakuru rally", { event_date: "2026-11-20", venue: "Afraha" }),
  ],
  "GET /party/slides/": ["Jobs for all", "Fair prices"].map((headline, i) => ({
    id: `s${i}`, headline, kicker: "", line: "", image_url: "", button_label: "", button_url: "",
  })),
  "GET /party/leaders/": [
    { id: "l2", name: "Juma Otieno", position: "Party Leader", bio: "", photo_url: "" },
    { id: "l1", name: "Amina Kariuki", position: "Secretary General", bio: "", photo_url: "" },
  ],
};

describe("the public site", () => {
  it("shows the latest published news and the next events on the home page", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect((await screen.findAllByText("Party congress opens")).length).toBeGreaterThan(0);
    expect(await screen.findByText("Nakuru rally")).toBeInTheDocument();
    expect(screen.getByText("Afraha")).toBeInTheDocument();
  });

  it("turns the carousel every six seconds until paused, and opens any slide", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    stubApi(ROUTES);
    renderApp(<Carousel />);
    const headline = () => screen.getByRole("heading", { level: 1 }).textContent;
    await screen.findByRole("button", { name: "Slide 2" });

    expect(headline()).toBe("Jobs for all");
    act(() => vi.advanceTimersByTime(6000));
    expect(headline()).toBe("Fair prices");
    fireEvent.click(screen.getByRole("button", { name: "Pause" }));
    act(() => vi.advanceTimersByTime(12000));
    expect(headline()).toBe("Fair prices");
    fireEvent.click(screen.getByRole("button", { name: "Slide 1" }));
    expect(headline()).toBe("Jobs for all");
  });

  it("lists the leaders in the order the server gives", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />, { path: "/leadership" });

    await screen.findByText("Amina Kariuki");
    const names = screen.getAllByText(/Amina Kariuki|Juma Otieno/).map((el) => el.textContent);

    expect(names).toEqual(["Juma Otieno", "Amina Kariuki"]);
  });

  it("reaches every page from the menu", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);
    const user = userEvent.setup();
    const menu = () => within(screen.getByRole("navigation", { name: "Main" }));
    const pages = [
      ["About", "About Umoja"],
      ["Leadership", "Leadership"],
      ["Manifesto", "Manifesto"],
      ["News", "News"],
      ["Events", "Events"],
    ];

    for (const [link, heading] of pages) {
      await user.click(menu().getByRole("link", { name: link }));
      expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
      expect(menu().getByRole("link", { name: link })).toHaveAttribute("aria-current", "page");
    }
    await user.click(screen.getAllByRole("link", { name: /Umoja Party/ })[0]);
    expect(await screen.findByRole("heading", { level: 1, name: "Jobs for all" })).toBeInTheDocument();
    await user.click(screen.getAllByRole("link", { name: "Join the party" })[0]);
    expect(await screen.findByRole("textbox", { name: "First name" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });
});
