// src/api/hooks.js
// React Query hooks. Queries read; mutations write and then invalidate the
// caches that changed — e.g. scheduling an event refreshes both the event list
// AND the strategy read, because the strategy is computed from events.

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { api } from "./client";

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

// Public self-registration needs no token — the client just omits it when absent.
export function useRegisterSupporter() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) =>
      api("/supporters/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("supporters"),
  });
}

// ---- Onboarding: geography pickers + campaign setup ----------------------
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

// Creates the campaign AND generates its targets in one call; returns the
// campaign plus a setup summary { grain, units, total_registered, win_number }.
export function useSetupCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) =>
      api("/campaigns/setup/", { method: "POST", body: payload }),
    onSuccess: () => qc.invalidateQueries(),
  });
}

// The user's campaign(s). For a single-campaign MVP, take the first.
export const useCampaigns = () =>
  useQuery({ queryKey: ["campaigns"], queryFn: () => api("/campaigns/") });

// Edit a target's turnout assumption; the server recomputes votes_needed.
export function useUpdateTarget() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: ({ id, ...body }) =>
      api(`/targets/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidate("targets", "strategy"),
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

export const useTeam = (role, enabled = true) =>
  useQuery({
    queryKey: ["team", role],
    queryFn: () => (role ? api(`/users/?role=${role}`) : api("/users/")),
    enabled,
  });

// Creates a login. The password comes back once and is never fetchable again.
export function useCreateUser() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/users/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("team", "mobilizers", "strategy"),
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
