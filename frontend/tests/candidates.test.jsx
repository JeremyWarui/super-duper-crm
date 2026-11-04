/** Candidates on the website, the editor's profiles and event aspirants, and the manager's list. */
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import Root, { AppRoutes } from "../src/Gate";
import Volunteers from "../src/pages/campaign/Volunteers";
import { useAuth } from "../src/store/auth";
import { renderApp, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

const CARD = { slug: "mp-westlands-1a2b3c4d", name: "Brian Ochieng", seat: "mp", area: "Westlands", county: "Nairobi City", photo_url: "", slogan: "Jobs" };
const DETAIL = {
  ...CARD,
  bio: "Teacher.",
  priorities: [],
  office_address: "",
  office_phone: "",
  office_email: "",
  events: [],
  volunteering_open: true,
  wards: [{ id: "w1", name: "Parklands" }, { id: "w2", name: "Kangemi" }],
  consent_wording: "I agree that this campaign may contact me.",
};
const PUBLIC = {
  "GET /party/": { name: "Umoja Party" },
  "GET /party/places/": [{ id: "c1", name: "Nairobi City" }],
  "GET /candidates/?seat=&county=&q=": [CARD],
  "GET /candidates/?seat=governor&county=&q=": [],
  "GET /candidates/?seat=governor&county=&q=Kang": [],
  [`GET /candidates/${CARD.slug}/`]: DETAIL,
};

describe("candidates on the website", () => {
  it("narrows the list by seat and by a name or area search", async () => {
    const calls = stubApi(PUBLIC);
    renderApp(<AppRoutes />, { path: "/candidates" });
    await screen.findByText("Brian Ochieng");

    await userEvent.click(within(screen.getByRole("group", { name: "Filter by seat" })).getByRole("button", { name: "Governor" }));

    expect(await screen.findByText(/No candidates match/)).toBeInTheDocument();
    await userEvent.type(screen.getByRole("searchbox", { name: "Search by name or area" }), "Kang");
    await vi.waitFor(() => expect(calls.some((c) => c.path === "/candidates/?seat=governor&county=&q=Kang")).toBe(true));
    expect(calls.some((c) => c.path === "/candidates/?seat=governor&county=&q=")).toBe(true);
  });

  it("offers only the seat's wards, and hides the form when volunteering is closed", async () => {
    stubApi(PUBLIC);
    const first = renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });
    const ward = await screen.findByRole("combobox", { name: "Ward" });
    const wards = within(ward).getAllByRole("option").map((o) => o.textContent);
    first.unmount();

    stubApi({ ...PUBLIC, [`GET /candidates/${CARD.slug}/`]: { ...DETAIL, volunteering_open: false, wards: [] } });
    renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });
    await screen.findByRole("heading", { name: "Brian Ochieng" });

    expect(wards).toEqual(["Pick your ward", "Parklands", "Kangemi"]);
    expect(screen.queryByRole("button", { name: "I'll volunteer" })).toBeNull();
  });
});

describe("the website editor's candidates", () => {
  it("publishes a profile and names an aspirant at an event", async () => {
    signIn("manager");
    useAuth.setState({ user: { ...useAuth.getState().user, is_superuser: true } });
    const candidate = { aspirant_id: "a1", name: "Brian Ochieng", seat: "mp", area: "Westlands", profile: { photo_url: "", slogan: "", bio: "", priorities: [], office_address: "", office_phone: "", office_email: "", published: false } };
    const event = { id: "e1", kind: "event", title: "Town hall", body: "", image_url: "", event_date: "2026-11-20", venue: "", published_on: null, published: true, updated_at: "2026-11-01T00:00:00Z" };
    const calls = stubApi({
      "GET /party/": { name: "Umoja Party" },
      "GET /admin/party/posts/": [event],
      "GET /admin/party/candidates/": [candidate],
      "PUT /admin/party/candidates/a1/profile/": candidate,
      "GET /admin/party/posts/e1/aspirants/": { aspirant_ids: [] },
      "PUT /admin/party/posts/e1/aspirants/": { aspirant_ids: ["a1"] },
      "GET /party/places/": [],
    });
    renderApp(<Root />, { path: "/party/website" });
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "Candidates" }));
    await user.click(await screen.findByRole("button", { name: "Edit profile" }));
    await user.type(screen.getByLabelText("Slogan (optional)"), "Jobs");
    await user.click(screen.getByRole("checkbox", { name: "Published on the website" }));
    await user.click(screen.getByRole("button", { name: "Save profile" }));
    await user.click(screen.getByRole("button", { name: "Posts" }));
    await user.click(await screen.findByRole("button", { name: "Edit" }));
    await user.click(await screen.findByRole("checkbox", { name: /Brian Ochieng/ }));
    await user.click(screen.getByRole("button", { name: "Save aspirants" }));

    const profile = calls.find((c) => c.method === "PUT" && c.path === "/admin/party/candidates/a1/profile/");
    expect(profile.body).toMatchObject({ slogan: "Jobs", published: true, priorities: [] });
    await vi.waitFor(() => expect(calls.find((c) => c.method === "PUT" && c.path === "/admin/party/posts/e1/aspirants/")?.body).toEqual({ aspirant_ids: ["a1"] }));
  });
});

describe("the campaign manager's volunteers", () => {
  it("lists the volunteers the candidate's page signed up", async () => {
    stubApi({
      "GET /campaigns/k1/volunteers/": [
        { id: "v1", first_name: "Wanjiku", last_name: "Njeri", phone: "+254712345678", ward: { id: "w1", name: "Parklands" }, registration_centre: null, profession: "teacher", profession_other: "", status: "interested", interests: ["door_to_door"], interest_other: "", preferred_contact: "sms" },
      ],
    });
    render(
      <QueryClientProvider client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}>
        <Volunteers campaign={{ id: "k1" }} />
      </QueryClientProvider>,
    );

    const row = (await screen.findByText("Wanjiku Njeri")).closest("tr");

    expect(row).toHaveTextContent("Parklands");
    expect(within(row).getByRole("button", { name: "Make active" })).toBeInTheDocument();
  });
});
