// src/api/hooks.js
// React Query hooks. Queries read; mutations write and then invalidate the
// caches that changed — e.g. scheduling an event refreshes both the event list
// AND the strategy read, because the strategy is computed from events.

import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";

// ---- Queries --------------------------------------------------------------
export const useWards = () =>
  useQuery({ queryKey: ["wards"], queryFn: () => api("/wards/") });

export const useTargets = (campaignId) =>
  useQuery({ queryKey: ["targets", campaignId], queryFn: () => api(`/targets/?campaign=${campaignId}`), enabled: !!campaignId });

export const useEvents = (campaignId) =>
  useQuery({ queryKey: ["events", campaignId], queryFn: () => api(`/events/?campaign=${campaignId}`), enabled: !!campaignId });

export const useMobilizers = (campaignId) =>
  useQuery({ queryKey: ["mobilizers", campaignId], queryFn: () => api(`/mobilizers/?campaign=${campaignId}`), enabled: !!campaignId });

export const useSupporters = (campaignId) =>
  useQuery({ queryKey: ["supporters", campaignId], queryFn: () => api(`/supporters/?campaign=${campaignId}`), enabled: !!campaignId });

export const useStrategy = (campaignId) =>
  useQuery({ queryKey: ["strategy", campaignId], queryFn: () => api(`/strategy/?campaign=${campaignId}`), enabled: !!campaignId });

// ---- Mutations ------------------------------------------------------------
function useInvalidator() {
  const qc = useQueryClient();
  return (...keys) => keys.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
}

export function useSetTarget() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/targets/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("targets", "strategy"),
  });
}

export function useAddMobilizer() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/mobilizers/", { method: "POST", body: payload }),
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
      api(`/events/${id}/record/`, { method: "POST", body: { number_reached, number_attended } }),
    onSuccess: () => invalidate("events", "strategy"),
  });
}

// Public self-registration needs no token — the client just omits it when absent.
export function useRegisterSupporter() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/supporters/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("supporters"),
  });
}

// ---- Onboarding: geography pickers + campaign setup ----------------------
export const useCounties = () =>
  useQuery({ queryKey: ["counties"], queryFn: () => api("/counties/") });

export const useConstituencies = (countyId) =>
  useQuery({ queryKey: ["constituencies", countyId], queryFn: () => api(`/constituencies/?county=${countyId}`), enabled: !!countyId });

export const useWardsIn = (constituencyId) =>
  useQuery({ queryKey: ["wardsIn", constituencyId], queryFn: () => api(`/wards/?constituency=${constituencyId}`), enabled: !!constituencyId });

// Creates the campaign AND generates its targets in one call; returns the
// campaign plus a setup summary { grain, units, total_registered, win_number }.
export function useSetupCampaign() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload) => api("/campaigns/setup/", { method: "POST", body: payload }),
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
    mutationFn: ({ id, ...body }) => api(`/targets/${id}/`, { method: "PATCH", body }),
    onSuccess: () => invalidate("targets", "strategy"),
  });
}

// Ward drill-down for MCA races: the ward's registration centres + their voters.
export const useCentres = (wardId) =>
  useQuery({ queryKey: ["centres", wardId], queryFn: () => api(`/centres/?ward=${wardId}`), enabled: !!wardId });

export const useWardsInCounty = (countyId) =>
  useQuery({ queryKey: ["wardsInCounty", countyId], queryFn: () => api(`/wards/?county=${countyId}`), enabled: !!countyId });

// The units a chosen seat will get a target for, before it is created.
export function useUnitsPreview({ office_level, county, constituency, ward }) {
  const wardsInCounty = useWardsInCounty(office_level === "county" ? county : null);
  const wardsInConstituency = useWardsIn(office_level === "constituency" ? constituency : null);
  const centres = useCentres(office_level === "ward" ? ward : null);

  const source = office_level === "county" ? wardsInCounty : office_level === "constituency" ? wardsInConstituency : centres;
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
    mutationFn: ({ id, ...body }) => api(`/events/${id}/invite/`, { method: "POST", body }),
    onSuccess: (_data, variables) => {
      if (!variables.dry_run) invalidate("events", "strategy");
    },
  });
}

export const useTeam = () =>
  useQuery({ queryKey: ["team"], queryFn: () => api("/users/") });

// Creates a login. The password comes back once and is never fetchable again.
export function useCreateUser() {
  const invalidate = useInvalidator();
  return useMutation({
    mutationFn: (payload) => api("/users/", { method: "POST", body: payload }),
    onSuccess: () => invalidate("team", "mobilizers", "strategy"),
  });
}
