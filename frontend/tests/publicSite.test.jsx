/** The party's public site: what the pages show and how they link. */
import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { useAuth } from "../src/store/auth";
import { Carousel } from "../src/pages/public/Home";
import { renderApp, signIn, stubApi } from "./helpers";

const pdf = vi.hoisted(() => ({ load: null }));
vi.mock("@/lib/pdf", () => ({ loadPdf: (url) => pdf.load(url) }));

const fakePdf = () => ({
  getPage: async () => ({
    getViewport: ({ scale }) => ({ width: 600 * scale, height: 800 * scale }),
    render: () => ({ promise: Promise.resolve() }),
  }),
  destroy: () => {},
});

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
  "GET /site/": PARTY,
  "GET /party/": { consent_wording: "Umoja may keep my details." },
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

  it("offers Join the party to visitors but not to a signed-in member", async () => {
    stubApi(ROUTES);
    const visitor = renderApp(<AppRoutes />);
    const header = within(await screen.findByRole("banner"));
    expect(header.getByRole("link", { name: "Join the party" })).toBeInTheDocument();
    visitor.unmount();

    signIn(null);
    useAuth.setState({ user: { ...useAuth.getState().user, kind: "member", member_account: true } });
    renderApp(<AppRoutes />);
    expect(within(await screen.findByRole("banner")).queryByRole("link", { name: "Join the party" })).toBeNull();
    useAuth.getState().logout();
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

  it("shows a statement's reference and draws its signed PDF", async () => {
    const opened = [];
    pdf.load = async (url) => {
      opened.push(url);
      return fakePdf();
    };
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
    const viewer = within(screen.getByRole("region", { name: "The signed statement" }));
    expect(viewer.getByRole("img", { name: "The signed statement" })).toBeInTheDocument();
    expect(viewer.getByRole("link", { name: "Download the PDF" })).toHaveAttribute("href", "https://example.com/statement.pdf");
    expect(opened).toEqual(["https://example.com/statement.pdf"]);
  });

  it("keeps the download link when the statement's PDF cannot be drawn", async () => {
    pdf.load = async () => {
      throw new Error("bad PDF");
    };
    stubApi({ ...ROUTES, "GET /party/posts/s1/": post("s1", "news", "Statement", { label: "statement", pdf_url: "https://example.com/s.pdf" }) });
    renderApp(<AppRoutes />, { path: "/news/s1" });

    const viewer = within(await screen.findByRole("region", { name: "The signed statement" }));
    expect(await viewer.findByRole("alert")).toHaveTextContent("The PDF cannot be shown here.");
    expect(viewer.getByRole("link", { name: "Download the PDF" })).toHaveAttribute("href", "https://example.com/s.pdf");
  });

  it("draws a post's formatted text and drops anything that could run", async () => {
    stubApi({
      ...ROUTES,
      "GET /party/posts/n1/": post("n1", "news", "Party congress opens", {
        body: '<h2>What was agreed</h2><p>Delegates voted <strong>yes</strong>.</p><ul><li>Fees fall</li></ul><img src="x" onerror="window.hit=1"><script>window.hit=1</script>',
        read_minutes: 1,
      }),
    });
    renderApp(<AppRoutes />, { path: "/news/n1" });

    expect(await screen.findByRole("heading", { name: "What was agreed" })).toBeInTheDocument();
    expect(screen.getByText("yes").tagName).toBe("STRONG");
    expect(screen.getByRole("listitem")).toHaveTextContent("Fees fall");
    expect(document.querySelector("article script, article [onerror]")).toBeNull();
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
    stubApi({ ...ROUTES, "GET /candidates/": [], "GET /party/results/": [] });
    renderApp(<AppRoutes />);
    const user = userEvent.setup();
    await screen.findByRole("navigation", { name: "Main" });
    const menu = () => within(screen.getByRole("navigation", { name: "Main" }));
    const pages = [
      ["About", "About Umoja"],
      ["News", "News"],
      ["Events", "Events near you"],
      ["Candidates", "Our candidates"],
      ["Results", "Primary results"],
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
