// The signed-in party portal: routes `/party/*` and the shell around each page.
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "@/store/auth";
import DataRequests from "@/components/DataRequests";
import Aspirants from "./Aspirants";
import Branches from "./Branches";
import Dashboard from "./Dashboard";
import Members from "./Members";
import PaymentsIn from "./PaymentsIn";
import Messages from "./Messages";
import Volunteers from "./Volunteers";
import Website from "./Website";
import { PartyShell } from "@/components/layout/PartyShell";
import { pagesFor } from "@/lib/partyNav";

// The page each party route shows.
const ELEMENTS = {
  "dashboard": <Dashboard />,
  "members": <Members />,
  "volunteers": <Volunteers />,
  "data-requests": <DataRequests />,
  "aspirants": <Aspirants />,
  "payments-in": <PaymentsIn />,
  "messages": <Messages />,
  "branches": <Branches />,
  "website": <Website />,
};

export default function Portal() {
  const user = useAuth((s) => s.user);
  const { pathname } = useLocation();
  const pages = pagesFor(user);
  const current = pages.find(([key]) => pathname.startsWith(`/party/${key}`)) ?? pages[0];

  return (
    <PartyShell crumb={current?.[1] || "Party CRM"} page={current?.[3]}>
      {pages.length ? (
        <Routes>
          {pages.map(([key]) => (
            <Route key={key} path={`party/${key}`} element={ELEMENTS[key]} />
          ))}
          <Route path="*" element={<Navigate to={`/party/${pages[0][0]}`} replace />} />
        </Routes>
      ) : (
        <p className="text-muted-foreground">There is nothing for your office here yet.</p>
      )}
    </PartyShell>
  );
}
