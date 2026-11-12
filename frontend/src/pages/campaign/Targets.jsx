import { useCallback, useEffect, useRef, useState } from "react";
import { useRefreshTargets, useTargets, useUpdateTarget } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Card, CardTitle } from "@/components/ui/card";
import { TBody, TD, TH, THead, TR, Table } from "@/components/ui/table";
import { formatNumber as fmt } from "@/lib/format";
import { winNumber } from "@/winNumber";
import { ErrorText } from "@/components/ui/error-text";
import { SlottedHeader } from "@/components/layout/AppPage";
import { LoadingText } from "@/components/ui/loading-text";
import { isLead, unitOf } from "./helpers";
import { FigureBand } from "@/components/ui/stat-tiles";
import { StatusText } from "@/components/ui/notice";

const SAVE_STATUS = {
  saving: ["Saving…", "text-muted-foreground"],
  saved: ["Saved", "text-primary"],
  failed: ["Not saved, try again", "text-bad-foreground"],
};

// A slider moves the screen at once and saves only when the user lets go.
function TargetRow({ target, draft, onDraft, onSettle }) {
  const { mutate } = useUpdateTarget();
  const [status, setStatus] = useState("");
  const slider = useRef(null);
  const saved = Math.round(target.projected_turnout_pct || 60);
  const pct = draft ?? saved;
  const needed = draft == null ? target.votes_needed : winNumber(target.registered_voters, draft);
  const name = target.centre_name || target.ward_name;
  const known = useRef(saved);  // the value saved or on its way; a release with it sends nothing
  useEffect(() => { if (status !== "saving") known.current = saved; }, [status, saved]);

  // Saves on release or a key press, not on every move.
  // "change" alone is not enough: Chromium skips it when a drag ends where it started.
  useEffect(() => {
    const el = slider.current;
    const save = () => {
      const value = Number(el.value);
      if (value === known.current) return;
      known.current = value;
      setStatus("saving");
      mutate(
        { id: target.id, projected_turnout_pct: value },
        {
          onSuccess: () => { setStatus("saved"); onSettle(target.id, value, false); },
          onError: () => { setStatus("failed"); onSettle(target.id, value, true); },
        },
      );
    };
    el.addEventListener("change", save);
    el.addEventListener("pointerup", save);
    return () => {
      el.removeEventListener("change", save);
      el.removeEventListener("pointerup", save);
    };
  }, [target.id, mutate, onSettle]);

  const shown = status && !(status === "saved" && draft != null);
  return (
    <TR>
      <TD className="font-semibold">{name}</TD>
      <TD numeric>{fmt(target.registered_voters)}</TD>
      <TD className="min-w-[220px]">
        <div className="flex items-center gap-3">
          <input ref={slider} type="range" min={40} max={85} value={pct} aria-label={`Turnout for ${name}`} onChange={(e) => { onDraft(target.id, Number(e.target.value)); setStatus((s) => (s === "saving" ? s : "")); }} className="h-11 flex-1 cursor-pointer accent-primary" />
          <span className="w-10 text-right font-bold tabular-nums">{pct}%</span>
        </div>
        {shown && <div className={`text-small font-semibold ${SAVE_STATUS[status][1]}`}>{SAVE_STATUS[status][0]}</div>}
      </TD>
      <TD numeric className="font-bold">{fmt(needed)}</TD>
    </TR>
  );
}

function Totals({ rows, turnoutOf, neededOf }) {
  const registered = rows.reduce((s, t) => s + (t.registered_voters || 0), 0);
  const cast = rows.reduce((s, t) => s + Math.round(((t.registered_voters || 0) * turnoutOf(t)) / 100), 0);
  const win = rows.reduce((s, t) => s + (neededOf(t) || 0), 0);
  const figures = [["Registered voters", fmt(registered)], ["Projected votes cast", fmt(cast)], ["Win number (50% + 1)", fmt(win), null, "text-accent"]];
  return <FigureBand label="Win number" figures={figures} />;
}

export default function Targets({ campaign, role }) {
  const { data, isLoading, error } = useTargets(campaign.id);
  const refresh = useRefreshTargets();
  // Win numbers follow a new voter register only when someone who runs the campaign asks.
  const refreshes = isLead(role);
  const action = refreshes ? (
    <Button variant="quiet" disabled={refresh.isPending} onClick={() => refresh.mutate(campaign.id)}
      title="Recompute every win number from the latest voter register; turnouts and committed votes stay.">
      {refresh.isPending ? "Refreshing…" : "Refresh targets"}
    </Button>
  ) : null;
  const { noun } = unitOf(campaign);
  const [drafts, setDrafts] = useState({});  // turnout per target id, until its save settles
  const onDraft = useCallback((id, pct) => setDrafts((d) => ({ ...d, [id]: pct })), []);
  // A failed save always puts the saved number back; a good one keeps a newer drag.
  const onSettle = useCallback((id, pct, failed) => setDrafts((d) => {
    if (!failed && d[id] !== pct) return d;
    const { [id]: _settled, ...rest } = d;
    return rest;
  }), []);
  const rows = data || [];
  const turnoutOf = (t) => drafts[t.id] ?? Math.round(t.projected_turnout_pct || 60);
  const neededOf = (t) => (t.id in drafts ? winNumber(t.registered_voters, drafts[t.id]) : t.votes_needed);
  return (
    <>
      <SlottedHeader context="Plan" title="Targets" sub={`Set the expected turnout in each ${noun}. The win number is half the projected votes cast, plus one.`} actions={action} />
      {refresh.isSuccess && <StatusText>Refreshed from the latest register: {fmt(refresh.data.units)} {noun}s, win number {fmt(refresh.data.win_number)}.</StatusText>}
      <ErrorText error={refresh.error} />
      {isLoading && <LoadingText />}
      <ErrorText error={error} />
      {data && (
        <>
          <Totals rows={rows} turnoutOf={turnoutOf} neededOf={neededOf} />
          <Card variant="outline" className="min-w-0 gap-3" role="region" aria-labelledby="turnout-h">
            <CardTitle id="turnout-h">Turnout per {noun}</CardTitle>
            <Table minWidth={600}>
              <THead><TR>
                <TH>{noun === "centre" ? "Centre" : "Ward"}</TH><TH align="right">Registered</TH><TH>Expected turnout</TH><TH align="right">Win number</TH>
              </TR></THead>
              <TBody>{rows.map((t) => <TargetRow key={t.id} target={t} draft={drafts[t.id]} onDraft={onDraft} onSettle={onSettle} />)}</TBody>
            </Table>
            <p className="text-small text-muted-foreground">Release a slider to save it. The overview and the {noun}s page update from the saved figures.</p>
          </Card>
        </>
      )}
    </>
  );
}
