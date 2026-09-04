/** The query hooks: what they ask for, and what they refresh after a write. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import {
  useConstituencies,
  useEvents,
  useRecordEvent,
  useScheduleEvent,
  useStrategy,
  useTargets,
  useWardsIn,
} from "../src/api/hooks";
import { EVENTS, STRATEGY, TARGETS, signIn, stubApi } from "./helpers";

afterEach(() => {
  vi.unstubAllGlobals();
});

function wrap() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 } },
  });
  const wrapper = ({ children }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

describe("the query hooks", () => {
  it("scopes every campaign query to the campaign it was given", async () => {
    signIn();
    const calls = stubApi({ "GET /targets/": TARGETS, "GET /strategy/": STRATEGY });
    const { wrapper } = wrap();

    renderHook(() => useTargets("c1"), { wrapper });
    renderHook(() => useStrategy("c1"), { wrapper });

    await waitFor(() => expect(calls.length).toBe(2));
    expect(calls.map((c) => c.path).sort()).toEqual([
      "/strategy/?campaign=c1",
      "/targets/?campaign=c1",
    ]);
  });

  it("asks for nothing until it knows which campaign", async () => {
    signIn();
    const calls = stubApi({ "GET /targets/": TARGETS });
    const { wrapper } = wrap();

    const { result } = renderHook(() => useTargets(undefined), { wrapper });

    expect(result.current.fetchStatus).toBe("idle");
    expect(calls).toHaveLength(0);
  });

  it("waits for a county before listing its constituencies", async () => {
    signIn();
    const calls = stubApi({ "GET /constituencies/": [] });
    const { wrapper } = wrap();

    renderHook(() => useConstituencies(""), { wrapper });

    expect(calls).toHaveLength(0);
  });

  it("lists the wards inside one constituency", async () => {
    signIn();
    const calls = stubApi({ "GET /wards/": [{ id: "w1", name: "Zimmerman" }] });
    const { wrapper } = wrap();

    renderHook(() => useWardsIn("k1"), { wrapper });

    await waitFor(() => expect(calls[0].path).toBe("/wards/?constituency=k1"));
  });

  it("refreshes the strategy after an event is scheduled", async () => {
    /* The strategy is computed from events, so a stale read would contradict itself. */
    signIn();
    stubApi({ "GET /strategy/": STRATEGY, "POST /events/": { id: "e2" } });
    const { queryClient, wrapper } = wrap();
    const invalidate = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useScheduleEvent(), { wrapper });
    result.current.mutate({ campaign: "c1", ward: "w1", title: "Rally" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const keys = invalidate.mock.calls.map((c) => c[0].queryKey[0]);
    expect(keys).toContain("events");
    expect(keys).toContain("strategy");
  });

  it("records attendance against the event's own route", async () => {
    signIn();
    const calls = stubApi({ "POST /events/e1/record/": EVENTS[0] });
    const { wrapper } = wrap();

    const { result } = renderHook(() => useRecordEvent(), { wrapper });
    result.current.mutate({ id: "e1", number_reached: 400, number_attended: 300 });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(calls[0].path).toBe("/events/e1/record/");
    expect(calls[0].body).toEqual({ number_reached: 400, number_attended: 300 });
  });

  it("surfaces the server's message when a write is refused", async () => {
    signIn();
    stubApi({
      "POST /events/": { status: 400, body: { detail: "A mobilizer may only work in their own ward." } },
    });
    const { wrapper } = wrap();

    const { result } = renderHook(() => useScheduleEvent(), { wrapper });
    result.current.mutate({ campaign: "c1", ward: "w2" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error.message).toBe("A mobilizer may only work in their own ward.");
  });

  it("reads the event list back for one campaign", async () => {
    signIn();
    stubApi({ "GET /events/": EVENTS });
    const { wrapper } = wrap();

    const { result } = renderHook(() => useEvents("c1"), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data[0].title).toBe("Zimmerman town hall");
  });
});
