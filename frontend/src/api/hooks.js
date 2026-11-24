// src/api/hooks.js
// React Query hooks. Queries read; mutations write and then invalidate the
// caches that changed — e.g. scheduling an event refreshes both the event list
// AND the strategy read, because the strategy is computed from events.

import { useEffect } from "react";
import {
  keepPreviousData,
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, download, upload } from "./client";
import { useAuth } from "@/store/auth";
import { pollWhileWaiting } from "@/lib/sms";

// ---- Shared shapes ----------------------------------------------------------
/** "key=value&..." for the filters that have a value; written after a literal "?" so the contract test reads the path. */
const queryOf = (filters) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters || {})) {
    if (value !== "" && value != null) params.set(key, value);
  }
  return params.toString();
};

/** A read cached under [key, id] that waits for its id. */
const useFor = (key, id, queryFn, more) => useQuery({ queryKey: [key, id], queryFn, enabled: !!id, ...more });

// Invalidates each key; resolves once the active ones have refetched.
function useInvalidator() {
  const qc = useQueryClient();
  return (...keys) => Promise.all(keys.map((k) => qc.invalidateQueries({ queryKey: [k] })));
}

function useInvalidating(when, mutationFn, keys) {
  const invalidate = useInvalidator();
  return useMutation({ mutationFn, [when]: () => invalidate(...keys) });
}

// A mutation that refreshes the caches named by `keys` once it succeeds; it stays pending until they have.
const useWrite = (mutationFn, ...keys) => useInvalidating("onSuccess", mutationFn, keys);

// The same, refreshing after a refusal too: a refused change may mean the row moved on.
const useWriteSettled = (mutationFn, ...keys) => useInvalidating("onSettled", mutationFn, keys);

/** A mutation whose answer becomes the cache at `key`: an array, or a function of the variables. */
function useReplace(mutationFn, key) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (data, variables) => data && qc.setQueryData(typeof key === "function" ? key(variables) : key, data),
  });
}

/** Saves through `change(id, body)` with an id and `add(body)` without one. */
const saveBy = (add, change) => ({ id, ...body }) => (id ? change(id, body) : add(body));

// ---- Queries --------------------------------------------------------------
/** A campaign's targets, only those in `place.county` or `place.constituency` when given. */
export const useTargets = (campaignId, place = {}) =>
  useQuery({
    queryKey: ["targets", campaignId, place.county || null, place.constituency || null],
    queryFn: () => api(`/targets/?${queryOf({ campaign: campaignId, county: place.county, constituency: place.constituency })}`),
    enabled: !!campaignId,
  });

export const useEvents = (campaignId) => useFor("events", campaignId, () => api(`/events/?campaign=${campaignId}`));

export const useMobilizers = (campaignId) => useFor("mobilizers", campaignId, () => api(`/mobilizers/?campaign=${campaignId}`));

// The contact register, newest first, PAGE_ROWS at a time; `q` matches a name or phone on the server.
export const useSupporterPages = (campaignId, { q = "", support_level = "" } = {}) =>
  useInfiniteQuery({
    queryKey: ["supporters", campaignId, "pages", q, support_level],
    queryFn: ({ pageParam }) => api(`/supporters/?${queryOf({ campaign: campaignId, q, support_level, limit: PAGE_ROWS, offset: pageParam })}`),
    initialPageParam: 0,
    getNextPageParam: nextPlain,
    placeholderData: keepPreviousData,
    enabled: !!campaignId,
  });

/** Counts of the register, by level and missing consent, for the same `q`. */
export const useSupporterCounts = (campaignId, q = "") =>
  useQuery({
    queryKey: ["supporters", campaignId, "summary", q],
    queryFn: () => api(`/supporters/summary/?${queryOf({ campaign: campaignId, q })}`),
    enabled: !!campaignId,
    placeholderData: keepPreviousData,
  });

/** The first few contacts matching `q`, once it has two characters. */
export const useSupporterSearch = (campaignId, q) =>
  useQuery({
    queryKey: ["supporters", campaignId, "search", q],
    queryFn: () => api(`/supporters/?${queryOf({ campaign: campaignId, q, limit: 8 })}`),
    enabled: !!campaignId && q.length >= 2,
  });

export const useConsentWording = () =>
  useQuery({
    queryKey: ["consent-wording"],
    queryFn: () => api("/supporters/consent-wording/"),
    staleTime: Infinity,
  });

/** The strategy read; its units only in `place.county` or `place.constituency` when given. */
export const useStrategy = (campaignId, place = {}) =>
  useQuery({
    queryKey: ["strategy", campaignId, place.county || null, place.constituency || null],
    queryFn: () => api(`/strategy/?${queryOf({ campaign: campaignId, county: place.county, constituency: place.constituency })}`),
    enabled: !!campaignId,
  });

// ---- Mutations ------------------------------------------------------------
export const useAddMobilizer = () =>
  useWrite(
    (payload) =>
      api("/mobilizers/", { method: "POST", body: payload }),
    "mobilizers", "strategy",
  );

// Rename a mobilizer, or move them to a unit or to none; the server frees the unit's last holder.
export const useUpdateMobilizer = () =>
  useWrite(
    ({ id, ...body }) =>
      api(`/mobilizers/${id}/`, { method: "PATCH", body }),
    "mobilizers", "strategy",
  );

export const useScheduleEvent = () =>
  useWrite(
    (payload) => api("/events/", { method: "POST", body: payload }),
    "events", "strategy",
  );

export const useRecordEvent = () =>
  useWrite(
    ({ id, number_reached, number_attended }) =>
      api(`/events/${id}/record/`, {
        method: "POST",
        body: { number_reached, number_attended },
      }),
    "events", "strategy",
  );

// A supporter the team registers by hand; progress counts them at once.
export const useRegisterSupporter = () =>
  useWrite(
    (payload) =>
      api("/supporters/", { method: "POST", body: payload }),
    "supporters", "strategy",
  );

// Put a supporter at a centre with a target, so they count toward it.
export const usePlaceSupporter = () =>
  useWrite(
    ({ id, registration_centre }) =>
      api(`/supporters/${id}/`, { method: "PATCH", body: { registration_centre } }),
    "supporters", "strategy",
  );

// ---- Supporter sign-up behind an event's QR code -----------------------------
export const useJoinPage = (code) =>
  useQuery({
    queryKey: ["join", code],
    queryFn: () => api(`/join/${encodeURIComponent(code)}/`, { anonymous: true }),
    retry: false,
  });

export function useJoin(code) {
  return useMutation({
    mutationFn: (payload) =>
      api(`/join/${encodeURIComponent(code)}/`, { method: "POST", body: payload, anonymous: true }),
  });
}

// Withdrawing needs only the private code from the thank-you screen.
export function useWithdraw(code) {
  return useMutation({
    mutationFn: () =>
      api(`/join/withdraw/${encodeURIComponent(code)}/`, { method: "POST", anonymous: true }),
  });
}

// The campaign-wide sign-up link; only the manager may read or open it.
export const useCampaignSignups = (campaignId) =>
  useFor("campaignSignups", campaignId, () => api(`/campaigns/${campaignId}/signups/`));

export const useSetCampaignSignups = () =>
  useWrite(
    ({ campaign, open }) =>
      api(`/campaigns/${campaign}/signups/`, { method: "POST", body: { open } }),
    "campaignSignups",
  );

export const useSetSignups = () =>
  useWrite(
    ({ id, open }) =>
      api(`/events/${id}/signups/`, { method: "POST", body: { open } }),
    "events",
  );

// ---- Payments to mobilizers ----------------------------------------------
export const usePayments = (campaignId) => useFor("payments", campaignId, () => api(`/payments/?campaign=${campaignId}`));

// Whether a release moves real money ("practice" moves none).
export const usePayoutMode = () =>
  useQuery({ queryKey: ["payoutMode"], queryFn: () => api("/payments/payout-mode/") });

// Whether the payout balance covers these payments and their fees.
export const useReleaseCheck = (ids) =>
  useQuery({
    queryKey: ["payments", "release-check", ids],
    queryFn: () => api("/payments/release-check/", { method: "POST", body: { payments: ids } }),
    enabled: ids.length > 0,
  });

export const useReconciliation = (campaignId, enabled = true) =>
  useQuery({
    queryKey: ["payments", "reconciliation", campaignId],
    queryFn: () => api(`/payments/reconciliation/?campaign=${campaignId}`),
    enabled: !!campaignId && enabled,
  });

export const useReconcileNow = () =>
  useReplace(
    (campaignId) => api(`/payments/reconciliation/?campaign=${campaignId}`, { method: "POST" }),
    (campaignId) => ["payments", "reconciliation", campaignId],
  );

export const useReleasePayment = () =>
  useWriteSettled(({ id }) => api(`/payments/${id}/release/`, { method: "POST" }), "payments");

export const useMarkNotSent = () =>
  useWriteSettled(({ id }) => api(`/payments/${id}/not-sent/`, { method: "POST" }), "payments");

export const useSchedulePayment = () =>
  useWrite(
    (payload) => api("/payments/", { method: "POST", body: payload }),
    "payments",
  );

export const useMarkPaid = () =>
  useWriteSettled(
    ({ id, reference }) => api(`/payments/${id}/paid/`, { method: "POST", body: { reference } }),
    "payments",
  );

// Refuses a payment with a reason; its assignment can be paid by a new one.
export const useDeclinePayment = () =>
  useWriteSettled(
    ({ id, reason }) => api(`/payments/${id}/decline/`, { method: "POST", body: { reason } }),
    "payments",
  );

// ---- assignments ------------------------------------------------------------
export const useAssignments = (campaignId, status) =>
  useQuery({
    queryKey: ["assignments", campaignId, status],
    queryFn: () => api(`/assignments/?${queryOf({ campaign: campaignId, status })}`),
    enabled: !!campaignId,
  });

export const useCreateAssignment = () =>
  useWrite(
    (body) => api("/assignments/", { method: "POST", body }),
    "assignments",
  );

// Texts to supporters: drafts, approval and the delivery log.
export const useMessages = (campaignId) => useFor("messages", campaignId, () => api(`/messages/?campaign=${campaignId}`));

// Who a message to these wards would reach now; the wording does not change it.
export const useMessageReach = (campaignId, wards) =>
  useQuery({
    queryKey: ["messages", "reach", campaignId, wards],
    queryFn: () => api("/messages/preview/", { method: "POST", body: { campaign: campaignId, wards, body: "-" } }),
    enabled: !!campaignId,
    placeholderData: (previous) => previous,
  });

export const useDraftMessage = () =>
  useWrite(
    (body) => api("/messages/", { method: "POST", body }),
    "messages", "sms-runs",
  );

// Bulk text runs: polled every ten seconds while one is sending or waiting for the window.
export const useSmsRuns = (campaignId) =>
  useQuery({
    queryKey: ["sms-runs", campaignId],
    queryFn: () => api(`/campaigns/${campaignId}/sms-runs/`),
    enabled: !!campaignId,
    refetchInterval: (query) =>
      query.state.data?.some((r) => ["sending", "scheduled"].includes(r.status)) ? 10_000 : false,
  });

const RUN_ACTIONS = {
  pause: (c, id) => api(`/campaigns/${c}/sms-runs/${id}/pause/`, { method: "POST" }),
  resume: (c, id) => api(`/campaigns/${c}/sms-runs/${id}/resume/`, { method: "POST" }),
  halt: (c, id, body) => api(`/campaigns/${c}/sms-runs/${id}/halt/`, { method: "POST", body }),
};

export const useRunAction = (campaignId) =>
  useWrite(({ id, action, body }) => RUN_ACTIONS[action](campaignId, id, body), "sms-runs");

// Online calls and the call alerts that ring the team.
export const useCalls = (campaignId) =>
  useQuery({
    queryKey: ["calls", campaignId],
    queryFn: () => api(`/campaigns/${campaignId}/meetings/`),
    enabled: !!campaignId,
    refetchInterval: (query) => (query.state.data?.some((c) => c.meeting.status === "live") ? 15_000 : false),
  });

export const useStartCall = (campaignId) =>
  useWrite((body) => api(`/campaigns/${campaignId}/meetings/`, { method: "POST", body }), "calls");

// A fresh token each time the page opens; it is good for fifteen minutes.
export const useJoinCall = (meetingId) =>
  useQuery({
    queryKey: ["call-token", meetingId],
    queryFn: () => api(`/meetings/${meetingId}/token/`),
    enabled: !!meetingId,
    staleTime: 0,
    gcTime: 0,
    refetchOnWindowFocus: false,
    retry: false,
  });

export const useEndCall = () =>
  useWrite((meetingId) => api(`/meetings/${meetingId}/end/`, { method: "POST" }), "calls");

export const usePushKey = () =>
  useQuery({ queryKey: ["push-key"], queryFn: () => api("/push/key/"), staleTime: Infinity });

export const useSendMessage = () =>
  useWrite(
    ({ id, language }) => api(`/messages/${id}/send/`, { method: "POST", body: { language } }),
    "messages", "sms-runs",
  );

export const useDeclineMessage = () =>
  useWrite(
    ({ id, note }) => api(`/messages/${id}/decline/`, { method: "POST", body: { note } }),
    "messages",
  );

export const useDeleteMessage = () =>
  useWrite(
    (id) => api(`/messages/${id}/`, { method: "DELETE" }),
    "messages",
  );

export const useMessageLog = (id) =>
  useQuery({
    queryKey: ["messages", "log", id],
    queryFn: () => api(`/messages/${id}/log/`),
    enabled: !!id,
    refetchInterval: pollWhileWaiting,
  });

// A campaign's test texts, sent at once past the queue.
export const useTestTexts = (campaignId) =>
  useQuery({
    queryKey: ["sms-tests", campaignId],
    queryFn: () => api(`/console/sms/test/?campaign=${campaignId}`),
    enabled: !!campaignId,
    refetchInterval: pollWhileWaiting,
  });

export const useSendTestText = () =>
  useWrite((body) => api("/console/sms/test/", { method: "POST", body }), "sms-tests");

export const useSettleAssignment = () =>
  useWriteSettled(
    ({ id, outcome }) =>
      outcome === "done"
        ? api(`/assignments/${id}/done/`, { method: "POST" })
        : api(`/assignments/${id}/cancel/`, { method: "POST" }),
    "assignments",
  );

// ---- geography pickers ----------------------------------------------------
export const useCounties = (enabled = true) =>
  useQuery({ queryKey: ["counties"], queryFn: () => api("/counties/"), enabled, staleTime: Infinity });

export const useConstituencies = (countyId) =>
  useFor("constituencies", countyId, () => api(`/constituencies/?county=${countyId}`));

export const useWardsIn = (constituencyId) =>
  useFor("wardsIn", constituencyId, () => api(`/wards/?constituency=${constituencyId}`));

// The user's campaign(s). For a single-campaign MVP, take the first.
export const useCampaigns = () =>
  useQuery({ queryKey: ["campaigns"], queryFn: () => api("/campaigns/") });

// Ward drill-down for MCA races: the ward's registration centres + their voters.
export const useCentres = (wardId) => useFor("centres", wardId, () => api(`/centres/?ward=${wardId}`));

export const useWardsInCounty = (countyId) => useFor("wardsInCounty", countyId, () => api(`/wards/?county=${countyId}`));

// The units a chosen seat will get a target for, before it is created.
export function useUnitsPreview({ office_level, county, constituency, ward }) {
  const wardsInCounty = useWardsInCounty(
    office_level === "county" ? county : null,
  );
  const wardsInConstituency = useWardsIn(
    office_level === "constituency" ? constituency : null,
  );
  const centres = useCentres(office_level === "ward" ? ward : null);

  const source =
    office_level === "county"
      ? wardsInCounty
      : office_level === "constituency"
        ? wardsInConstituency
        : centres;
  return {
    grain: office_level === "ward" ? "centre" : "ward",
    units: source.data || [],
    isLoading: source.isLoading,
    error: source.error,
  };
}

// Text an event's supporters. A dry run sends nothing.
export function useInviteToEvent() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/events/${id}/invite/`, { method: "POST", body }),
    onSuccess: (_data, variables) => {
      if (!variables.dry_run) invalidate("events", "strategy");
    },
  });
}

// Creates a login. The password comes back once and is never fetchable again.
export const useCreateUser = () =>
  useWrite(
    (payload) => api("/users/", { method: "POST", body: payload }),
    "team", "mobilizers", "strategy",
  );

// ---- the campaign's own team ----------------------------------------------
export const useTeam = (campaignId) => useFor("team", campaignId, () => api(`/campaigns/${campaignId}/team/`));

// The candidate adds the manager, or replaces the one there with `replace: true`.
export const useSetManager = () =>
  useWrite(
    ({ campaign, ...body }) =>
      api(`/campaigns/${campaign}/team/manager/`, { method: "POST", body }),
    "team",
  );

// Adds a coordinator or comms officer; the password comes back once.
export const useAddStaff = () =>
  useWrite(
    ({ campaign, ...body }) =>
      api(`/campaigns/${campaign}/team/`, { method: "POST", body }),
    "team",
  );

// Takes a coordinator or comms officer off the campaign; their login is turned off.
export const useRemoveStaff = () =>
  useWrite(
    ({ campaign, user }) =>
      api(`/campaigns/${campaign}/team/${user}/`, { method: "DELETE" }),
    "team",
  );

// A coordinator's area: the wards and registration centres they cover.
export const useArea = (campaignId, userId) =>
  useQuery({
    queryKey: ["area", campaignId, userId],
    queryFn: () => api(`/campaigns/${campaignId}/team/${userId}/area/`),
    enabled: !!campaignId && !!userId,
  });

export const useSetArea = () =>
  useWrite(
    ({ campaign, user, ...body }) =>
      api(`/campaigns/${campaign}/team/${user}/area/`, { method: "PUT", body }),
    "area",
  );

// ---- sign-in links ---------------------------------------------------------
// The same answer whether or not the address has a login.
export const useRequestReset = () =>
  useMutation({
    mutationFn: (email) => api("/auth/password-reset/", { method: "POST", body: { email }, anonymous: true }),
  });

// What a sign-in link is for and whose login it sets; an error when it is spent.
// Pass enabled=false once the link is claimed, so signing in never reads the spent link again.
export const useLink = (token, enabled = true) =>
  useQuery({
    queryKey: ["link", token],
    queryFn: () => api(`/auth/links/${token}/`, { anonymous: true }),
    retry: false,
    enabled,
  });

// Sets the password through the link; resolves to the session it opens.
export const useClaimLink = (token) =>
  useMutation({
    mutationFn: (password) => api(`/auth/links/${token}/`, { method: "POST", body: { password }, anonymous: true }),
  });

// ---- sign-in options -------------------------------------------------------
export const useSignInOptions = () =>
  useQuery({ queryKey: ["sign-in-options"], queryFn: () => api("/auth/options/", { anonymous: true }), staleTime: Infinity });

export const finishGoogle = (handoff, bind) =>
  api("/auth/google/finish/", { method: "POST", body: { handoff, bind }, anonymous: true });

// ---- admin console --------------------------------------------------------
// Only a superuser may call these; every route checks the flag again itself.
export const useAdminOverview = () =>
  useQuery({
    queryKey: ["admin", "overview"],
    queryFn: () => api("/admin/overview/"),
  });

export const useAdminUsers = (role) =>
  useQuery({
    queryKey: ["admin", "users", role || "all"],
    queryFn: () => api(`/admin/users/?${queryOf({ role })}`),
    // Each filter is its own key. Without this the list empties while the next
    // one loads and the console says nobody matches.
    placeholderData: keepPreviousData,
  });

// The password comes back once, so it is handed to the hook's owner rather
// than to the form, which unmounts as soon as the list refetches.
export function useCreateLogin({ onPassword } = {}) {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/admin/users/", { method: "POST", body: payload }),
    onSuccess: (data) => {
      onPassword?.(data);
      return invalidate("admin");
    },
  });
}

// Emails the login a reset link. Every callback runs on whoever owns the hook,
// and is handed the id it was about: React Query drops per-call callbacks when
// the calling component unmounts, and a row unmounts whenever the list
// refetches or the filter changes. A shared mutation also only remembers its latest call, so the caller
// has to key what it keeps by id rather than read `error` or `isPending` here.
export function useResetPassword({ onPassword, onFailed, onDone } = {}) {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id }) => api(`/admin/users/${id}/reset-password/`, { method: "POST" }),
    onSuccess: (data, variables) => {
      onPassword?.(data, variables);
      return invalidate("admin");
    },
    onError: (error, variables) => onFailed?.(error, variables),
    onSettled: (_data, _error, variables) => onDone?.(variables),
  });
}

export const useSetActive = () =>
  useWrite(({ id, active }) => api(`/admin/users/${id}/active/`, { method: "POST", body: { active } }), "admin");

export const useSetEmail = () =>
  useWrite(({ id, email }) => api(`/admin/users/${id}/email/`, { method: "PUT", body: { email } }), "admin");

export const useRenameCampaign = () =>
  useWrite(({ campaign, title }) => api(`/admin/campaigns/${campaign}/`, { method: "PATCH", body: { title } }), "admin");

// Only a superuser deletes a campaign; nothing inside one can. A 404 means somebody else deleted it.
export const useDeleteCampaign = () =>
  useWriteSettled(({ campaign }) => api(`/admin/campaigns/${campaign}/`, { method: "DELETE" }), "admin");

// No role: the place somebody takes is their login's, and the server refuses a payload that says otherwise.
export const useAddMember = () =>
  useWrite(({ campaign, user }) => api(`/admin/campaigns/${campaign}/members/`, { method: "POST", body: { user } }), "admin");

export const useRemoveMember = () =>
  useWrite(({ campaign, user }) => api(`/admin/campaigns/${campaign}/members/${user}/`, { method: "DELETE" }), "admin");

// ---- site settings ---------------------------------------------------------
export const useSite = () =>
  useQuery({
    queryKey: ["site"],
    queryFn: () => api("/site/", { anonymous: true }),
    // Before setup the answer is final: go to /setup at once.
    retry: (count, error) => error?.code !== "not_set_up" && count < 3,
  });

// ---- public website content ------------------------------------------------
// Published news, newest first, 20 per page from `offset`, optionally one `label`;
// or events from today on, optionally in one `county`.
export const usePublicPosts = (kind, offset = 0, { label = "", county = "" } = {}) =>
  useQuery({
    queryKey: ["public-posts", kind, offset, label, county],
    queryFn: () => api(`/website/posts/?${queryOf({ kind, offset, label, county })}`, { anonymous: true }),
  });

export const usePublicPost = (id) =>
  useQuery({
    queryKey: ["public-post", id],
    queryFn: () => api(`/website/posts/${id}/`, { anonymous: true }),
  });

// The homepage's carousel slides and agenda issues: published ones, or all of them for the editor.
export const usePublicSlides = () =>
  useQuery({ queryKey: ["public-slides"], queryFn: () => api("/website/slides/", { anonymous: true }) });

export const usePublicIssues = () =>
  useQuery({ queryKey: ["public-issues"], queryFn: () => api("/website/issues/", { anonymous: true }) });

export const usePublicIssue = (id) =>
  useQuery({ queryKey: ["public-issues", id], queryFn: () => api(`/website/issues/${id}/`, { anonymous: true }) });

// Documents on the Media page.
export const usePublicDocuments = () =>
  useQuery({ queryKey: ["public-documents"], queryFn: () => api("/website/documents/", { anonymous: true }) });

// The homepage's Watch row.
export const usePublicVideos = () =>
  useQuery({ queryKey: ["public-videos"], queryFn: () => api("/website/videos/", { anonymous: true }) });

// Counties, or one county's constituencies, or one constituency's wards.
export const usePlaces = ({ county, constituency, ward, enabled = true } = {}) =>
  useQuery({
    // A lookup waiting for its place keys apart, so it never shows the counties.
    queryKey: ["places", county || null, constituency || null, ward || null, enabled],
    enabled,
    // The server answers for the narrowest place given, so only that one is sent.
    queryFn: () => api(`/website/places/?${queryOf(ward ? { ward } : constituency ? { constituency } : { county })}`, { anonymous: true }),
    staleTime: Infinity,
  });

/** The places down to `level` (county, constituency, ward or centre) for the chosen place, each [] until loaded. */
export function usePlaceLists({ county, constituency, ward } = {}, level = "ward") {
  const depth = ["county", "constituency", "ward", "centre"].indexOf(level);
  const counties = usePlaces().data || [];
  const constituencies = usePlaces({ county, enabled: depth >= 1 && !!county }).data || [];
  const wards = usePlaces({ constituency, enabled: depth >= 2 && !!constituency }).data || [];
  const centres = usePlaces({ ward, enabled: depth >= 3 && !!ward }).data || [];
  return { counties, constituencies, wards, centres };
}

// The footer's news sign-up, its unsubscribe link, and the demo Contribute form.
export const useSubscribe = () =>
  useMutation({
    mutationFn: (payload) =>
      api("/website/subscribe/", { method: "POST", body: payload, anonymous: true }),
  });

export const useUnsubscribe = (code) =>
  useMutation({
    mutationFn: () =>
      api(`/website/unsubscribe/${encodeURIComponent(code)}/`, { method: "POST", anonymous: true }),
  });

// Saves the console's site settings form.
export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api("/admin/site/", { method: "PUT", body: payload }),
    onSuccess: (saved) => qc.setQueryData(["site"], saved),
  });
}

// ---- signed-in login ------------------------------------------------------
// Refreshes the stored user, so roles changed since sign-in take effect.
export function useMe() {
  const query = useQuery({ queryKey: ["me"], queryFn: () => api("/auth/me/") });
  const fresh = query.data;
  useEffect(() => {
    if (fresh && JSON.stringify(fresh) !== JSON.stringify(useAuth.getState().user)) {
      useAuth.setState({ user: fresh });
    }
  }, [fresh]);
  return query;
}

// ---- console lists, loaded 50 rows at a time ---------------------------------
// Each key starts like its single-page list's, so the same invalidations refresh it.

export const PAGE_ROWS = 50;

// The next offset of a plain list: more may follow while the last page came back full.
const nextPlain = (last, pages) => (last.length === PAGE_ROWS ? pages.length * PAGE_ROWS : undefined);

export const useAdminUserPages = (role) =>
  useInfiniteQuery({
    queryKey: ["admin", "users", "pages", role || "all"],
    queryFn: ({ pageParam }) => api(`/admin/users/?${queryOf({ role, limit: PAGE_ROWS, offset: pageParam })}`),
    initialPageParam: 0,
    getNextPageParam: nextPlain,
    placeholderData: keepPreviousData,
  });

export const useAuditPages = ({ action, actor, since, until }) =>
  useInfiniteQuery({
    queryKey: ["admin", "audit", "pages", action, actor, since, until],
    queryFn: ({ pageParam }) => api(`/admin/audit/?${queryOf({ action, actor, since, until, limit: PAGE_ROWS, offset: pageParam })}`),
    initialPageParam: 0,
    getNextPageParam: nextPlain,
  });

/** Every row of a paged list loaded so far, in order. */
export const rowsOf = (pages, read = (page) => page) => (pages?.pages || []).flatMap(read);

// ---- the campaign's volunteers ----------------------------------------------
// The private link that takes a volunteer off the campaign's list.
export const useVolunteerWithdraw = () =>
  useMutation({
    mutationFn: (code) => api(`/website/volunteer/withdraw/${code}/`, { method: "POST", anonymous: true }),
  });

// A campaign's volunteers from its candidate's website page; the manager's list.
export const useCampaignVolunteers = (campaignId) =>
  useFor("campaign-volunteers", campaignId, () => api(`/campaigns/${campaignId}/volunteers/`));

export const useUpdateCampaignVolunteer = (campaignId) =>
  useWriteSettled(
    ({ id, ...body }) => api(`/campaigns/${campaignId}/volunteers/${id}/`, { method: "PATCH", body }),
    "campaign-volunteers",
  );

// ---- the campaign website ----------------------------------------------------
export const useSiteCandidate = () =>
  useQuery({
    queryKey: ["site-candidate"],
    queryFn: () => api("/site/candidate/", { anonymous: true }),
    retry: false,
  });

export const useSiteVolunteer = () =>
  useMutation({
    mutationFn: (payload) => api("/site/volunteer/", { method: "POST", body: payload, anonymous: true }),
  });

// The workspace's website editor (site.write): one list, save and delete per kind of item.
const useWorkspaceWrite = (mutationFn) => useWriteSettled(mutationFn, "workspace-site", "site", "site-candidate");

/** One editor section: its list, save and delete hooks, and where its images go. */
const wsSection = (kind, list, add, change, remove) => ({
  upload: "/workspace/site/images/",
  query: function useList() { return useQuery({ queryKey: ["workspace-site", kind], queryFn: list }); },
  save: function useSave() { return useWorkspaceWrite(saveBy(add, change)); },
  del: function useDelete() { return useWorkspaceWrite(remove); },
});

export const WORKSPACE_SECTIONS = {
  posts: wsSection(
    "posts",
    () => api("/workspace/site/posts/"),
    (body) => api("/workspace/site/posts/", { method: "POST", body }),
    (id, body) => api(`/workspace/site/posts/${id}/`, { method: "PATCH", body }),
    (id) => api(`/workspace/site/posts/${id}/`, { method: "DELETE" }),
  ),
  slides: wsSection(
    "slides",
    () => api("/workspace/site/slides/"),
    (body) => api("/workspace/site/slides/", { method: "POST", body }),
    (id, body) => api(`/workspace/site/slides/${id}/`, { method: "PATCH", body }),
    (id) => api(`/workspace/site/slides/${id}/`, { method: "DELETE" }),
  ),
  issues: wsSection(
    "issues",
    () => api("/workspace/site/issues/"),
    (body) => api("/workspace/site/issues/", { method: "POST", body }),
    (id, body) => api(`/workspace/site/issues/${id}/`, { method: "PATCH", body }),
    (id) => api(`/workspace/site/issues/${id}/`, { method: "DELETE" }),
  ),
  documents: wsSection(
    "documents",
    () => api("/workspace/site/documents/"),
    (body) => api("/workspace/site/documents/", { method: "POST", body }),
    (id, body) => api(`/workspace/site/documents/${id}/`, { method: "PATCH", body }),
    (id) => api(`/workspace/site/documents/${id}/`, { method: "DELETE" }),
  ),
  videos: wsSection(
    "videos",
    () => api("/workspace/site/videos/"),
    (body) => api("/workspace/site/videos/", { method: "POST", body }),
    (id, body) => api(`/workspace/site/videos/${id}/`, { method: "PATCH", body }),
    (id) => api(`/workspace/site/videos/${id}/`, { method: "DELETE" }),
  ),
};

export const useWorkspaceSettings = () =>
  useQuery({ queryKey: ["workspace-site", "settings"], queryFn: () => api("/workspace/site/settings/") });

export const useSaveWorkspaceSettings = () =>
  useWorkspaceWrite((body) => api("/workspace/site/settings/", { method: "PUT", body }));

export const useWorkspaceCandidatePage = () =>
  useQuery({ queryKey: ["workspace-site", "candidate"], queryFn: () => api("/workspace/site/candidate/") });

export const useSaveWorkspaceCandidatePage = () =>
  useWorkspaceWrite((body) => api("/workspace/site/candidate/", { method: "PUT", body }));

// ---- team sign-up and agents ------------------------------------------------
// The public page behind a workspace's team link.
export const useTeamSignup = (code) =>
  useQuery({ queryKey: ["team-signup", code], queryFn: () => api(`/team-signup/${code}/`, { anonymous: true }), retry: false });

export const useSignupCentres = (code, ward) =>
  useQuery({
    queryKey: ["team-signup-centres", code, ward],
    queryFn: () => api(`/team-signup/${code}/centres/?ward=${ward}`, { anonymous: true }),
    enabled: !!ward,
  });

export const useSubmitSignup = (code) =>
  useMutation({ mutationFn: (body) => api(`/team-signup/${code}/`, { method: "POST", body, anonymous: true }) });

// Sign-ups the caller may decide, in one status.
export const useRegistrations = (campaignId, status) =>
  useQuery({
    queryKey: ["registrations", campaignId, status],
    queryFn: () => api(`/campaigns/${campaignId}/registrations/?status=${status}`),
    enabled: !!campaignId,
  });

export const useDecideRegistration = () =>
  useWrite(
    ({ campaign, id, decision, reason }) =>
      decision === "reject"
        ? api(`/campaigns/${campaign}/registrations/${id}/reject/`, { method: "POST", body: { reason } })
        : api(`/campaigns/${campaign}/registrations/${id}/approve/`, { method: "POST" }),
    "registrations", "team", "mobilizers", "agents", "agent-coverage",
  );

export const useTeamLink = (campaignId) => useFor("team-link", campaignId, () => api(`/campaigns/${campaignId}/team-link/`));

export const useReplaceTeamLink = () =>
  useReplace((campaignId) => api(`/campaigns/${campaignId}/team-link/`, { method: "POST" }), (campaignId) => ["team-link", campaignId]);

export const useAgents = (campaignId) => useFor("agents", campaignId, () => api(`/agents/?campaign=${campaignId}`));

export const useAgentCoverage = (campaignId) =>
  useFor("agent-coverage", campaignId, () => api(`/agents/coverage/?campaign=${campaignId}`));

export const useUpdateAgent = () =>
  useWrite(
    ({ id, ...body }) => api(`/agents/${id}/`, { method: "PATCH", body }),
    "agents", "agent-coverage",
  );

export const exportAgents = (campaignId) => download(`/agents/export/?campaign=${campaignId}`, "agents.csv");

// First-run setup: open before the installation exists; the token rides in a header for reads.
export const useCheckSetupToken = () =>
  useMutation({ mutationFn: (token) => api("/setup/check/", { method: "POST", body: { token }, anonymous: true }) });

export const useSetupAreas = (token, level, parent) =>
  useQuery({
    queryKey: ["setup-areas", level, parent],
    enabled: Boolean(token) && (level === "county" || Boolean(parent)),
    queryFn: () => api(`/setup/areas/?${queryOf({ level, parent })}`, { anonymous: true, headers: { "X-Setup-Token": token } }),
  });

// What setup will save as the seat's targets; worked out on the server, nothing saved.
export const useTargetPreview = (token, seat) =>
  useQuery({
    queryKey: ["setup-target-preview", seat],
    enabled: Boolean(token && seat.seat),
    queryFn: () => api("/setup/target-preview/", { method: "POST", body: seat, anonymous: true, headers: { "X-Setup-Token": token } }),
    staleTime: Infinity,
    retry: false,
  });

export const useRunSetup = () =>
  useMutation({ mutationFn: (body) => api("/setup/", { method: "POST", body, anonymous: true }) });

export const useSetupServices = (enabled) =>
  useQuery({ queryKey: ["setup-services"], enabled, queryFn: () => api("/setup/services/") });

export const useTestService = () =>
  useMutation({ mutationFn: (key) => api(`/setup/services/${key}/test/`, { method: "POST" }) });

// Reference data imports from the console; a dry run reports the changes and writes nothing.
export const useImportRuns = () =>
  useQuery({ queryKey: ["admin", "imports"], queryFn: () => api("/admin/imports/") });

export function useRunImport() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ kind, filename, csv, dry_run }) => {
      const body = { filename, csv, dry_run };
      return kind === "boundaries"
        ? api("/admin/imports/boundaries/", { method: "POST", body })
        : api("/admin/imports/register/", { method: "POST", body });
    },
    onSuccess: (report) => {
      if (report.applied) qc.invalidateQueries();
    },
  });
}

export const useRefreshTargets = () =>
  useWrite(
    (campaignId) => api("/targets/refresh/", { method: "POST", body: { campaign: campaignId } }),
    "targets", "strategy",
  );

// The console's Health, Audit and Export tabs.
export const useHealth = () =>
  useQuery({ queryKey: ["admin", "health"], queryFn: () => api("/admin/health/") });

export const useBackups = () =>
  useQuery({ queryKey: ["admin", "backups"], queryFn: () => api("/admin/backups/") });

export function useTestSend() {
  return useMutation({
    mutationFn: ({ kind, phone }) =>
      kind === "sms"
        ? api("/admin/test/sms/", { method: "POST", body: { phone } })
        : api("/admin/test/payout/", { method: "POST", body: { phone } }),
  });
}

// A public site image, sent to the workspace's file store.
export const useUploadImage = (path) => useMutation({ mutationFn: ({ file, area }) => upload(path, file, { area }) });

// ---- personal data: requests, erasure, withdrawal links, closing ------------
export const useDataRequests = (campaignId) =>
  useFor("data-requests", campaignId, () => api(`/campaigns/${campaignId}/data/requests/`));

export const useLogDataRequest = (campaignId) =>
  useWrite(
    (body) => api(`/campaigns/${campaignId}/data/requests/`, { method: "POST", body }),
    "data-requests",
  );

export const useUpdateDataRequest = (campaignId) =>
  useWrite(
    ({ id, ...body }) => api(`/campaigns/${campaignId}/data/requests/${id}/`, { method: "PATCH", body }),
    "data-requests",
  );

export const useLeftTeam = (campaignId) => useFor("left-team", campaignId, () => api(`/campaigns/${campaignId}/data/left-team/`));

const ERASE = {
  supporters: (campaignId, id) => api(`/campaigns/${campaignId}/data/supporters/${id}/erase/`, { method: "POST" }),
  volunteers: (campaignId, id) => api(`/campaigns/${campaignId}/data/volunteers/${id}/erase/`, { method: "POST" }),
  registrations: (campaignId, id) => api(`/campaigns/${campaignId}/data/registrations/${id}/erase/`, { method: "POST" }),
};

// kind is supporters, volunteers or registrations.
export const useErase = (campaignId, kind) =>
  useWrite((id) => ERASE[kind](campaignId, id), "supporters", "campaign-volunteers", "left-team", "data-close");

export const useWithdrawalLink = (campaignId, supporterId) =>
  useQuery({
    queryKey: ["withdrawal-link", supporterId],
    queryFn: () => api(`/campaigns/${campaignId}/data/supporters/${supporterId}/withdrawal/`),
    enabled: !!supporterId,
  });

export const useTextWithdrawalLink = (campaignId) =>
  useMutation({ mutationFn: (id) => api(`/campaigns/${campaignId}/data/supporters/${id}/withdrawal/`, { method: "POST" }) });

export const useCloseState = (campaignId) => useFor("data-close", campaignId, () => api(`/campaigns/${campaignId}/data/close/`));

export const useSetRetention = (campaignId) =>
  useWrite((retention_months) => api(`/campaigns/${campaignId}/data/retention/`, { method: "PUT", body: { retention_months } }), "data-close");

export const useCloseCampaign = (campaignId) =>
  useWrite(() => api(`/campaigns/${campaignId}/data/close/`, { method: "POST" }), "data-close", "campaigns");

export const useEraseSupporters = (campaignId) =>
  useWrite(() => api(`/campaigns/${campaignId}/data/erase-supporters/`, { method: "POST" }), "data-close", "supporters");

// ---- paying in by M-Pesa: the dialog's options, a contribution, and a
// payment's status while the dialog waits.
export const usePayOptions = () =>
  useQuery({ queryKey: ["pay-options"], queryFn: () => api("/pay/options/", { anonymous: true }) });

export const useContribute = () =>
  useMutation({ mutationFn: (body) => api("/pay/contribution/", { method: "POST", body, anonymous: true }) });

/** Polls every 3 seconds while the payment waits for the phone. */
export const usePayment = (reference) =>
  useQuery({
    queryKey: ["payment-in", reference],
    queryFn: () => api(`/pay/${reference}/`, { anonymous: true }),
    enabled: !!reference,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

// The campaign's list of money paid in.
export const usePaymentsIn = (campaignId, status) =>
  useQuery({
    queryKey: ["payments-in", campaignId, status],
    queryFn: () => api(`/campaigns/${campaignId}/payments-in/?status=${status}`),
  });

export const useDecidePaymentIn = (campaignId) =>
  useWrite(
    ({ id, reason }) =>
      reason === undefined
        ? api(`/campaigns/${campaignId}/payments-in/${id}/confirm/`, { method: "POST" })
        : api(`/campaigns/${campaignId}/payments-in/${id}/reject/`, { method: "POST", body: { reason } }),
    "payments-in",
  );
