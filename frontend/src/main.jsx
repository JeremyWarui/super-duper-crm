// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Login from "./components/Login";
import Onboarding from "./components/Onboarding";
import App from "./App";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// Signed in with no campaign yet -> set one up first. A mobilizer cannot create
// one, so they go straight to App, which tells them there is nothing to work on.
function SignedIn() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const needsSetup =
    campaigns.isSuccess && campaigns.data.length === 0 && role !== "mobilizer";
  return needsSetup ? <Onboarding onDone={() => campaigns.refetch()} /> : <App />;
}

function Root() {
  const token = useAuth((s) => s.token);
  return token ? <SignedIn /> : <Login />;
}

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <Root />
    </QueryClientProvider>
  </React.StrictMode>
);
