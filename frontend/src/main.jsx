// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "@fontsource-variable/public-sans";
import "@fontsource-variable/bricolage-grotesque";
import "@/styles/globals.css";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes, forgetOnSwitch } from "./Gate";
import { BrandingProvider } from "@/theme/branding";

const queryClient = new QueryClient({
  // A refusal does not change on a retry, so a 403 is shown at once.
  defaultOptions: {
    queries: { staleTime: 30_000, retry: (count, error) => error?.status !== 403 && count < 1 },
  },
});
forgetOnSwitch(queryClient);

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
