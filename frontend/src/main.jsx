// src/main.jsx
import React from "react";
import ReactDOM from "react-dom/client";
import "./index.css";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAuth } from "./store/auth";
import { useCampaigns } from "./api/hooks";
import Login from "./components/Login";
import Onboarding from "./components/Onboarding";
import Admin from "./components/Admin";
import App from "./App";
import Join from "./components/Join";

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
});

// Signed in with no campaign -> set one up. A mobilizer cannot, so they skip it.
function SignedIn() {
  const role = useAuth((s) => s.user?.role);
  const campaigns = useCampaigns();
  const needsSetup =
    campaigns.isSuccess && campaigns.data.length === 0 && role !== "mobilizer";
  return needsSetup ? (
    <Onboarding onDone={() => campaigns.refetch()} />
  ) : (
    <App />
  );
}

// A superuser runs the deployment rather than a campaign, so they get the
// console instead of the campaign gate.
function Inside() {
  const isSuperuser = useAuth((s) => s.user?.is_superuser);
  return isSuperuser ? <Admin /> : <SignedIn />;
}

function Root() {
  const token = useAuth((s) => s.token);
  return token ? <Inside /> : <Login />;
}

// An event's QR code opens /join/<code>, which needs no login.
const joinCode = window.location.pathname.match(/^\/join\/([^/]+)\/?$/)?.[1];

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      {joinCode ? <Join code={decodeURIComponent(joinCode)} /> : <Root />}
    </QueryClientProvider>
  </React.StrictMode>,
);
