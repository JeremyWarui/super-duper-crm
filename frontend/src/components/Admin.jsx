// src/components/Admin.jsx
// The console for whoever runs the deployment: every campaign on it, every
// login, and the few repairs that cannot be done from inside a campaign.
// Shown only to a superuser; every route it calls checks the flag again.
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useAdminOverview, rowsOf, useAdminUserPages, useAdminUsers, useCreateLogin, useResetPassword } from "../api/hooks";
import { useInstall } from "../app/site";
import { useCopy } from "../copy";
import { useAuth } from "../store/auth";
import { formatNumber as fmt, plural } from "../lib/format";
import { SlottedHeader } from "@/components/layout/AppPage";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { StatTiles } from "@/components/ui/stat-tiles";
import { LoadingText } from "@/components/ui/loading-text";
import { FilterPills } from "@/components/ui/tabs";
import { PartyShell } from "../pages/party/Portal";
import AuditTrail from "./console/AuditTrail";
import ExportPanel from "./console/ExportPanel";
import Health from "./console/Health";
import ReferenceData from "./console/ReferenceData";
import { LoadMore } from "@/components/ui/load-more";
import { Failed } from "./console/kit";
import { CampaignCard, OpenPartyWorkspace } from "./console/Campaigns";
import { NewLogin, UserRow } from "./console/Logins";
import SiteSettings from "./console/SiteSettings";

// Which sign-in links went out this visit, kept until the console is closed.
function Handout({ shown }) {
  if (!shown.length) return null;
  return (
    <Card variant="outline" className="gap-2 border-warn bg-warn/40">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="text-body font-bold">Sign-in links</h2>
        <span className="text-small text-warn-foreground">each person chooses their own password</span>
      </div>
      <ul className="flex flex-col divide-y divide-warn text-ui">
        {shown.map((p) => (
          <li key={p.username} className="flex flex-wrap justify-between gap-x-4 gap-y-1 py-2">
            <span className="font-semibold break-all">{p.username}</span>
            <span>{(p.sent ?? p.invite) === "email" ? "Link emailed" : "No email: nothing sent"}</span>
          </li>
        ))}
      </ul>
    </Card>
  );
}

// The shell's menu carries the only way out of the console, so every state renders
// inside it: a signed-out operator can always sign out and back in.
function Shell({ children }) {
  return (
    <PartyShell crumb="Console" page={{ kit: true }}>
      <SlottedHeader title="Console" />
      {children}
    </PartyShell>
  );
}

export default function Admin() {
  const me = useAuth((s) => s.user);
  const { aspirant } = useInstall();
  const copy = useCopy();
  const overview = useAdminOverview();
  const [roleFilter, setRoleFilter] = useState("");
  // Every login, for the campaign pickers and the tab count; the Logins tab lists them a page at a time.
  const users = useAdminUsers();
  const loginPages = useAdminUserPages(roleFilter);
  const [tab, setTab] = useState("campaigns");
  const navigate = useNavigate();
  const [handouts, setHandouts] = useState([]);
  // Owned here, not in the row: a row unmounts on every refetch. One mutation
  // serves every row, and it only remembers its latest call, so what each row
  // shows is kept by id.
  const [failed, setFailed] = useState({});
  const [running, setRunning] = useState(() => new Set());
  const forget = (id) => setFailed(({ [id]: _gone, ...rest }) => rest);
  const handOut = (r) =>
    setHandouts((h) => [...h.filter((p) => p.username !== r.username), r]);
  const reset = useResetPassword({
    onPassword: handOut,
    onFailed: (error, { id }) =>
      setFailed((f) => ({ ...f, [id]: error.message })),
    onDone: ({ id }) =>
      setRunning((ids) => {
        const left = new Set(ids);
        left.delete(id);
        return left;
      }),
  });
  const create = useCreateLogin({ onPassword: handOut });
  const startReset = (id) => {
    forget(id);
    setRunning((ids) => new Set(ids).add(id));
    reset.mutate({ id });
  };

  if (overview.isLoading)
    return (
      <Shell>
        <LoadingText>Loading the console…</LoadingText>
      </Shell>
    );
  if (overview.error)
    return (
      <Shell>
        <Failed error={overview.error} onRetry={() => overview.refetch()} />
        <Handout shown={handouts} />
      </Shell>
    );

  const { totals, campaigns } = overview.data;
  const everyone = users.data || [];
  const listed = rowsOf(loginPages.data);
  const unstaffed = campaigns.filter((c) => c.members.length === 0).length;

  return (
    <Shell>
      <div className="flex flex-col gap-3">
        <StatTiles min={150} tiles={[
          ["Campaigns", fmt(totals.campaigns)],
          ["Logins", fmt(totals.users)],
          ["Places held", fmt(totals.members)],
          ["Targets", fmt(totals.targets)],
          ["Mobilizers", fmt(totals.mobilizers)],
          ["Events", fmt(totals.events)],
          ["Supporters", fmt(totals.supporters)],
        ]} />
        {unstaffed > 0 && (
          <p className="text-ui font-semibold text-destructive">
            {plural(unstaffed, "campaign")} with nobody on{" "}
            {unstaffed === 1 ? "it" : "them"}: nobody can see{" "}
            {unstaffed === 1 ? "it" : "them"} until somebody is put on.
          </p>
        )}
      </div>

      <Handout shown={handouts} />

      <div className="flex flex-col gap-4">
        <FilterPills look="rounded"
          label="Console sections"
          value={tab}
          onChange={setTab}
          options={[
            ["campaigns", `Campaigns (${campaigns.length})`],
            ["users", `Logins (${everyone.length})`],
            ["party", copy.settingsTab],
            ["areas", "Areas and register"],
            ["health", "Health"],
            ["audit", "Audit"],
            ["export", "Export"],
          ]}
        />

        {tab === "campaigns" && !aspirant && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
            <Button shape="rounded" size="sm" variant="quiet" onClick={() => navigate("/party/aspirants")}>New campaign</Button>
            <span className="text-ui text-muted-foreground">
              A workspace is made from an approved aspirant, in Aspirants.
            </span>
          </div>
        )}
        {tab === "campaigns" && <OpenPartyWorkspace onInvite={handOut} />}

        {tab === "campaigns" &&
          (campaigns.length === 0 ? (
            <Card variant="outline">
              <span className="text-muted-foreground">
                No campaigns yet.
              </span>
            </Card>
          ) : (
            campaigns.map((c) => (
              <CampaignCard key={c.id} campaign={c} users={everyone} />
            ))
          ))}

        {tab === "party" && !aspirant && (
          <div>
            <Button shape="rounded" size="sm" variant="quiet" onClick={() => navigate("/party/aspirants")}>Open aspirants</Button>
          </div>
        )}
        {tab === "party" && <SiteSettings />}
        {tab === "areas" && <ReferenceData />}
        {tab === "health" && <Health />}
        {tab === "audit" && <AuditTrail />}
        {tab === "export" && <ExportPanel />}

        {tab === "users" && (
          <Card variant="outline" className="min-w-0">
            <FilterPills
              label="Show logins"
              value={roleFilter}
              onChange={(key) => {
                setRoleFilter(key);
                setFailed({});
              }}
              options={[
                ["", "Everyone"],
                ["manager", "Managers"],
                ["candidate", "Aspirants"],
                ["mobilizer", "Mobilizers"],
              ]}
            />
            <NewLogin campaigns={campaigns} create={create} />
            <div className="flex flex-col">
              {loginPages.isPending ? (
                <LoadingText>Loading the logins…</LoadingText>
              ) : listed.length === 0 ? (
                <p className="text-ui text-muted-foreground">
                  Nobody matches that.
                </p>
              ) : (
                listed.map((u) => (
                  <UserRow
                    key={u.id}
                    user={u}
                    me={me?.id}
                    onReset={startReset}
                    resetting={running.has(u.id)}
                    resetError={failed[u.id]}
                  />
                ))
              )}
            </div>
            <LoadMore
              shown={listed.length}
              total={roleFilter ? undefined : everyone.length}
              noun="logins"
              hasMore={!!loginPages.hasNextPage}
              loading={loginPages.isFetchingNextPage}
              onMore={() => loginPages.fetchNextPage()}
            />
          </Card>
        )}
      </div>
    </Shell>
  );
}
