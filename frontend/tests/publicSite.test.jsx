/** The campaign's public site: what the pages show and how they link. */
import { act, fireEvent, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { Carousel } from "../src/pages/public/sections";
import { renderApp, stubApi } from "./helpers";

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

const SITE = {
  name: "Jane for Kasarani",
  short_name: "JK",
  logo_url: "",
  primary_colour: "#112233",
  secondary_colour: "#445566",
  contact_email: "info@jane.ke",
  contact_phone: "",
  address: "",
  social_links: {},
  volunteer_consent_wording: "Jane's campaign may contact me.",
};

const PAGE = {
  name: "Jane Wanjiku", seat: "mp", area: "Kasarani", photo_url: "", slogan: "", bio: "", priorities: [],
  volunteering_open: false, wards: [], consent_wording: "",
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
  "GET /site/": SITE,
  "GET /site/candidate/": PAGE,
  "GET /website/places/": [],
  "GET /website/posts/?kind=news&offset=0": [post("n1", "news", "Campaign launch opens")],
  "GET /website/posts/?kind=event&offset=0": [
    post("e1", "event", "Nakuru rally", { event_date: "2026-11-20", venue: "Afraha" }),
  ],
  "GET /website/slides/": ["Jobs for all", "Fair prices"].map((headline, i) => ({
    id: `s${i}`, headline, kicker: "", line: "", image_url: "", button_label: "", button_url: "",
  })),
};

describe("the public site", () => {
  it("shows the latest published news and the next events on the home page", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect((await screen.findAllByText("Campaign launch opens")).length).toBeGreaterThan(0);
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

  it("shows a statement's reference and draws its signed PDF", async () => {
    const opened = [];
    pdf.load = async (url) => {
      opened.push(url);
      return fakePdf();
    };
    stubApi({
      ...ROUTES,
      "GET /website/posts/s1/": post("s1", "news", "Statement on prices", {
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
    stubApi({ ...ROUTES, "GET /website/posts/s1/": post("s1", "news", "Statement", { label: "statement", pdf_url: "https://example.com/s.pdf" }) });
    renderApp(<AppRoutes />, { path: "/news/s1" });

    const viewer = within(await screen.findByRole("region", { name: "The signed statement" }));
    expect(await viewer.findByRole("alert")).toHaveTextContent("The PDF cannot be shown here.");
    expect(viewer.getByRole("link", { name: "Download the PDF" })).toHaveAttribute("href", "https://example.com/s.pdf");
  });

  it("draws a post's formatted text and drops anything that could run", async () => {
    stubApi({
      ...ROUTES,
      "GET /website/posts/n1/": post("n1", "news", "Campaign launch opens", {
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
      "GET /website/videos/": [{ id: "v1", title: "Manifesto launch", url: "https://youtu.be/dQw4w9WgXcQ", thumbnail_url: "", duration: "4:15" }],
    });
    const { container } = renderApp(<AppRoutes />);

    const video = await screen.findByRole("link", { name: /Manifesto launch/ }, { timeout: 5000 });
    expect(video).toHaveAttribute("href", "https://youtu.be/dQw4w9WgXcQ");
    expect(video).toHaveTextContent("4:15");
    expect(container.querySelector('img[src="https://img.youtube.com/vi/dQw4w9WgXcQ/hqdefault.jpg"]')).not.toBeNull();
  });

});
