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
  "GET /site/": { name: "Umoja Party" },
  "GET /party/places/": [{ id: "c1", name: "Nairobi City" }],
  "GET /candidates/": [CARD],
  "GET /candidates/?seat=governor": [],
  "GET /candidates/?seat=governor&q=Kang": [],
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
    await vi.waitFor(() => expect(calls.some((c) => c.path === "/candidates/?seat=governor&q=Kang")).toBe(true));
    expect(calls.some((c) => c.path === "/candidates/?seat=governor")).toBe(true);
  });

  it("offers only the seat's wards, and hides the form when volunteering is closed", async () => {
    stubApi(PUBLIC);
    const first = renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });
    await userEvent.click(await screen.findByRole("button", { name: "Volunteer for Brian" }));
    const ward = await screen.findByRole("combobox", { name: "Ward" });
    const wards = within(ward).getAllByRole("option").map((o) => o.textContent);
    first.unmount();

    stubApi({ ...PUBLIC, [`GET /candidates/${CARD.slug}/`]: { ...DETAIL, volunteering_open: false, wards: [] } });
    renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });
    await screen.findByRole("heading", { name: "Brian Ochieng" });

    expect(wards).toEqual(["Pick your ward", "Parklands", "Kangemi"]);
    expect(screen.queryByRole("button", { name: "Volunteer for Brian" })).toBeNull();
  });

  it("shows each priority as a photo card", async () => {
    const water = { title: "Water", text: "Piped water in every ward.", image_url: "https://example.org/water.jpg" };
    stubApi({ ...PUBLIC, [`GET /candidates/${CARD.slug}/`]: { ...DETAIL, priorities: [water] } });
    renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });

    await userEvent.click(await screen.findByRole("tab", { name: "Priorities" }));

    const card = (await screen.findByText("Water")).closest(".aspect-square");
    expect(card.querySelector("img").getAttribute("src")).toBe(water.image_url);
    expect(within(card).getByText("01")).toBeInTheDocument();
    expect(within(card).getByText(water.text)).toBeInTheDocument();
  });

  it("sends the volunteer form only once every field is filled", async () => {
    const calls = stubApi({
      ...PUBLIC,
      "GET /party/places/?ward=w1": [{ id: "s1", name: "Parklands Primary" }],
      [`POST /candidates/${CARD.slug}/volunteer/`]: { message: "Thank you.", withdraw_code: "x" },
    });
    renderApp(<AppRoutes />, { path: `/candidates/${CARD.slug}` });
    await userEvent.click(await screen.findByRole("button", { name: "Volunteer for this campaign" }));
    expect(screen.getByRole("dialog", { name: "Volunteer for Brian" })).toBeInTheDocument();
    const send = await screen.findByRole("button", { name: "I'll volunteer" });
    const steps = [
      () => userEvent.type(screen.getByRole("textbox", { name: "First name" }), "Wanjiku"),
      () => userEvent.type(screen.getByRole("textbox", { name: "Last name" }), "Njeri"),
      () => userEvent.type(screen.getByRole("textbox", { name: "Email" }), "wanjiku@example.com"),
      () => userEvent.type(screen.getByRole("textbox", { name: "Phone" }), "0712345678"),
      () => userEvent.selectOptions(screen.getByRole("combobox", { name: "Ward" }), "w1"),
      async () => userEvent.selectOptions(screen.getByRole("combobox", { name: "Polling station" }), await screen.findByRole("option", { name: "Parklands Primary" })),
      () => userEvent.selectOptions(screen.getByRole("combobox", { name: "Profession" }), "teacher"),
      () => userEvent.click(screen.getByRole("checkbox", { name: "Door-to-door Campaign" })),
      () => userEvent.selectOptions(screen.getByRole("combobox", { name: "Preferred contact" }), "sms"),
      () => userEvent.click(screen.getByRole("checkbox", { name: DETAIL.consent_wording })),
    ];
    const disabled = [];
    for (const step of steps) {
      disabled.push(send.disabled);
      await step();
    }
    await userEvent.click(send);

    expect(disabled.every(Boolean)).toBe(true);
    const sent = calls.find((c) => c.method === "POST").body;
    expect(sent).toMatchObject({ first_name: "Wanjiku", last_name: "Njeri", email: "wanjiku@example.com", phone: "0712345678", ward: "w1", registration_centre: "s1", profession: "teacher", areas: ["door_to_door"], preferred_contact: "sms", consent_given: true });
  });
});

describe("the website editor's candidates", () => {
  it("publishes a profile and names an aspirant at an event", async () => {
    signIn("manager");
    useAuth.setState({ user: { ...useAuth.getState().user, is_superuser: true } });
    const candidate = { aspirant_id: "a1", name: "Brian Ochieng", seat: "mp", area: "Westlands", profile: { photo_url: "", slogan: "", bio: "", priorities: [], office_address: "", office_phone: "", office_email: "", published: false } };
    const event = { id: "e1", kind: "event", title: "Town hall", body: "", image_url: "", event_date: "2026-11-20", venue: "", published_on: null, published: true, updated_at: "2026-11-01T00:00:00Z" };
    const calls = stubApi({
      "GET /site/": { name: "Umoja Party" },
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
