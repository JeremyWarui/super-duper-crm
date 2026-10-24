/** What each hook asks for, and what a write refreshes. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useRegisterSupporter, useStrategy, useTargets } from "../src/api/hooks";
import { STRATEGY, TARGETS, signIn, stubApi } from "./helpers";

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
});

describe("what a write refreshes", () => {
  it("refreshes the progress after a mobilizer registers a supporter", async () => {
    signIn();
    const calls = stubApi({
      "GET /strategy/": STRATEGY,
      "POST /supporters/": { id: "s1" },
    });
    const { wrapper } = wrap();
    renderHook(() => useStrategy("c1"), { wrapper });
    const write = renderHook(() => useRegisterSupporter(), { wrapper });
    await waitFor(() => expect(calls.length).toBe(1));

    await act(() => write.result.current.mutateAsync({ full_name: "Wanjiku", consent_given: true }));

    await waitFor(() =>
      expect(calls.filter((c) => c.path === "/strategy/?campaign=c1")).toHaveLength(2),
    );
  });
});
