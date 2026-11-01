// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { AppRoutes, forgetOnSwitch } from "./Gate";

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
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>,
);
