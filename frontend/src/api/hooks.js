// src/api/hooks.js
// React Query hooks. Queries read; mutations write and then invalidate the
// caches that changed — e.g. scheduling an event refreshes both the event list
// AND the strategy read, because the strategy is computed from events.

import { useEffect } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, download, upload } from "./client";
import { useAuth } from "../store/auth";

// ---- Queries --------------------------------------------------------------
export const useWards = () =>
  useQuery({ queryKey: ["wards"], queryFn: () => api("/wards/") });

export const useTargets = (campaignId) =>
  useQuery({
    queryKey: ["targets", campaignId],
    queryFn: () => api(`/targets/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

export const useEvents = (campaignId) =>
  useQuery({
    queryKey: ["events", campaignId],
    queryFn: () => api(`/events/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

export const useMobilizers = (campaignId) =>
  useQuery({
    queryKey: ["mobilizers", campaignId],
    queryFn: () => api(`/mobilizers/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

export const useSupporters = (campaignId) =>
  useQuery({
    queryKey: ["supporters", campaignId],
    queryFn: () => api(`/supporters/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

export const useConsentWording = () =>
  useQuery({
    queryKey: ["consent-wording"],
    queryFn: () => api("/supporters/consent-wording/"),
    staleTime: Infinity,
  });

export const useStrategy = (campaignId) =>
  useQuery({
    queryKey: ["strategy", campaignId],
    queryFn: () => api(`/strategy/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

// ---- Mutations ------------------------------------------------------------
function useInvalidator() {
  const qc = useQueryClient();
  return (...keys) =>
    keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function useSetTarget() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/targets/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("targets", "strategy"),
  });
}

export function useAddMobilizer() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/mobilizers/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("mobilizers", "strategy"),
  });
}

// Rename a mobilizer, or move them to a unit or to none; the server frees the unit's last holder.
export function useUpdateMobilizer() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/mobilizers/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidate("mobilizers", "strategy"),
  });
}

export function useScheduleEvent() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/events/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("events", "strategy"),
  });
}

export function useRecordEvent() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, number_reached, number_attended }) =>
      api(`/events/${id}/record/`, {
        method: "POST",
        body: { number_reached, number_attended },
      }),
    onSuccess: () => invalidate("events", "strategy"),
  });
}

// A supporter the team registers by hand; progress counts them at once.
export function useRegisterSupporter() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/supporters/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("supporters", "strategy"),
  });
}

// Put a supporter at a centre with a target, so they count toward it.
export function usePlaceSupporter() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, registration_centre }) =>
      api(`/supporters/${id}/`, { method: "PATCH", body: { registration_centre } }),
    onSuccess: () => invalidate("supporters", "strategy"),
  });
}

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
  useQuery({
    queryKey: ["campaignSignups", campaignId],
    queryFn: () => api(`/campaigns/${campaignId}/signups/`),
    enabled: !!campaignId,
  });

export function useSetCampaignSignups() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, open }) =>
      api(`/campaigns/${campaign}/signups/`, { method: "POST", body: { open } }),
    onSuccess: () => invalidate("campaignSignups"),
  });
}

export function useSetSignups() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, open }) =>
      api(`/events/${id}/signups/`, { method: "POST", body: { open } }),
    onSuccess: () => invalidate("events"),
  });
}

// ---- Payments to mobilizers ----------------------------------------------
export const usePayments = (campaignId) =>
  useQuery({
    queryKey: ["payments", campaignId],
    queryFn: () => api(`/payments/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

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

export function useReconcileNow() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId) => api(`/payments/reconciliation/?campaign=${campaignId}`, { method: "POST" }),
    onSuccess: (data, campaignId) => qc.setQueryData(["payments", "reconciliation", campaignId], data),
  });
}

export function useReleasePayment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id }) => api(`/payments/${id}/release/`, { method: "POST" }),
    onSettled: () => invalidate("payments"),
  });
}

export function useMarkNotSent() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id }) => api(`/payments/${id}/not-sent/`, { method: "POST" }),
    onSettled: () => invalidate("payments"),
  });
}

export function useSchedulePayment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/payments/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("payments"),
  });
}

export function useMarkPaid() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, reference }) =>
      api(`/payments/${id}/paid/`, { method: "POST", body: { reference } }),
    onSettled: () => invalidate("payments"),  // a refused change may mean the row moved on
  });
}

// Refuses a payment with a reason; its assignment can be paid by a new one.
export function useDeclinePayment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, reason }) => api(`/payments/${id}/decline/`, { method: "POST", body: { reason } }),
    onSettled: () => invalidate("payments"),  // a refused change may mean the row moved on
  });
}

// ---- assignments ------------------------------------------------------------
export const useAssignments = (campaignId, status) =>
  useQuery({
    queryKey: ["assignments", campaignId, status],
    queryFn: () => api(`/assignments/?campaign=${campaignId}${status ? `&status=${status}` : ""}`),
    enabled: !!campaignId,
  });

export function useCreateAssignment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api("/assignments/", { method: "POST", body }),
    onSuccess: () => invalidate("assignments"),
  });
}

// Texts to supporters: drafts, approval and the delivery log.
export const useMessages = (campaignId) =>
  useQuery({
    queryKey: ["messages", campaignId],
    queryFn: () => api(`/messages/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

// Who a message to these wards would reach now; the wording does not change it.
export const useMessageReach = (campaignId, wards) =>
  useQuery({
    queryKey: ["messages", "reach", campaignId, wards],
    queryFn: () => api("/messages/preview/", { method: "POST", body: { campaign: campaignId, wards, body: "-" } }),
    enabled: !!campaignId,
    placeholderData: (previous) => previous,
  });

export function useDraftMessage() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api("/messages/", { method: "POST", body }),
    onSuccess: () => invalidate("messages"),
  });
}

export function useSendMessage() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (id) => api(`/messages/${id}/send/`, { method: "POST" }),
    onSuccess: () => invalidate("messages"),
  });
}

export function useDeclineMessage() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, note }) => api(`/messages/${id}/decline/`, { method: "POST", body: { note } }),
    onSuccess: () => invalidate("messages"),
  });
}

export function useDeleteMessage() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (id) => api(`/messages/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidate("messages"),
  });
}

export const useMessageLog = (id) =>
  useQuery({
    queryKey: ["messages", "log", id],
    queryFn: () => api(`/messages/${id}/log/`),
    enabled: !!id,
  });

export function useSettleAssignment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, outcome }) =>
      outcome === "done"
        ? api(`/assignments/${id}/done/`, { method: "POST" })
        : api(`/assignments/${id}/cancel/`, { method: "POST" }),
    onSettled: () => invalidate("assignments"),
  });
}

// ---- geography pickers ----------------------------------------------------
export const useCounties = () =>
  useQuery({ queryKey: ["counties"], queryFn: () => api("/counties/") });

export const useConstituencies = (countyId) =>
  useQuery({
    queryKey: ["constituencies", countyId],
    queryFn: () => api(`/constituencies/?county=${countyId}`),
    enabled: !!countyId,
  });

export const useWardsIn = (constituencyId) =>
  useQuery({
    queryKey: ["wardsIn", constituencyId],
    queryFn: () => api(`/wards/?constituency=${constituencyId}`),
    enabled: !!constituencyId,
  });

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
export const useCentres = (wardId) =>
  useQuery({
    queryKey: ["centres", wardId],
    queryFn: () => api(`/centres/?ward=${wardId}`),
    enabled: !!wardId,
  });

export const useWardsInCounty = (countyId) =>
  useQuery({
    queryKey: ["wardsInCounty", countyId],
    queryFn: () => api(`/wards/?county=${countyId}`),
    enabled: !!countyId,
  });

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
export function useCreateUser() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/users/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("team", "mobilizers", "strategy"),
  });
}

// ---- the campaign's own team ----------------------------------------------
export const useTeam = (campaignId) =>
  useQuery({
    queryKey: ["team", campaignId],
    queryFn: () => api(`/campaigns/${campaignId}/team/`),
    enabled: !!campaignId,
  });

// The aspirant adds the manager, or replaces the one there with `replace: true`.
export function useSetManager() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, ...body }) =>
      api(`/campaigns/${campaign}/team/manager/`, { method: "POST", body }),
    onSuccess: () => invalidate("team"),
  });
}

// Adds a coordinator or comms officer; the password comes back once.
export function useAddStaff() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, ...body }) =>
      api(`/campaigns/${campaign}/team/`, { method: "POST", body }),
    onSuccess: () => invalidate("team"),
  });
}

// Takes a coordinator or comms officer off the campaign; their login is turned off.
export function useRemoveStaff() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, user }) =>
      api(`/campaigns/${campaign}/team/${user}/`, { method: "DELETE" }),
    onSuccess: () => invalidate("team"),
  });
}

// A coordinator's area: the wards and registration centres they cover.
export const useArea = (campaignId, userId) =>
  useQuery({
    queryKey: ["area", campaignId, userId],
    queryFn: () => api(`/campaigns/${campaignId}/team/${userId}/area/`),
    enabled: !!campaignId && !!userId,
  });

export function useSetArea() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, user, ...body }) =>
      api(`/campaigns/${campaign}/team/${user}/area/`, { method: "PUT", body }),
    onSuccess: () => invalidate("area"),
  });
}

// ---- sign-in links ---------------------------------------------------------
// The same answer whether or not the address has a login.
export const useRequestReset = () =>
  useMutation({
    mutationFn: (email) => api("/auth/password-reset/", { method: "POST", body: { email }, anonymous: true }),
  });

// What a sign-in link is for and whose login it sets; an error when it is spent.
export const useLink = (token) =>
  useQuery({
    queryKey: ["link", token],
    queryFn: () => api(`/auth/links/${token}/`, { anonymous: true }),
    retry: false,
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
    queryFn: () =>
      role ? api(`/admin/users/?role=${role}`) : api("/admin/users/"),
    // Each filter is its own key. Without this the list empties while the next
    // one loads and the console says nobody matches.
    placeholderData: keepPreviousData,
  });

// The password comes back once, so it is handed to the hook's owner rather
// than to the form, which unmounts as soon as the list refetches.
export function useCreateLogin({ onPassword } = {}) {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/admin/users/", { method: "POST", body: payload }),
    onSuccess: (data) => {
      onPassword?.(data);
      return invalidate();
    },
  });
}

function useAdminInvalidator() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["admin"] });
}

// Emails the login a reset link. Every callback runs on whoever owns the hook,
// and is handed the id it was about: React Query drops per-call callbacks when
// the calling component unmounts, and a row unmounts whenever the list
// refetches or the filter changes. A shared mutation also only remembers its latest call, so the caller
// has to key what it keeps by id rather than read `error` or `isPending` here.
export function useResetPassword({ onPassword, onFailed, onDone } = {}) {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ id }) => api(`/admin/users/${id}/reset-password/`, { method: "POST" }),
    onSuccess: (data, variables) => {
      onPassword?.(data, variables);
      return invalidate();
    },
    onError: (error, variables) => onFailed?.(error, variables),
    onSettled: (_data, _error, variables) => onDone?.(variables),
  });
}

export function useSetActive() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ id, active }) =>
      api(`/admin/users/${id}/active/`, { method: "POST", body: { active } }),
    onSuccess: invalidate,
  });
}

export function useSetEmail() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ id, email }) =>
      api(`/admin/users/${id}/email/`, { method: "PUT", body: { email } }),
    onSuccess: invalidate,
  });
}

export function useRenameCampaign() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ campaign, title }) =>
      api(`/admin/campaigns/${campaign}/`, {
        method: "PATCH",
        body: { title },
      }),
    onSuccess: invalidate,
  });
}

// Only a superuser deletes a campaign; nothing inside one can.
export function useDeleteCampaign() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ campaign }) =>
      api(`/admin/campaigns/${campaign}/`, { method: "DELETE" }),
    // A 404 means somebody else deleted it, so the list is stale either way.
    onSettled: invalidate,
  });
}

export function useAddMember() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    // No role: the place somebody takes is their login's, and the server
    // refuses a payload that says otherwise.
    mutationFn: ({ campaign, user }) =>
      api(`/admin/campaigns/${campaign}/members/`, {
        method: "POST",
        body: { user },
      }),
    onSuccess: invalidate,
  });
}

export function useRemoveMember() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ campaign, user }) =>
      api(`/admin/campaigns/${campaign}/members/${user}/`, {
        method: "DELETE",
      }),
    onSuccess: invalidate,
  });
}

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

const PARTY_FIELDS = ["registration_number", "founded_year", "aspirant_steps"];

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
    queryFn: () => {
      const only = `${label ? `&label=${label}` : ""}${county ? `&county=${county}` : ""}`;
      return api(`/party/posts/?kind=${kind}&offset=${offset}${only}`, { anonymous: true });
    },
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

function useSiteWrite(mutationFn) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["site"] });
      qc.invalidateQueries({ queryKey: ["public-leaders"] });
      qc.invalidateQueries({ queryKey: ["public-posts"] });
      qc.invalidateQueries({ queryKey: ["public-slides"] });
      qc.invalidateQueries({ queryKey: ["public-issues"] });
      qc.invalidateQueries({ queryKey: ["public-documents"] });
      qc.invalidateQueries({ queryKey: ["public-values"] });
      qc.invalidateQueries({ queryKey: ["public-organs"] });
      qc.invalidateQueries({ queryKey: ["public-results"] });
      qc.invalidateQueries({ queryKey: ["public-videos"] });
      qc.invalidateQueries({ queryKey: ["public-candidates"] });
    },
  });
}

// With an `id` the row is changed, without one it is added.
export const useSaveLeader = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/leaders/${id}/`, { method: "PATCH", body })
      : api("/admin/party/leaders/", { method: "POST", body }),
  );

export const useDeleteLeader = () =>
  useSiteWrite((id) => api(`/admin/party/leaders/${id}/`, { method: "DELETE" }));

export const useSavePost = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/posts/${id}/`, { method: "PATCH", body })
      : api("/admin/party/posts/", { method: "POST", body }),
  );

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
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/slides/${id}/`, { method: "PATCH", body })
      : api("/admin/party/slides/", { method: "POST", body }),
  );
export const useSaveIssue = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/issues/${id}/`, { method: "PATCH", body })
      : api("/admin/party/issues/", { method: "POST", body }),
  );
export const useDeleteSlide = () => useSiteWrite((id) => api(`/admin/party/slides/${id}/`, { method: "DELETE" }));
export const useDeleteIssue = () => useSiteWrite((id) => api(`/admin/party/issues/${id}/`, { method: "DELETE" }));

// Party documents linked from the About page: published ones, or all of them for the editor.
export const usePublicDocuments = () =>
  useQuery({ queryKey: ["public-documents"], queryFn: () => api("/party/documents/", { anonymous: true }) });

export const useSiteDocuments = () =>
  useQuery({ queryKey: ["site", "documents"], queryFn: () => api("/admin/party/documents/") });

export const useSaveDocument = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/documents/${id}/`, { method: "PATCH", body })
      : api("/admin/party/documents/", { method: "POST", body }),
  );
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
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/values/${id}/`, { method: "PATCH", body })
      : api("/admin/party/values/", { method: "POST", body }),
  );
export const useSaveOrgan = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/organs/${id}/`, { method: "PATCH", body })
      : api("/admin/party/organs/", { method: "POST", body }),
  );
export const useDeleteValue = () => useSiteWrite((id) => api(`/admin/party/values/${id}/`, { method: "DELETE" }));
export const useDeleteOrgan = () => useSiteWrite((id) => api(`/admin/party/organs/${id}/`, { method: "DELETE" }));

// The homepage's Watch row.
export const usePublicVideos = () =>
  useQuery({ queryKey: ["public-videos"], queryFn: () => api("/party/videos/", { anonymous: true }) });

export const useSiteVideos = () =>
  useQuery({ queryKey: ["site", "videos"], queryFn: () => api("/admin/party/videos/") });

export const useSaveVideo = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/videos/${id}/`, { method: "PATCH", body })
      : api("/admin/party/videos/", { method: "POST", body }),
  );
export const useDeleteVideo = () => useSiteWrite((id) => api(`/admin/party/videos/${id}/`, { method: "DELETE" }));

// Primary results: each row is one candidate's votes in one seat and area.
export const usePublicResults = () =>
  useQuery({ queryKey: ["public-results"], queryFn: () => api("/party/results/", { anonymous: true }) });

export const useSiteResults = () =>
  useQuery({ queryKey: ["site", "results"], queryFn: () => api("/admin/party/results/") });

export const useSaveResult = () =>
  useSiteWrite(({ id, ...body }) =>
    id
      ? api(`/admin/party/results/${id}/`, { method: "PATCH", body })
      : api("/admin/party/results/", { method: "POST", body }),
  );
export const useDeleteResult = () => useSiteWrite((id) => api(`/admin/party/results/${id}/`, { method: "DELETE" }));

// Counties, or one county's constituencies, or one constituency's wards.
export const usePartyPlaces = ({ county, constituency, ward, enabled = true } = {}) =>
  useQuery({
    // A lookup waiting for its place keys apart, so it never shows the counties.
    queryKey: ["party-places", county || null, constituency || null, ward || null, enabled],
    enabled,
    queryFn: () => {
      if (ward) return api(`/party/places/?ward=${ward}`, { anonymous: true });
      if (constituency) return api(`/party/places/?constituency=${constituency}`, { anonymous: true });
      if (county) return api(`/party/places/?county=${county}`, { anonymous: true });
      return api("/party/places/", { anonymous: true });
    },
    staleTime: Infinity,
  });

// County branches: published ones for the site, every county's for the superuser.
export const usePublicBranches = () =>
  useQuery({ queryKey: ["public-branches"], queryFn: () => api("/party/branches/", { anonymous: true }) });

export const usePublicBranch = (countyId) =>
  useQuery({
    queryKey: ["public-branches", countyId],
    queryFn: () => api(`/party/branches/${countyId}/`, { anonymous: true }),
  });

export function useSaveBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ county, ...payload }) =>
      api(`/admin/party/branches/${county}/`, { method: "PUT", body: payload }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-branches"] });
      qc.invalidateQueries({ queryKey: ["office-branches"] });
      qc.invalidateQueries({ queryKey: ["public-branches"] });
    },
  });
}

// The signed-in member's own account.
export const useAccount = () => useQuery({ queryKey: ["account"], queryFn: () => api("/account/") });

export function useChangeVolunteering() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api("/account/volunteer/", { method: "PUT", body: payload }),
    onSuccess: (account) => qc.setQueryData(["account"], account),
  });
}

export function useStopVolunteering() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/account/volunteer/stop/", { method: "POST" }),
    onSuccess: (account) => qc.setQueryData(["account"], account),
  });
}
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

export function useGrantPartyRole() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ user, role }) =>
      api(`/admin/users/${user}/party-roles/`, {
        method: "POST",
        body: { role },
      }),
    onSuccess: invalidate,
  });
}

export function useRevokePartyRole() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ user, role }) =>
      api(`/admin/users/${user}/party-roles/${role}/`, { method: "DELETE" }),
    onSuccess: invalidate,
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

// ---- party member register ------------------------------------------------
const memberQuery = (filters) => {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(filters || {})) {
    if (value !== "" && value != null) params.set(key, value);
  }
  return params.toString();
};

// The superuser's party-wide counts; `from` and `to` bound events.
export const usePartyDashboard = (filters) =>
  useQuery({
    queryKey: ["party-dashboard", filters],
    queryFn: () => api(`/party/dashboard/?${memberQuery(filters)}`),
    placeholderData: keepPreviousData,
  });

export const usePartyMembers = (filters) =>
  useQuery({
    queryKey: ["party-members", filters],
    queryFn: () => api(`/party/members/?${memberQuery(filters)}`),
    placeholderData: keepPreviousData,
  });

export const usePartyMember = (id) =>
  useQuery({
    queryKey: ["party-member", id],
    queryFn: () => api(`/party/members/${id}/`),
    enabled: !!id,
  });

export function useMoveMember() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, status, reason }) =>
      api(`/party/members/${id}/status/`, {
        method: "POST",
        body: reason ? { status, reason } : { status },
      }),
    onSuccess: () => invalidate("party-members", "party-member"),
  });
}

export const exportPartyMembers = (filters) =>
  download(`/party/members/export.csv?${memberQuery(filters)}`, "party-members.csv");

// ---- party volunteer register ---------------------------------------------
export const usePartyVolunteers = (filters) =>
  useQuery({
    queryKey: ["party-volunteers", filters],
    queryFn: () => api(`/party/volunteers/?${memberQuery(filters)}`),
    placeholderData: keepPreviousData,
  });

export function useUpdateVolunteer() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/party/volunteers/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidate("party-volunteers"),
  });
}

export const exportPartyVolunteers = (filters) =>
  download(`/party/volunteers/export.csv?${memberQuery(filters)}`, "party-volunteers.csv");

// ---- nominations ----------------------------------------------------------
export const useAspirants = (filters) =>
  useQuery({
    queryKey: ["aspirants", filters],
    queryFn: () => api(`/party/aspirants/?${memberQuery(filters)}`),
    placeholderData: keepPreviousData,
  });

export const useAspirant = (id) =>
  useQuery({
    queryKey: ["aspirant", id],
    queryFn: () => api(`/party/aspirants/${id}/`),
    enabled: !!id,
  });

export const useCandidates = (q) =>
  useQuery({
    queryKey: ["aspirant-candidates", q],
    queryFn: () => api(`/party/aspirants/candidates/?q=${encodeURIComponent(q)}`),
    enabled: q.trim().length >= 2,
  });

export function useNominate() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api("/party/aspirants/", { method: "POST", body }),
    onSuccess: () => invalidate("aspirants", "aspirant-candidates"),
  });
}

export function useMoveAspirant() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, status, reason }) =>
      api(`/party/aspirants/${id}/status/`, {
        method: "POST",
        body: reason ? { status, reason } : { status },
      }),
    onSuccess: () => invalidate("aspirants", "aspirant"),
  });
}

export function useCreateWorkspace() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/party/aspirants/${id}/workspace/`, { method: "POST", body }),
    onSuccess: () => invalidate("aspirants", "aspirant"),
  });
}

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

export function useLinkPartyMember() {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ user, member }) =>
      api(`/admin/users/${user}/party-member/`, { method: "PUT", body: { member } }),
    onSuccess: invalidate,
  });
}

// Candidates on the website: the directory, one profile, and its "Support" form.
export const usePublicCandidates = ({ seat = "", county = "", q = "" } = {}) =>
  useQuery({
    queryKey: ["public-candidates", seat, county, q],
    queryFn: () => api(`/candidates/?seat=${seat}&county=${county}&q=${encodeURIComponent(q)}`, { anonymous: true }),
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
  useQuery({
    queryKey: ["campaign-volunteers", campaignId],
    queryFn: () => api(`/campaigns/${campaignId}/volunteers/`),
    enabled: !!campaignId,
  });

export function useUpdateCampaignVolunteer(campaignId) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, ...body }) => api(`/campaigns/${campaignId}/volunteers/${id}/`, { method: "PATCH", body }),
    onSettled: () => qc.invalidateQueries({ queryKey: ["campaign-volunteers", campaignId] }),
  });
}



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
function useWorkspaceWrite(mutationFn) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSettled: () => {
      qc.invalidateQueries({ queryKey: ["workspace-site"] });
      qc.invalidateQueries({ queryKey: ["site"] });
      qc.invalidateQueries({ queryKey: ["site-candidate"] });
    },
  });
}

function useWsList(kind, queryFn) {
  return useQuery({ queryKey: ["workspace-site", kind], queryFn });
}

export const WORKSPACE_SECTIONS = {
  posts: {
    upload: "/workspace/site/images/",
    query: function usePosts() { return useWsList("posts", () => api("/workspace/site/posts/")); },
    save: function useSavePost() {
      return useWorkspaceWrite(({ id, ...body }) =>
        id ? api(`/workspace/site/posts/${id}/`, { method: "PATCH", body }) : api("/workspace/site/posts/", { method: "POST", body }));
    },
    del: function useDeletePost() { return useWorkspaceWrite((id) => api(`/workspace/site/posts/${id}/`, { method: "DELETE" })); },
  },
  slides: {
    upload: "/workspace/site/images/",
    query: function useSlides() { return useWsList("slides", () => api("/workspace/site/slides/")); },
    save: function useSaveSlide() {
      return useWorkspaceWrite(({ id, ...body }) =>
        id ? api(`/workspace/site/slides/${id}/`, { method: "PATCH", body }) : api("/workspace/site/slides/", { method: "POST", body }));
    },
    del: function useDeleteSlide() { return useWorkspaceWrite((id) => api(`/workspace/site/slides/${id}/`, { method: "DELETE" })); },
  },
  issues: {
    upload: "/workspace/site/images/",
    query: function useIssues() { return useWsList("issues", () => api("/workspace/site/issues/")); },
    save: function useSaveIssue() {
      return useWorkspaceWrite(({ id, ...body }) =>
        id ? api(`/workspace/site/issues/${id}/`, { method: "PATCH", body }) : api("/workspace/site/issues/", { method: "POST", body }));
    },
    del: function useDeleteIssue() { return useWorkspaceWrite((id) => api(`/workspace/site/issues/${id}/`, { method: "DELETE" })); },
  },
  documents: {
    upload: "/workspace/site/images/",
    query: function useDocuments() { return useWsList("documents", () => api("/workspace/site/documents/")); },
    save: function useSaveDocument() {
      return useWorkspaceWrite(({ id, ...body }) =>
        id ? api(`/workspace/site/documents/${id}/`, { method: "PATCH", body }) : api("/workspace/site/documents/", { method: "POST", body }));
    },
    del: function useDeleteDocument() { return useWorkspaceWrite((id) => api(`/workspace/site/documents/${id}/`, { method: "DELETE" })); },
  },
  videos: {
    upload: "/workspace/site/images/",
    query: function useVideos() { return useWsList("videos", () => api("/workspace/site/videos/")); },
    save: function useSaveVideo() {
      return useWorkspaceWrite(({ id, ...body }) =>
        id ? api(`/workspace/site/videos/${id}/`, { method: "PATCH", body }) : api("/workspace/site/videos/", { method: "POST", body }));
    },
    del: function useDeleteVideo() { return useWorkspaceWrite((id) => api(`/workspace/site/videos/${id}/`, { method: "DELETE" })); },
  },
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
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ manager }) =>
      replace
        ? api("/party/workspace/manager/", { method: "POST", body: { manager } })
        : api("/party/workspace/", { method: "POST", body: { manager } }),
    onSuccess: (data) => {
      onInvite?.(data);
      return invalidate();
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

export function useReplaceRecruitment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api("/party/workspace/recruitment/", { method: "POST" }),
    onSuccess: (data) => qc.setQueryData(["recruitment"], data),
  });
}

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

export function useDecideRegistration() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ campaign, id, decision, reason }) =>
      decision === "reject"
        ? api(`/campaigns/${campaign}/registrations/${id}/reject/`, { method: "POST", body: { reason } })
        : api(`/campaigns/${campaign}/registrations/${id}/approve/`, { method: "POST" }),
    onSuccess: () => invalidate("registrations", "team", "mobilizers", "agents", "agent-coverage"),
  });
}

export const useTeamLink = (campaignId) =>
  useQuery({ queryKey: ["team-link", campaignId], queryFn: () => api(`/campaigns/${campaignId}/team-link/`), enabled: !!campaignId });

export function useReplaceTeamLink() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (campaignId) => api(`/campaigns/${campaignId}/team-link/`, { method: "POST" }),
    onSuccess: (data, campaignId) => qc.setQueryData(["team-link", campaignId], data),
  });
}

export const useAgents = (campaignId) =>
  useQuery({ queryKey: ["agents", campaignId], queryFn: () => api(`/agents/?campaign=${campaignId}`), enabled: !!campaignId });

export const useAgentCoverage = (campaignId) =>
  useQuery({ queryKey: ["agent-coverage", campaignId], queryFn: () => api(`/agents/coverage/?campaign=${campaignId}`), enabled: !!campaignId });

export function useUpdateAgent() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) => api(`/agents/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidate("agents", "agent-coverage"),
  });
}

export const exportAgents = (campaignId) => download(`/agents/export/?campaign=${campaignId}`, "agents.csv");

// First-run setup: open before the installation exists; the token rides in a header for reads.
export const useCheckSetupToken = () =>
  useMutation({ mutationFn: (token) => api("/setup/check/", { method: "POST", body: { token }, anonymous: true }) });

export const useSetupAreas = (token, level, parent) =>
  useQuery({
    queryKey: ["setup-areas", level, parent],
    enabled: Boolean(token) && (level === "county" || Boolean(parent)),
    queryFn: () => api(`/setup/areas/?level=${level}&parent=${parent || ""}`, { anonymous: true, headers: { "X-Setup-Token": token } }),
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

export function useRefreshTargets() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (campaignId) => api("/targets/refresh/", { method: "POST", body: { campaign: campaignId } }),
    onSuccess: () => invalidate("targets", "strategy"),
  });
}

// The console's Health, Audit and Export tabs.
export const useHealth = () =>
  useQuery({ queryKey: ["admin", "health"], queryFn: () => api("/admin/health/") });

export const useBackups = () =>
  useQuery({ queryKey: ["admin", "backups"], queryFn: () => api("/admin/backups/") });

export const useAuditTrail = ({ action, actor, since, until }) =>
  useQuery({
    queryKey: ["admin", "audit", action, actor, since, until],
    queryFn: () =>
      api(`/admin/audit/?action=${encodeURIComponent(action)}&actor=${encodeURIComponent(actor)}&since=${since}&until=${until}&limit=200`),
  });

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
  useQuery({
    queryKey: ["branch-officials", countyId],
    enabled: Boolean(countyId),
    queryFn: () => api(`/party/office/branches/${countyId}/officials/`),
  });

function useOfficialsChanged() {
  const qc = useQueryClient();
  return () => ["branch-officials", "office-branches", "admin-branches", "public-branches"].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function useAppointOfficial() {
  const changed = useOfficialsChanged();
  return useMutation({
    mutationFn: ({ county, ...body }) => api(`/party/office/branches/${county}/officials/`, { method: "POST", body }),
    onSuccess: changed,
  });
}

export function useEndTerm() {
  const changed = useOfficialsChanged();
  return useMutation({
    mutationFn: ({ id, ...body }) => api(`/party/office/officials/${id}/end/`, { method: "POST", body }),
    onSuccess: changed,
  });
}

export const useUploadMinutes = () => useMutation({ mutationFn: (file) => upload("/party/office/minutes/", file) });
// A public site image, sent to the party's file store or to an aspirant workspace's.
export const useUploadImage = (path) => useMutation({ mutationFn: ({ file, area }) => upload(path, file, { area }) });

// Applying to vie: the published timetable, a member's own application, and the officer's side.
export const useNominationNotice = () =>
  useQuery({ queryKey: ["nominations", "current"], queryFn: () => api("/party/nominations/current/") });

export const useMyNomination = () =>
  useQuery({ queryKey: ["nominations", "mine"], queryFn: () => api("/party/nominations/mine/") });

function useMine(mutationFn) {
  const qc = useQueryClient();
  return useMutation({ mutationFn, onSuccess: (data) => data && qc.setQueryData(["nominations", "mine"], data) });
}

export const useApplyToVie = () => useMine((seat) => api("/party/nominations/mine/", { method: "POST", body: { seat } }));
export const useAttachNominationDocument = () =>
  useMine(({ file, label }) => upload("/party/nominations/mine/documents/", file, { label }));
export function useDetachNominationDocument() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (id) => api(`/party/nominations/mine/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => invalidate("nominations"),
  });
}
export const useSubmitNomination = () =>
  useMine(() => api("/party/nominations/mine/submit/", { method: "POST", body: { declaration: true } }));
export const useWithdrawNomination = () => useMine(() => api("/party/nominations/mine/withdraw/", { method: "POST" }));

export const useNominationWindows = () =>
  useQuery({ queryKey: ["nominations", "windows"], queryFn: () => api("/party/nominations/windows/") });

export function useDraftNominationWindow() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api("/party/nominations/windows/", { method: "POST", body }),
    onSuccess: () => invalidate("nominations"),
  });
}

export function useReviseNominationWindow() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, body }) => api(`/party/nominations/windows/${id}/`, { method: "PUT", body }),
    onSuccess: () => invalidate("nominations"),
  });
}

export function usePublishNominationWindow() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (id) => api(`/party/nominations/windows/${id}/publish/`, { method: "POST" }),
    onSuccess: () => invalidate("nominations"),
  });
}

export function useMarkNominationFeePaid() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, reference }) => api(`/party/nominations/applications/${id}/fee/`, { method: "POST", body: { reference } }),
    onSuccess: () => invalidate("aspirants", "aspirant"),
  });
}

// A hosted workspace's party feed and what it shares; the party's view of those counts.
export const usePartyFeed = (campaignId) =>
  useQuery({
    queryKey: ["party-feed", campaignId],
    queryFn: () => api(`/party-feed/?campaign=${campaignId}`),
    enabled: !!campaignId,
  });

export function useChangeSharing(campaignId) {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api(`/party-feed/sharing/?campaign=${campaignId}`, { method: "PUT", body }),
    onSuccess: () => invalidate("party-feed"),
  });
}

export const usePartyShared = () => useQuery({ queryKey: ["party-shared"], queryFn: () => api("/party/shared/") });

// The party office's texts to members and volunteers.
export const usePartyMessages = () => useQuery({ queryKey: ["party-messages"], queryFn: () => api("/party/messages/") });

export const usePartyMessageReach = ({ audience, county, constituency, ward }) =>
  useQuery({
    queryKey: ["party-messages", "reach", audience, county, constituency, ward],
    queryFn: () => api("/party/messages/preview/", { method: "POST", body: { audience, county, constituency, ward } }),
    placeholderData: (previous) => previous,
  });

function usePartyMessageAction(mutationFn) {
  const invalidate = useInvalidator();
  return useMutation({ mutationFn, onSuccess: () => invalidate("party-messages") });
}

export const useDraftPartyMessage = () =>
  usePartyMessageAction(({ audience, county, constituency, ward, body }) => api("/party/messages/", { method: "POST", body: { audience, county, constituency, ward, body } }));
export const useSendPartyMessage = () => usePartyMessageAction((id) => api(`/party/messages/${id}/send/`, { method: "POST" }));
export const useDeclinePartyMessage = () =>
  usePartyMessageAction(({ id, note }) => api(`/party/messages/${id}/decline/`, { method: "POST", body: { note } }));

// ---- personal data: requests, erasure, withdrawal links, closing ------------
// `campaignId` undefined is the party's own requests (Membership Officer).
export const useDataRequests = (campaignId) =>
  useQuery({
    queryKey: ["data-requests", campaignId ?? "party"],
    queryFn: () => (campaignId ? api(`/campaigns/${campaignId}/data/requests/`) : api("/party/data-requests/")),
  });

function useDataWrite(mutationFn, ...keys) {
  const invalidate = useInvalidator();
  return useMutation({ mutationFn, onSuccess: () => invalidate(...keys) });
}

export const useLogDataRequest = (campaignId) =>
  useDataWrite(
    (body) =>
      campaignId
        ? api(`/campaigns/${campaignId}/data/requests/`, { method: "POST", body })
        : api("/party/data-requests/", { method: "POST", body }),
    "data-requests",
  );

export const useUpdateDataRequest = (campaignId) =>
  useDataWrite(
    ({ id, ...body }) =>
      campaignId
        ? api(`/campaigns/${campaignId}/data/requests/${id}/`, { method: "PATCH", body })
        : api(`/party/data-requests/${id}/`, { method: "PATCH", body }),
    "data-requests",
  );

export const useLeftTeam = (campaignId) =>
  useQuery({ queryKey: ["left-team", campaignId], queryFn: () => api(`/campaigns/${campaignId}/data/left-team/`), enabled: !!campaignId });

const ERASE = {
  supporters: (campaignId, id) => api(`/campaigns/${campaignId}/data/supporters/${id}/erase/`, { method: "POST" }),
  volunteers: (campaignId, id) => api(`/campaigns/${campaignId}/data/volunteers/${id}/erase/`, { method: "POST" }),
  registrations: (campaignId, id) => api(`/campaigns/${campaignId}/data/registrations/${id}/erase/`, { method: "POST" }),
};

// kind is supporters, volunteers or registrations.
export const useErase = (campaignId, kind) =>
  useDataWrite((id) => ERASE[kind](campaignId, id), "supporters", "campaign-volunteers", "left-team", "data-close");

export const useWithdrawalLink = (campaignId, supporterId) =>
  useQuery({
    queryKey: ["withdrawal-link", supporterId],
    queryFn: () => api(`/campaigns/${campaignId}/data/supporters/${supporterId}/withdrawal/`),
    enabled: !!supporterId,
  });

export const useTextWithdrawalLink = (campaignId) =>
  useMutation({ mutationFn: (id) => api(`/campaigns/${campaignId}/data/supporters/${id}/withdrawal/`, { method: "POST" }) });

export const useCloseState = (campaignId) =>
  useQuery({ queryKey: ["data-close", campaignId], queryFn: () => api(`/campaigns/${campaignId}/data/close/`), enabled: !!campaignId });

export const useSetRetention = (campaignId) =>
  useDataWrite((retention_months) => api(`/campaigns/${campaignId}/data/retention/`, { method: "PUT", body: { retention_months } }), "data-close");

export const useCloseCampaign = (campaignId) =>
  useDataWrite(() => api(`/campaigns/${campaignId}/data/close/`, { method: "POST" }), "data-close", "campaigns");

export const useEraseSupporters = (campaignId) =>
  useDataWrite(() => api(`/campaigns/${campaignId}/data/erase-supporters/`, { method: "POST" }), "data-close", "supporters");

export const useEraseMember = () =>
  useDataWrite((id) => api(`/party/members/${id}/erase/`, { method: "POST" }), "party-members", "party-member", "party-volunteers");

export const useErasePartyVolunteer = () =>
  useDataWrite((id) => api(`/party/volunteers/${id}/erase/`, { method: "POST" }), "party-volunteers");

// ---- paying in by M-Pesa: the dialog's options, a contribution, a member's fee, and a
// payment's status while the dialog waits.
export const usePayOptions = () =>
  useQuery({ queryKey: ["pay-options"], queryFn: () => api("/pay/options/", { anonymous: true }) });

export const useContribute = () =>
  useMutation({ mutationFn: (body) => api("/pay/contribution/", { method: "POST", body, anonymous: true }) });

export function usePayFee() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (body) => api("/party/nominations/mine/pay/", { method: "POST", body }),
    onSuccess: () => invalidate("nominations"),
  });
}

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

export function useDecidePaymentIn(campaignId) {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, reason }) => {
      if (campaignId) {
        return reason === undefined
          ? api(`/campaigns/${campaignId}/payments-in/${id}/confirm/`, { method: "POST" })
          : api(`/campaigns/${campaignId}/payments-in/${id}/reject/`, { method: "POST", body: { reason } });
      }
      return reason === undefined
        ? api(`/party/payments-in/${id}/confirm/`, { method: "POST" })
        : api(`/party/payments-in/${id}/reject/`, { method: "POST", body: { reason } });
    },
    onSuccess: () => invalidate("payments-in", "nominations", "aspirants", "aspirant"),
  });
}
