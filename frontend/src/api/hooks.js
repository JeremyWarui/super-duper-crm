// src/api/hooks.js
// React Query hooks. Queries read; mutations write and then invalidate the
// caches that changed — e.g. scheduling an event refreshes both the event list
// AND the strategy read, because the strategy is computed from events.

import { useEffect } from "react";
import {
  keepPreviousData,
  useMutation,
  useQueries,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api, download } from "./client";
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

export function useCancelPayment() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id }) => api(`/payments/${id}/cancel/`, { method: "POST" }),
    onSettled: () => invalidate("payments"),  // a refused change may mean the row moved on
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

// The signed-in campaign's own subscription; it answers even while the campaign is locked.
export const useOwnSubscription = () =>
  useQuery({ queryKey: ["subscription"], queryFn: () => api("/subscription/") });

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

export function useResetTeamPassword() {
  return useMutation({
    mutationFn: ({ campaign, user }) =>
      api(`/campaigns/${campaign}/team/${user}/reset-password/`, {
        method: "POST",
      }),
  });
}

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

// A campaign with its aspirant's and manager's logins; each password comes back
// once and is handed to the hook's owner.
export function useAdminCreateCampaign({ onPassword } = {}) {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/admin/campaigns/", { method: "POST", body: payload }),
    onSuccess: (data) => {
      data.logins.forEach((login) => onPassword?.(login));
      return invalidate();
    },
  });
}

function useAdminInvalidator() {
  const qc = useQueryClient();
  return () => qc.invalidateQueries({ queryKey: ["admin"] });
}

// Every callback runs on whoever owns the hook, and is handed the id it was
// about. The password comes back once, so it must not be delivered through a
// per-call callback: React Query drops those when the calling component
// unmounts, and a row unmounts whenever the list refetches or the filter
// changes. A shared mutation also only remembers its latest call, so the caller
// has to key what it keeps by id rather than read `error` or `isPending` here.
export function useResetPassword({ onPassword, onFailed, onDone } = {}) {
  const invalidate = useAdminInvalidator();
  return useMutation({
    mutationFn: ({ id, password }) =>
      api(`/admin/users/${id}/reset-password/`, {
        method: "POST",
        body: { password: password || null },
      }),
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

// ---- party settings and offices -------------------------------------------
export const useParty = () =>
  useQuery({ queryKey: ["party"], queryFn: () => api("/party/", { anonymous: true }) });

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

export const useAdminBranches = () =>
  useQuery({ queryKey: ["admin-branches"], queryFn: () => api("/admin/party/branches/") });

export function useSaveBranch() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ county, ...payload }) =>
      api(`/admin/party/branches/${county}/`, { method: "PUT", body: payload }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-branches"] });
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

export const useContribute = () =>
  useMutation({
    mutationFn: (payload) =>
      api("/party/contribute/", { method: "POST", body: payload, anonymous: true }),
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

export function useSaveParty() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) =>
      api("/admin/party/", { method: "PUT", body: payload }),
    onSuccess: (data) => qc.setQueryData(["party"], data),
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

// The superuser's party-wide counts; `from` and `to` bound events and revenue.
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

// ---- party finance --------------------------------------------------------
export const useFinancePlans = () =>
  useQuery({ queryKey: ["finance", "plans"], queryFn: () => api("/party/finance/plans/") });

export const useFinanceSubscriptions = (filters) =>
  useQuery({
    queryKey: ["finance", "subscriptions", filters],
    queryFn: () => api(`/party/finance/subscriptions/?${memberQuery(filters)}`),
    placeholderData: keepPreviousData,
  });

// How many campaigns are in each state; "" counts them all.
export const useFinanceStateCounts = (states) =>
  useQueries({
    queries: states.map((state) => ({
      queryKey: ["finance", "subscriptions", { state, limit: 1 }],
      queryFn: () => api(`/party/finance/subscriptions/?${memberQuery({ state, limit: 1 })}`),
    })),
    combine: (results) =>
      Object.fromEntries(states.map((state, i) => [state, results[i].data?.total])),
  });

export const useFinanceSubscription = (id) =>
  useQuery({
    queryKey: ["finance", "subscription", id],
    queryFn: () => api(`/party/finance/subscriptions/${id}/`),
    enabled: !!id,
  });

export const useFinanceSettings = () =>
  useQuery({ queryKey: ["finance", "settings"], queryFn: () => api("/party/finance/settings/") });

export const useRevenueReport = ({ from, to }) =>
  useQuery({
    queryKey: ["finance", "revenue", from, to],
    queryFn: () => api(`/party/finance/reports/revenue/?${memberQuery({ from, to })}`),
    enabled: !!from && !!to,
    placeholderData: keepPreviousData,
  });

export const useExpiringReport = (days) =>
  useQuery({
    queryKey: ["finance", "expiring", days],
    queryFn: () => api(`/party/finance/reports/expiring/?days=${days}`),
    placeholderData: keepPreviousData,
  });

// Every finance write refreshes every finance read: a payment moves the lists,
// the reports and the detail, and a settings change moves every campaign's state.
function useFinanceWrite(mutationFn) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn,
    onSuccess: (data) => {
      if (data?.entries) qc.setQueryData(["finance", "subscription", data.id], data);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

export const useCreatePlan = () =>
  useFinanceWrite((body) => api("/party/finance/plans/", { method: "POST", body }));

export const useUpdatePlan = () =>
  useFinanceWrite(({ id, ...body }) =>
    api(`/party/finance/plans/${id}/`, { method: "PATCH", body }),
  );

export const useChoosePlan = () =>
  useFinanceWrite(({ id, plan }) =>
    api(`/party/finance/subscriptions/${id}/plan/`, { method: "PUT", body: { plan } }),
  );

export const useRecordSubscriptionPayment = () =>
  useFinanceWrite(({ id, ...body }) =>
    api(`/party/finance/subscriptions/${id}/payments/`, { method: "POST", body }),
  );

export const useExtendSubscription = () =>
  useFinanceWrite(({ id, ...body }) =>
    api(`/party/finance/subscriptions/${id}/extensions/`, { method: "POST", body }),
  );

export const useVoidEntry = () =>
  useFinanceWrite(({ id, entry, reason }) =>
    api(`/party/finance/subscriptions/${id}/entries/${entry}/void/`, {
      method: "POST",
      body: { reason },
    }),
  );

// `hold: "none"` lifts it; the server drops the reason.
export const useSetHold = () =>
  useFinanceWrite(({ id, ...body }) =>
    api(`/party/finance/subscriptions/${id}/hold/`, { method: "PUT", body }),
  );

// ---- party payouts ---------------------------------------------------------
export const usePartyPayouts = () =>
  useQuery({ queryKey: ["finance", "payouts"], queryFn: () => api("/party/finance/payouts/") });

export const usePayoutSpend = () =>
  useQuery({ queryKey: ["finance", "payouts", "spend"], queryFn: () => api("/party/finance/payouts/spend/") });

export const usePayoutCampaigns = () =>
  useQuery({ queryKey: ["finance", "payouts", "campaigns"], queryFn: () => api("/party/finance/payouts/campaigns/") });

export const usePayoutPayees = (q) =>
  useQuery({
    queryKey: ["finance", "payouts", "payees", q],
    enabled: q.trim().length >= 2,
    queryFn: () => api(`/party/finance/payouts/payees/?q=${encodeURIComponent(q.trim())}`),
  });

export const useSchedulePayout = () =>
  useFinanceWrite((body) => api("/party/finance/payouts/", { method: "POST", body }));

export const useReleasePayout = () =>
  useFinanceWrite(({ id }) => api(`/party/finance/payouts/${id}/release/`, { method: "POST" }));

export const useMarkPayoutPaid = () =>
  useFinanceWrite(({ id, reference }) =>
    api(`/party/finance/payouts/${id}/paid/`, { method: "POST", body: { reference } }),
  );

export const useMarkPayoutNotSent = () =>
  useFinanceWrite(({ id }) => api(`/party/finance/payouts/${id}/not-sent/`, { method: "POST" }));

export const useCancelPayout = () =>
  useFinanceWrite(({ id }) => api(`/party/finance/payouts/${id}/cancel/`, { method: "POST" }));

export function useSaveFinanceSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body) => api("/party/finance/settings/", { method: "PUT", body }),
    onSuccess: (data) => qc.setQueryData(["finance", "settings"], data),
    onSettled: () => qc.invalidateQueries({ queryKey: ["finance"] }),
  });
}

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

