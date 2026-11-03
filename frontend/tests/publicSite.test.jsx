/** The party's public site: what the pages show and how they link. */
import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AppRoutes } from "../src/Gate";
import { renderApp, stubApi } from "./helpers";

afterEach(() => {
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
  "GET /party/leaders/": [
    { id: "l2", name: "Juma Otieno", position: "Party Leader", bio: "", photo_url: "" },
    { id: "l1", name: "Amina Kariuki", position: "Secretary General", bio: "", photo_url: "" },
  ],
};

describe("the public site", () => {
  it("shows the latest published news and the next events on the home page", async () => {
    stubApi(ROUTES);
    renderApp(<AppRoutes />);

    expect(await screen.findByRole("link", { name: "Party congress opens" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: "Nakuru rally" })).toBeInTheDocument();
    expect(screen.getByText("20 Nov 2026 · Afraha")).toBeInTheDocument();
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
    const menu = () => within(screen.getByRole("navigation", { name: "Site" }));
    const pages = [
      ["About", "About Umoja"],
      ["Leadership", "Leadership"],
      ["Manifesto", "Manifesto"],
      ["News", "News"],
      ["Events", "Events"],
      ["Home", "Umoja Party"],
    ];

    for (const [link, heading] of pages) {
      await user.click(menu().getByRole("link", { name: link }));
      expect(await screen.findByRole("heading", { level: 1, name: heading })).toBeInTheDocument();
    }
    await user.click(menu().getByRole("link", { name: "Join" }));
    expect(await screen.findByRole("textbox", { name: "First name" })).toBeInTheDocument();
    expect(menu().getByRole("link", { name: "Sign in" })).toHaveAttribute("href", "/signin");
  });
});
