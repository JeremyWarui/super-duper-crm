/** What each hook asks for, and what a write refreshes. */
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { useStrategy, useTargets } from "../src/api/hooks";
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
