import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render } from "@testing-library/react";
import { vi } from "vitest";
import { useAuth } from "../src/store/auth";

export const API = "http://localhost:8000/api";

/** Stub fetch with `"METHOD /path"` -> body, or -> `{ status, body }` to fail. */
export function stubApi(routes) {
  const calls = [];
  const fetchMock = vi.fn(async (url, options = {}) => {
    const method = options.method || "GET";
    const path = String(url).replace(API, "");
    calls.push({ method, path, body: options.body ? JSON.parse(options.body) : null, options });

    const match = routes[`${method} ${path}`] ?? routes[`${method} ${path.split("?")[0]}`];
    if (match === undefined) {
      return jsonResponse(404, { detail: `No stub for ${method} ${path}` });
    }
    const override =
      match !== null && typeof match === "object" && "status" in match && "body" in match;
    return override ? jsonResponse(match.status, match.body) : jsonResponse(200, match);
  });
  vi.stubGlobal("fetch", fetchMock);
  return calls;
}

function jsonResponse(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  };
}

export function signIn(role = "manager") {
  useAuth.setState({
    token: "test-token",
    user: { id: "u1", username: role, full_name: "Test User", role },
  });
}

/** Render inside a fresh query client. */
export function renderApp(ui) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  return {
    queryClient,
    ...render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>),
  };
}

export const CAMPAIGN = {
  id: "c1",
  candidate: "u1",
  title: "Jane for Roysambu",
  office_level: "constituency",
  county: null,
  constituency: "k1",
  ward: null,
  election_date: "2027-08-10",
  operational_grain: "ward",
  created_at: "2026-01-01T00:00:00Z",
};

export const STRATEGY = {
  win_number: 19981,
  committed: 9211,
  progress_pct: 46.1,
  total_registered: 66600,
  total_cast: 39960,
  units: [
    {
      unit: "Zimmerman",
      needed: 9211,
      committed: 9211,
      gap: 0,
      progress: 1,
      events: 2,
      has_mobilizer: true,
      share: 0.461,
    },
    {
      unit: "Githurai",
      needed: 10770,
      committed: 0,
      gap: 10770,
      progress: 0,
      events: 0,
      has_mobilizer: false,
      share: 0.539,
    },
  ],
  notes: [
    {
      tone: "go",
      title: "Go next: Githurai",
      text: "Biggest winnable gap - 10,770 votes short, 54% of the win number is here.",
    },
  ],
};

export const TARGETS = [
  {
    id: "t1",
    campaign: "c1",
    ward: "w1",
    ward_name: "Zimmerman",
    registration_centre: null,
    centre_name: null,
    registered_voters: 30701,
    projected_turnout_pct: "60.00",
    votes_needed: 9211,
    votes_committed: 9211,
    votes_remaining: 0,
    progress_pct: 100.0,
  },
  {
    id: "t2",
    campaign: "c1",
    ward: "w2",
    ward_name: "Githurai",
    registration_centre: null,
    centre_name: null,
    registered_voters: 35899,
    projected_turnout_pct: "60.00",
    votes_needed: 10770,
    votes_committed: 0,
    votes_remaining: 10770,
    progress_pct: 0.0,
  },
];

export const EVENTS = [
  {
    id: "e1",
    campaign: "c1",
    ward: "w1",
    ward_name: "Zimmerman",
    registration_centre: null,
    mobilizer: "m1",
    title: "Zimmerman town hall",
    venue: "Social hall",
    scheduled_date: "2027-06-12T00:00:00Z",
    status: "planned",
    number_reached: 0,
    number_attended: 0,
    turnout_pct: 0.0,
  },
];

export const INVITE_RESULT = {
  provider: "console",
  delivered: false,
  dry_run: false,
  message: "Town hall this Saturday.",
  parts: 1,
  supporters_matched: 3,
  requested: 2,
  accepted: [{ phone: "+254712345678", status: "skipped", detail: "" }],
  rejected: [{ phone: "not a phone", status: "invalid", detail: "Not a usable number." }],
  detail:
    "No SMS gateway is configured, so nothing was sent. Set SMS_PROVIDER=africastalking with AT_USERNAME and AT_API_KEY to send.",
  number_reached: 0,
};

export const CREATED_USER = {
  id: "u9",
  username: "wanjiku",
  full_name: "Wanjiku Njeri",
  role: "mobilizer",
  phone: "+254700333444",
  password: "Kx8fQ2mNpR4w",
  mobilizer: "m9",
  ward_name: "Githurai",
};

/** Everything App reads on first render. */
export function dashboardRoutes(overrides = {}) {
  return {
    "GET /campaigns/": [CAMPAIGN],
    "GET /strategy/": STRATEGY,
    "GET /targets/": TARGETS,
    "GET /events/": EVENTS,
    "GET /mobilizers/": [],
    "GET /supporters/": [],
    "POST /events/e1/invite/": INVITE_RESULT,
    "POST /users/": CREATED_USER,
    "GET /users/": [],
    ...overrides,
  };
}
