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
export const useTargets = (campaignId) => useFor("targets", campaignId, () => api(`/targets/?campaign=${campaignId}`));

export const useEvents = (campaignId) => useFor("events", campaignId, () => api(`/events/?campaign=${campaignId}`));

export const useMobilizers = (campaignId) => useFor("mobilizers", campaignId, () => api(`/mobilizers/?campaign=${campaignId}`));

export const useSupporters = (campaignId) => useFor("supporters", campaignId, () => api(`/supporters/?campaign=${campaignId}`));

export const useConsentWording = () =>
  useQuery({
    queryKey: ["consent-wording"],
    queryFn: () => api("/supporters/consent-wording/"),
    staleTime: Infinity,
  });

export const useStrategy = (campaignId) => useFor("strategy", campaignId, () => api(`/strategy/?campaign=${campaignId}`));

// ---- Mutations ------------------------------------------------------------
export const useSetTarget = () =>
  useWrite(
    (payload) =>
      api("/targets/", { method: "POST", body: payload }),
    "targets", "strategy",
  );

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
    "messages",
  );

export const useSendMessage = () =>
  useWrite(
    (id) => api(`/messages/${id}/send/`, { method: "POST" }),
    "messages",
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
  });

export const useSettleAssignment = () =>
  useWriteSettled(
    ({ id, outcome }) =>
      outcome === "done"
        ? api(`/assignments/${id}/done/`, { method: "POST" })
        : api(`/assignments/${id}/cancel/`, { method: "POST" }),
    "assignments",
  );

// ---- geography pickers ----------------------------------------------------
export const useCounties = () =>
  useQuery({ queryKey: ["counties"], queryFn: () => api("/counties/") });

export const useConstituencies = (countyId) =>
  useFor("constituencies", countyId, () => api(`/constituencies/?county=${countyId}`));

export const useWardsIn = (constituencyId) =>
  useFor("wardsIn", constituencyId, () => api(`/wards/?constituency=${constituencyId}`));

// The user's campaign(s). For a single-campaign MVP, take the first.
export const useCampaigns = () =>
  useQuery({ queryKey: ["campaigns"], queryFn: () => api("/campaigns/") });

// Edit a target's turnout assumption; the server recomputes votes_needed.
// Saves run one at a time, in order, and the saved row replaces the cached one.
export function useUpdateTarget() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/targets/${id}/`, { method: "PATCH", body }),
    scope: { id: "targets" },
    onSuccess: async (saved) => {
      await qc.cancelQueries({ queryKey: ["targets"] });  // a list fetch in flight would overwrite it
      qc.setQueriesData({ queryKey: ["targets"] }, (rows) =>
        rows?.map((t) => (t.id === saved.id ? saved : t)),
      );
      qc.invalidateQueries({ queryKey: ["strategy"] });
    },
  });
}

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

// The aspirant adds the manager, or replaces the one there with `replace: true`.
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

// ---- site and party settings, party offices --------------------------------
export const useSite = () =>
  useQuery({
    queryKey: ["site"],
    queryFn: () => api("/site/", { anonymous: true }),
    // Before setup the answer is final: go to /setup at once.
    retry: (count, error) => error?.code !== "not_set_up" && count < 3,
  });

// The party-only settings, read only in a party installation; the rest are site settings.
export const useParty = (enabled = true) =>
  useQuery({ queryKey: ["party"], queryFn: () => api("/party/", { anonymous: true }), enabled });

export const PARTY_FIELDS = ["registration_number", "founded_year", "aspirant_steps"];

// ---- public website content ------------------------------------------------
export const usePublicLeaders = () =>
  useQuery({
    queryKey: ["public-leaders"],
    queryFn: () => api("/party/leaders/", { anonymous: true }),
  });

// Published news, newest first, 20 per page from `offset`, optionally one `label`;
// or events from today on, optionally in one `county`.
export const usePublicPosts = (kind, offset = 0, { label = "", county = "" } = {}) =>
  useQuery({
    queryKey: ["public-posts", kind, offset, label, county],
    queryFn: () => api(`/party/posts/?${queryOf({ kind, offset, label, county })}`, { anonymous: true }),
  });

export const usePublicPost = (id) =>
  useQuery({
    queryKey: ["public-post", id],
    queryFn: () => api(`/party/posts/${id}/`, { anonymous: true }),
  });

// The superuser's editing of the site's leaders and posts, drafts included.
export const useSiteLeaders = () =>
  useQuery({ queryKey: ["site", "leaders"], queryFn: () => api("/admin/party/leaders/") });

export const useSitePosts = () =>
  useQuery({ queryKey: ["site", "posts"], queryFn: () => api("/admin/party/posts/") });

// The editor's lists and every public page read.
const siteOrPublic = ({ queryKey: [key] }) => key === "site" || String(key).startsWith("public-");

function useSiteWrite(mutationFn) {
  const qc = useQueryClient();
  return useMutation({ mutationFn, onSettled: () => qc.invalidateQueries({ predicate: siteOrPublic }) });
}

export const useSaveLeader = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/leaders/", { method: "POST", body }),
    (id, body) => api(`/admin/party/leaders/${id}/`, { method: "PATCH", body }),
  ));

export const useDeleteLeader = () =>
  useSiteWrite((id) => api(`/admin/party/leaders/${id}/`, { method: "DELETE" }));

export const useSavePost = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/posts/", { method: "POST", body }),
    (id, body) => api(`/admin/party/posts/${id}/`, { method: "PATCH", body }),
  ));

export const useDeletePost = () =>
  useSiteWrite((id) => api(`/admin/party/posts/${id}/`, { method: "DELETE" }));

// The homepage's carousel slides and agenda issues: published ones, or all of them for the editor.
export const usePublicSlides = () =>
  useQuery({ queryKey: ["public-slides"], queryFn: () => api("/party/slides/", { anonymous: true }) });

export const usePublicIssues = () =>
  useQuery({ queryKey: ["public-issues"], queryFn: () => api("/party/issues/", { anonymous: true }) });

export const usePublicIssue = (id) =>
  useQuery({ queryKey: ["public-issues", id], queryFn: () => api(`/party/issues/${id}/`, { anonymous: true }) });

export const useSiteSlides = () =>
  useQuery({ queryKey: ["site", "slides"], queryFn: () => api("/admin/party/slides/") });

export const useSiteIssues = () =>
  useQuery({ queryKey: ["site", "issues"], queryFn: () => api("/admin/party/issues/") });

export const useSaveSlide = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/slides/", { method: "POST", body }),
    (id, body) => api(`/admin/party/slides/${id}/`, { method: "PATCH", body }),
  ));
export const useSaveIssue = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/issues/", { method: "POST", body }),
    (id, body) => api(`/admin/party/issues/${id}/`, { method: "PATCH", body }),
  ));
export const useDeleteSlide = () => useSiteWrite((id) => api(`/admin/party/slides/${id}/`, { method: "DELETE" }));
export const useDeleteIssue = () => useSiteWrite((id) => api(`/admin/party/issues/${id}/`, { method: "DELETE" }));

// Party documents linked from the About page: published ones, or all of them for the editor.
export const usePublicDocuments = () =>
  useQuery({ queryKey: ["public-documents"], queryFn: () => api("/party/documents/", { anonymous: true }) });

export const useSiteDocuments = () =>
  useQuery({ queryKey: ["site", "documents"], queryFn: () => api("/admin/party/documents/") });

export const useSaveDocument = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/documents/", { method: "POST", body }),
    (id, body) => api(`/admin/party/documents/${id}/`, { method: "PATCH", body }),
  ));
export const useDeleteDocument = () => useSiteWrite((id) => api(`/admin/party/documents/${id}/`, { method: "DELETE" }));

// The About page's values and party organs, and its member and branch counts.
export const usePublicValues = () =>
  useQuery({ queryKey: ["public-values"], queryFn: () => api("/party/values/", { anonymous: true }) });

export const usePublicOrgans = () =>
  useQuery({ queryKey: ["public-organs"], queryFn: () => api("/party/organs/", { anonymous: true }) });

export const usePartyStats = () =>
  useQuery({ queryKey: ["party-stats"], queryFn: () => api("/party/stats/", { anonymous: true }) });

export const useSiteValues = () =>
  useQuery({ queryKey: ["site", "values"], queryFn: () => api("/admin/party/values/") });

export const useSiteOrgans = () =>
  useQuery({ queryKey: ["site", "organs"], queryFn: () => api("/admin/party/organs/") });

export const useSaveValue = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/values/", { method: "POST", body }),
    (id, body) => api(`/admin/party/values/${id}/`, { method: "PATCH", body }),
  ));
export const useSaveOrgan = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/organs/", { method: "POST", body }),
    (id, body) => api(`/admin/party/organs/${id}/`, { method: "PATCH", body }),
  ));
export const useDeleteValue = () => useSiteWrite((id) => api(`/admin/party/values/${id}/`, { method: "DELETE" }));
export const useDeleteOrgan = () => useSiteWrite((id) => api(`/admin/party/organs/${id}/`, { method: "DELETE" }));

// The homepage's Watch row.
export const usePublicVideos = () =>
  useQuery({ queryKey: ["public-videos"], queryFn: () => api("/party/videos/", { anonymous: true }) });

export const useSiteVideos = () =>
  useQuery({ queryKey: ["site", "videos"], queryFn: () => api("/admin/party/videos/") });

export const useSaveVideo = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/videos/", { method: "POST", body }),
    (id, body) => api(`/admin/party/videos/${id}/`, { method: "PATCH", body }),
  ));
export const useDeleteVideo = () => useSiteWrite((id) => api(`/admin/party/videos/${id}/`, { method: "DELETE" }));

// Primary results: each row is one candidate's votes in one seat and area.
export const usePublicResults = () =>
  useQuery({ queryKey: ["public-results"], queryFn: () => api("/party/results/", { anonymous: true }) });

export const useSiteResults = () =>
  useQuery({ queryKey: ["site", "results"], queryFn: () => api("/admin/party/results/") });

export const useSaveResult = () =>
  useSiteWrite(saveBy(
    (body) => api("/admin/party/results/", { method: "POST", body }),
    (id, body) => api(`/admin/party/results/${id}/`, { method: "PATCH", body }),
  ));
export const useDeleteResult = () => useSiteWrite((id) => api(`/admin/party/results/${id}/`, { method: "DELETE" }));

// Counties, or one county's constituencies, or one constituency's wards.
export const usePartyPlaces = ({ county, constituency, ward, enabled = true } = {}) =>
  useQuery({
    // A lookup waiting for its place keys apart, so it never shows the counties.
    queryKey: ["party-places", county || null, constituency || null, ward || null, enabled],
    enabled,
    // The server answers for the narrowest place given, so only that one is sent.
    queryFn: () => api(`/party/places/?${queryOf(ward ? { ward } : constituency ? { constituency } : { county })}`, { anonymous: true }),
    staleTime: Infinity,
  });

/** The party's places down to `level` (county, constituency, ward or centre) for the chosen place, each [] until loaded. */
export function usePartyPlaceLists({ county, constituency, ward } = {}, level = "ward") {
  const depth = ["county", "constituency", "ward", "centre"].indexOf(level);
  const counties = usePartyPlaces().data || [];
  const constituencies = usePartyPlaces({ county, enabled: depth >= 1 && !!county }).data || [];
  const wards = usePartyPlaces({ constituency, enabled: depth >= 2 && !!constituency }).data || [];
  const centres = usePartyPlaces({ ward, enabled: depth >= 3 && !!ward }).data || [];
  return { counties, constituencies, wards, centres };
}

// County branches: published ones for the site, every county's for the superuser.
export const usePublicBranches = () =>
  useQuery({ queryKey: ["public-branches"], queryFn: () => api("/party/branches/", { anonymous: true }) });

export const usePublicBranch = (countyId) =>
  useQuery({
    queryKey: ["public-branches", countyId],
    queryFn: () => api(`/party/branches/${countyId}/`, { anonymous: true }),
  });

export const useSaveBranch = () =>
  useWrite(
    ({ county, ...payload }) => api(`/admin/party/branches/${county}/`, { method: "PUT", body: payload }),
    "office-branches", "public-branches",
  );

// The signed-in member's own account.
export const useAccount = () => useQuery({ queryKey: ["account"], queryFn: () => api("/account/") });

export const useChangeVolunteering = () =>
  useReplace((payload) => api("/account/volunteer/", { method: "PUT", body: payload }), ["account"]);

export const useStopVolunteering = () =>
  useReplace(() => api("/account/volunteer/stop/", { method: "POST" }), ["account"]);
export const useLeaveParty = () =>
  useMutation({ mutationFn: () => api("/account/leave/", { method: "POST" }) });

// The footer's news sign-up, its unsubscribe link, and the demo Contribute form.
export const useSubscribe = () =>
  useMutation({
    mutationFn: (payload) =>
      api("/party/subscribe/", { method: "POST", body: payload, anonymous: true }),
  });

export const useUnsubscribe = (code) =>
  useMutation({
    mutationFn: () =>
      api(`/party/unsubscribe/${encodeURIComponent(code)}/`, { method: "POST", anonymous: true }),
  });

export const useJoinParty = () =>
  useMutation({
    mutationFn: (payload) =>
      api("/party/join/", { method: "POST", body: payload, anonymous: true }),
  });

export function useWithdrawParty(code) {
  return useMutation({
    mutationFn: () =>
      api(`/party/withdraw/${encodeURIComponent(code)}/`, { method: "POST", anonymous: true }),
  });
}

export function useWithdrawVolunteer(code) {
  return useMutation({
    mutationFn: () =>
      api(`/party/volunteer/withdraw/${encodeURIComponent(code)}/`, { method: "POST", anonymous: true }),
  });
}

// Saves one settings form: the site fields, then, in a party installation, the party-only ones.
export function useSaveSettings({ party: withParty = true } = {}) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: async (payload) => {
      const party = Object.fromEntries(PARTY_FIELDS.map((key) => [key, payload[key]]));
      const site = Object.fromEntries(Object.entries(payload).filter(([key]) => !PARTY_FIELDS.includes(key)));
      const saved = await api("/admin/site/", { method: "PUT", body: site });
      if (!withParty) return { site: saved };
      return { site: saved, party: await api("/admin/party/", { method: "PUT", body: party }) };
    },
    onSuccess: (data) => {
      qc.setQueryData(["site"], data.site);
      if (data.party) qc.setQueryData(["party"], data.party);
    },
    // The site half may have saved before the party half failed.
    onError: () => qc.invalidateQueries({ queryKey: ["site"] }),
  });
}

export const useGrantPartyRole = () =>
  useWrite(({ user, role }) => api(`/admin/users/${user}/party-roles/`, { method: "POST", body: { role } }), "admin");

export const useRevokePartyRole = () =>
  useWrite(({ user, role }) => api(`/admin/users/${user}/party-roles/${role}/`, { method: "DELETE" }), "admin");

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

// ---- party member register ------------------------------------------------
// The superuser's party-wide counts; `from` and `to` bound events.
export const usePartyDashboard = (filters) =>
  useQuery({
    queryKey: ["party-dashboard", filters],
    queryFn: () => api(`/party/dashboard/?${queryOf(filters)}`),
    placeholderData: keepPreviousData,
  });

export const usePartyMembers = (filters, enabled = true) =>
  useQuery({
    queryKey: ["party-members", filters],
    queryFn: () => api(`/party/members/?${queryOf(filters)}`),
    placeholderData: keepPreviousData,
    enabled,
  });

/** Members matching `q` and `filters`, asked for only once `q` has two letters: [query, searching]. */
export function useMemberSearch(q, filters) {
  const term = q.trim();
  const searching = term.length >= 2;
  return [usePartyMembers({ q: term, ...filters }, searching), searching];
}

export const usePartyMember = (id) => useFor("party-member", id, () => api(`/party/members/${id}/`));

export const useMoveMember = () =>
  useWrite(
    ({ id, status, reason }) =>
      api(`/party/members/${id}/status/`, {
        method: "POST",
        body: reason ? { status, reason } : { status },
      }),
    "party-members", "party-member",
  );

export const exportPartyMembers = (filters) =>
  download(`/party/members/export.csv?${queryOf(filters)}`, "party-members.csv");

// ---- party volunteer register ---------------------------------------------
export const useUpdateVolunteer = () =>
  useWrite(
    ({ id, ...body }) =>
      api(`/party/volunteers/${id}/`, { method: "PATCH", body }),
    "party-volunteers",
  );

export const exportPartyVolunteers = (filters) =>
  download(`/party/volunteers/export.csv?${queryOf(filters)}`, "party-volunteers.csv");

// ---- nominations ----------------------------------------------------------
export const useAspirants = (filters) =>
  useQuery({
    queryKey: ["aspirants", filters],
    queryFn: () => api(`/party/aspirants/?${queryOf(filters)}`),
    placeholderData: keepPreviousData,
  });

export const usePartyVolunteers = (filters) =>
  useQuery({
    queryKey: ["party-volunteers", filters],
    queryFn: () => api(`/party/volunteers/?${queryOf(filters)}`),
    placeholderData: keepPreviousData,
  });

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

export const useAspirant = (id) => useFor("aspirant", id, () => api(`/party/aspirants/${id}/`));

export const useCandidates = (q) =>
  useQuery({
    queryKey: ["aspirant-candidates", q],
    queryFn: () => api(`/party/aspirants/candidates/?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length >= 2,
  });

export const useNominate = () =>
  useWrite(
    (body) => api("/party/aspirants/", { method: "POST", body }),
    "aspirants", "aspirant-candidates",
  );

export const useMoveAspirant = () =>
  useWrite(
    ({ id, status, reason }) =>
      api(`/party/aspirants/${id}/status/`, {
        method: "POST",
        body: reason ? { status, reason } : { status },
      }),
    "aspirants", "aspirant",
  );

export const useCreateWorkspace = () =>
  useWrite(
    ({ id, ...body }) =>
      api(`/party/aspirants/${id}/workspace/`, { method: "POST", body }),
    "aspirants", "aspirant",
  );

// ---- party console top bar -------------------------------------------------
export const usePartySearch = (q) =>
  useQuery({
    queryKey: ["party-search", q.trim()],
    enabled: q.trim().length >= 2,
    queryFn: () => api(`/party/search/?q=${encodeURIComponent(q.trim())}`),
  });

export const usePartyNotifications = () =>
  useQuery({
    queryKey: ["party-notifications"],
    queryFn: () => api("/party/notifications/"),
    refetchInterval: 60_000,
  });

export const useLinkPartyMember = () =>
  useWrite(({ user, member }) => api(`/admin/users/${user}/party-member/`, { method: "PUT", body: { member } }), "admin");

// Candidates on the website: the directory, one profile, and its "Support" form.
export const usePublicCandidates = ({ seat = "", county = "", q = "" } = {}) =>
  useQuery({
    queryKey: ["public-candidates", seat, county, q],
    queryFn: () => api(`/candidates/?${queryOf({ seat, county, q })}`, { anonymous: true }),
  });

export const usePublicCandidate = (slug) =>
  useQuery({
    queryKey: ["public-candidates", "one", slug],
    queryFn: () => api(`/candidates/${slug}/`, { anonymous: true }),
    enabled: !!slug,
  });

export const useCandidateVolunteer = (slug) =>
  useMutation({
    mutationFn: (payload) => api(`/candidates/${slug}/volunteer/`, { method: "POST", body: payload, anonymous: true }),
  });

export const useCandidateWithdraw = () =>
  useMutation({
    mutationFn: (code) => api(`/candidates/volunteer/withdraw/${code}/`, { method: "POST", anonymous: true }),
  });

// The website editor's candidates: approved aspirants and their profiles, and an event's aspirants.
export const useSiteCandidates = () =>
  useQuery({ queryKey: ["site", "candidates"], queryFn: () => api("/admin/party/candidates/") });

export const useSaveProfile = () =>
  useSiteWrite(({ aspirant_id, ...body }) =>
    api(`/admin/party/candidates/${aspirant_id}/profile/`, { method: "PUT", body }),
  );

export const usePostAspirants = (postId) =>
  useQuery({
    queryKey: ["site", "post-aspirants", postId],
    queryFn: () => api(`/admin/party/posts/${postId}/aspirants/`),
    enabled: !!postId,
  });

export const useSavePostAspirants = () =>
  useSiteWrite(({ id, aspirant_ids }) =>
    api(`/admin/party/posts/${id}/aspirants/`, { method: "PUT", body: { aspirant_ids } }),
  );

// A campaign's volunteers from its candidate's website page; the manager's list.
export const useCampaignVolunteers = (campaignId) =>
  useFor("campaign-volunteers", campaignId, () => api(`/campaigns/${campaignId}/volunteers/`));

export const useUpdateCampaignVolunteer = (campaignId) =>
  useWriteSettled(
    ({ id, ...body }) => api(`/campaigns/${campaignId}/volunteers/${id}/`, { method: "PATCH", body }),
    "campaign-volunteers",
  );


// ---- an aspirant installation's website ------------------------------------
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

// ---- the party workspace: opening it, and its coordinators' members and link
// `id` is null until the workspace is opened.
export const usePartyWorkspace = (enabled) =>
  useQuery({ queryKey: ["admin", "party-workspace"], queryFn: () => api("/party/workspace/"), enabled });

/** Opens the party workspace, or with `replace` gives it a new Workspace Manager. */
export function useOpenPartyWorkspace({ onInvite, replace = false } = {}) {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ manager }) =>
      replace
        ? api("/party/workspace/manager/", { method: "POST", body: { manager } })
        : api("/party/workspace/", { method: "POST", body: { manager } }),
    onSuccess: (data) => {
      onInvite?.(data);
      return invalidate("admin");
    },
  });
}

export const useAreaMembers = (page) =>
  useQuery({
    queryKey: ["area-members", page],
    queryFn: () => api(`/party/workspace/members/?page=${page}`),
    placeholderData: keepPreviousData,
  });

export const useRecruitment = () =>
  useQuery({ queryKey: ["recruitment"], queryFn: () => api("/party/workspace/recruitment/") });

export const useReplaceRecruitment = () =>
  useReplace(() => api("/party/workspace/recruitment/", { method: "POST" }), ["recruitment"]);

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

// The party office's branches, for the Membership Officer and the superuser.
export const useOfficeBranches = () =>
  useQuery({ queryKey: ["office-branches"], queryFn: () => api("/party/office/branches/") });

// Branch officials: terms in each county branch office.
export const useBranchOfficials = (countyId) =>
  useFor("branch-officials", countyId, () => api(`/party/office/branches/${countyId}/officials/`));

export const useAppointOfficial = () =>
  useWrite(
    ({ county, ...body }) => api(`/party/office/branches/${county}/officials/`, { method: "POST", body }),
    "branch-officials", "office-branches", "public-branches",
  );

export const useEndTerm = () =>
  useWrite(
    ({ id, ...body }) => api(`/party/office/officials/${id}/end/`, { method: "POST", body }),
    "branch-officials", "office-branches", "public-branches",
  );

export const useUploadMinutes = () => useMutation({ mutationFn: (file) => upload("/party/office/minutes/", file) });
// A public site image, sent to the party's file store or to an aspirant workspace's.
export const useUploadImage = (path) => useMutation({ mutationFn: ({ file, area }) => upload(path, file, { area }) });

// Applying to vie: the published timetable, a member's own application, and the officer's side.
export const useNominationNotice = () =>
  useQuery({ queryKey: ["nominations", "current"], queryFn: () => api("/party/nominations/current/") });

export const useMyNomination = () =>
  useQuery({ queryKey: ["nominations", "mine"], queryFn: () => api("/party/nominations/mine/") });

const useMine = (mutationFn) => useReplace(mutationFn, ["nominations", "mine"]);

export const useApplyToVie = () => useMine((seat) => api("/party/nominations/mine/", { method: "POST", body: { seat } }));
export const useAttachNominationDocument = () =>
  useMine(({ file, label }) => upload("/party/nominations/mine/documents/", file, { label }));
export const useDetachNominationDocument = () =>
  useWrite(
    (id) => api(`/party/nominations/mine/documents/${id}/`, { method: "DELETE" }),
    "nominations",
  );
export const useSubmitNomination = () =>
  useMine(() => api("/party/nominations/mine/submit/", { method: "POST", body: { declaration: true } }));
export const useWithdrawNomination = () => useMine(() => api("/party/nominations/mine/withdraw/", { method: "POST" }));

export const useNominationWindows = () =>
  useQuery({ queryKey: ["nominations", "windows"], queryFn: () => api("/party/nominations/windows/") });

export const useDraftNominationWindow = () =>
  useWrite(
    (body) => api("/party/nominations/windows/", { method: "POST", body }),
    "nominations",
  );

export const useReviseNominationWindow = () =>
  useWrite(
    ({ id, body }) => api(`/party/nominations/windows/${id}/`, { method: "PUT", body }),
    "nominations",
  );

export const usePublishNominationWindow = () =>
  useWrite(
    (id) => api(`/party/nominations/windows/${id}/publish/`, { method: "POST" }),
    "nominations",
  );

export const useMarkNominationFeePaid = () =>
  useWrite(
    ({ id, reference }) => api(`/party/nominations/applications/${id}/fee/`, { method: "POST", body: { reference } }),
    "aspirants", "aspirant",
  );

// A hosted workspace's party feed and what it shares; the party's view of those counts.
export const usePartyFeed = (campaignId) => useFor("party-feed", campaignId, () => api(`/party-feed/?campaign=${campaignId}`));

export const useChangeSharing = (campaignId) =>
  useWrite(
    (body) => api(`/party-feed/sharing/?campaign=${campaignId}`, { method: "PUT", body }),
    "party-feed",
  );

export const usePartyShared = () => useQuery({ queryKey: ["party-shared"], queryFn: () => api("/party/shared/") });

// The party office's texts to members and volunteers.
export const usePartyMessages = () => useQuery({ queryKey: ["party-messages"], queryFn: () => api("/party/messages/") });

export const usePartyMessageReach = ({ audience, county, constituency, ward }) =>
  useQuery({
    queryKey: ["party-messages", "reach", audience, county, constituency, ward],
    queryFn: () => api("/party/messages/preview/", { method: "POST", body: { audience, county, constituency, ward } }),
    placeholderData: (previous) => previous,
  });

export const useDraftPartyMessage = () =>
  useWrite(({ audience, county, constituency, ward, body }) => api("/party/messages/", { method: "POST", body: { audience, county, constituency, ward, body } }), "party-messages");
export const useSendPartyMessage = () => useWrite((id) => api(`/party/messages/${id}/send/`, { method: "POST" }), "party-messages");
export const useDeclinePartyMessage = () =>
  useWrite(({ id, note }) => api(`/party/messages/${id}/decline/`, { method: "POST", body: { note } }), "party-messages");

// ---- personal data: requests, erasure, withdrawal links, closing ------------
// `campaignId` undefined is the party's own requests (Membership Officer).
export const useDataRequests = (campaignId) =>
  useQuery({
    queryKey: ["data-requests", campaignId ?? "party"],
    queryFn: () => (campaignId ? api(`/campaigns/${campaignId}/data/requests/`) : api("/party/data-requests/")),
  });


export const useLogDataRequest = (campaignId) =>
  useWrite(
    (body) =>
      campaignId
        ? api(`/campaigns/${campaignId}/data/requests/`, { method: "POST", body })
        : api("/party/data-requests/", { method: "POST", body }),
    "data-requests",
  );

export const useUpdateDataRequest = (campaignId) =>
  useWrite(
    ({ id, ...body }) =>
      campaignId
        ? api(`/campaigns/${campaignId}/data/requests/${id}/`, { method: "PATCH", body })
        : api(`/party/data-requests/${id}/`, { method: "PATCH", body }),
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

export const useEraseMember = () =>
  useWrite((id) => api(`/party/members/${id}/erase/`, { method: "POST" }), "party-members", "party-member", "party-volunteers");

export const useErasePartyVolunteer = () =>
  useWrite((id) => api(`/party/volunteers/${id}/erase/`, { method: "POST" }), "party-volunteers");

// ---- paying in by M-Pesa: the dialog's options, a contribution, a member's fee, and a
// payment's status while the dialog waits.
export const usePayOptions = () =>
  useQuery({ queryKey: ["pay-options"], queryFn: () => api("/pay/options/", { anonymous: true }) });

export const useContribute = () =>
  useMutation({ mutationFn: (body) => api("/pay/contribution/", { method: "POST", body, anonymous: true }) });

export const usePayFee = () =>
  useWrite(
    (body) => api("/party/nominations/mine/pay/", { method: "POST", body }),
    "nominations",
  );

/** Polls every 3 seconds while the payment waits for the phone. */
export const usePayment = (reference) =>
  useQuery({
    queryKey: ["payment-in", reference],
    queryFn: () => api(`/pay/${reference}/`, { anonymous: true }),
    enabled: !!reference,
    refetchInterval: (query) => (query.state.data?.status === "pending" ? 3000 : false),
  });

// The office's list of money paid in: a workspace's (`campaignId`) or, without one, the party's.
export const usePaymentsIn = (campaignId, status) =>
  useQuery({
    queryKey: ["payments-in", campaignId || "party", status],
    queryFn: () =>
      campaignId
        ? api(`/campaigns/${campaignId}/payments-in/?status=${status}`)
        : api(`/party/payments-in/?status=${status}`),
  });

export const useDecidePaymentIn = (campaignId) =>
  useWrite(
    ({ id, reason }) => {
      if (campaignId) {
        return reason === undefined
          ? api(`/campaigns/${campaignId}/payments-in/${id}/confirm/`, { method: "POST" })
          : api(`/campaigns/${campaignId}/payments-in/${id}/reject/`, { method: "POST", body: { reason } });
      }
      return reason === undefined
        ? api(`/party/payments-in/${id}/confirm/`, { method: "POST" })
        : api(`/party/payments-in/${id}/reject/`, { method: "POST", body: { reason } });
    },
    "payments-in", "nominations", "aspirants", "aspirant",
  );
