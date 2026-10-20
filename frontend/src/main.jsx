// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Root, { forgetOnSwitch } from "./Gate";
import Join from "./components/Join";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});
forgetOnSwitch(queryClient);

// An event's QR code opens /join/<code>, which needs no login.
const joinCode = window.location.pathname.match(/^\/join\/([^/]+)\/?$/)?.[1];

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {joinCode ? <Join code={decodeURIComponent(joinCode)} /> : <Root />}
    </QueryClientProvider>
  </React.StrictMode>,
);
