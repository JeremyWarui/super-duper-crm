// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/public-sans";
import "@fontsource-variable/bricolage-grotesque";
import "@/styles/globals.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes, forgetOnSwitch } from "./Gate";
import { api } from "@/api/client";
import { useAuth } from "@/store/auth";
import { BrandingProvider } from "@/theme/branding";

const queryClient = new QueryClient({
  // Data stays fresh for five minutes; a write refreshes what it changed at once. A refusal does
  // not change on a retry, so a 403 is shown at once.
  defaultOptions: {
    queries: { staleTime: 5 * 60_000, retry: (count, error) => error?.status !== 403 && count < 1 },
  },
});
forgetOnSwitch(queryClient);
// A returning login asks who it is and its campaigns alongside the site settings, not after them.
if (useAuth.getState().token) {
  queryClient.prefetchQuery({ queryKey: ["me"], queryFn: () => api("/auth/me/") });
  queryClient.prefetchQuery({ queryKey: ["campaigns"], queryFn: () => api("/campaigns/") });
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrandingProvider>
        <BrowserRouter>
          <AppRoutes />
        </BrowserRouter>
      </BrandingProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
