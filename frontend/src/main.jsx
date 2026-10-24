// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import Root, { forgetOnSwitch } from "./Gate";
import Join from "./components/Join";
import Withdraw from "./components/Withdraw";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});
forgetOnSwitch(queryClient);

// A sign-up link opens /join/<code>, and a supporter's withdrawal link /withdraw/<code>;
// neither needs a login.
const joinCode = window.location.pathname.match(/^\/join\/([^/]+)\/?$/)?.[1];
const withdrawCode = window.location.pathname.match(/^\/withdraw\/([^/]+)\/?$/)?.[1];
const page = joinCode ? (
  <Join code={decodeURIComponent(joinCode)} />
) : withdrawCode ? (
  <Withdraw code={decodeURIComponent(withdrawCode)} />
) : (
  <Root />
);

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {page}
    </QueryClientProvider>
  </React.StrictMode>,
);
