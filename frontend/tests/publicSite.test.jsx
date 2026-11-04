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

  it("shows a statement's reference and signed PDF", async () => {
    stubApi({
      ...ROUTES,
      "GET /party/posts/s1/": post("s1", "news", "Statement on prices", {
        label: "statement",
        author: "Grace Chebet, Secretary General",
        reference: "PP/ST/014/2026",
        pdf_url: "https://example.com/statement.pdf",
        read_minutes: 1,
      }),
    });
    renderApp(<AppRoutes />, { path: "/news/s1" });

    const record = within(await screen.findByRole("region", { name: "Official record" }));
    expect(record.getByText("PP/ST/014/2026")).toBeInTheDocument();
    expect(record.getByRole("link", { name: "Download the signed statement (PDF)" })).toHaveAttribute(
      "href",
      "https://example.com/statement.pdf",
    );
  });

  it("shows the Watch row with YouTube's thumbnail and the video's length", async () => {
    stubApi({
      ...ROUTES,
      "GET /party/videos/": [{ id: "v1", title: "Manifesto launch", url: "https://youtu.be/dQw4w9WgXcQ", thumbnail_url: "", duration: "4:15" }],
    });
    const { container } = renderApp(<AppRoutes />);

    const video = await screen.findByRole("link", { name: /Manifesto launch/ }, { timeout: 5000 });
    expect(video).toHaveAttribute("href", "https://youtu.be/dQw4w9WgXcQ");
    expect(video).toHaveTextContent("4:15");
    expect(container.querySelector('img[src="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"]')).not.toBeNull();
  });

  it("groups results by seat and says when they are demo results", async () => {
    const result = (id, seat, area, candidate, votes) => ({ id, seat, area, candidate, votes, declared_on: "2026-10-30", demo: true });
    stubApi({
      ...ROUTES,
      "GET /party/results/": [
        result("r1", "governor", "Nakuru County", "Mary Njeri", 1200),
        result("r2", "mca", "Kileleshwa", "Faith Muthoni", 80),
        result("r3", "mp", "Westlands", "Brian Ochieng", 900),
        result("r4", "mp", "Westlands", "Lucy Wairimu", 400),
      ],
    });
    renderApp(<AppRoutes />, { path: "/results" });

    expect(await screen.findByRole("note")).toHaveTextContent("Demo results");
    const races = screen.getAllByRole("article").map((a) => a.getAttribute("aria-label"));
    expect(races).toEqual(["MCA · Kileleshwa", "MP · Westlands", "Governor · Nakuru County"]);
    const westlands = within(screen.getByRole("article", { name: "MP · Westlands" }));
    expect(westlands.getAllByRole("listitem").map((li) => li.textContent)).toEqual(["✓ Brian Ochieng900 votes", "Lucy Wairimu400 votes"]);
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
      ["Events", "Events near you"],
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
