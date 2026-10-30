import { useCallback, useEffect, useRef, useState } from "react";
import { winNumber } from "../../winNumber";
import { formatNumber as fmt } from "../../lib/format";
import { PageTitle } from "../../components/ui";
import { useTargets, useUpdateTarget } from "../../api/hooks";
import { Card, ErrorMsg, Loading } from "./controls";

const SAVE_STATUS = {
  saving: ["Saving…", "muted"],
  saved: ["Saved", "text-good"],
  failed: ["Not saved, try again", "text-bad"],
};

// A slider moves the screen at once and saves only when the user lets go.
function TargetRow({ target, draft, onDraft, onSettle }) {
  const { mutate } = useUpdateTarget();
  const [status, setStatus] = useState("");
  const slider = useRef(null);
  const saved = Math.round(target.projected_turnout_pct || 60);
  const pct = draft ?? saved;
  const needed = draft == null ? target.votes_needed : winNumber(target.registered_voters, draft);
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

  return (
    <tr>
      <td className="strong">{target.centre_name || target.ward_name}</td>
      <td className="num">{fmt(target.registered_voters)}</td>
      <td className="center">
        <input ref={slider} type="range" min={40} max={85} value={pct} aria-label={`Turnout for ${target.centre_name || target.ward_name}`} onChange={(e) => { onDraft(target.id, Number(e.target.value)); setStatus((s) => (s === "saving" ? s : "")); }} className="slider" />
        <span className="slider-value">{pct}%</span>
        {status && !(status === "saved" && draft != null) && <div className={`save-status ${SAVE_STATUS[status][1]}`}>{SAVE_STATUS[status][0]}</div>}
      </td>
      <td className="num figure">{fmt(needed)}</td>
    </tr>
  );
}

export default function Targets({ campaign }) {
  const campaignId = campaign.id;
  const { data, isLoading, error } = useTargets(campaignId);
  const [drafts, setDrafts] = useState({});  // turnout per target id, until its save settles
  const onDraft = useCallback((id, pct) => setDrafts((d) => ({ ...d, [id]: pct })), []);
  // A failed save always puts the saved number back; a good one keeps a newer drag.
  const onSettle = useCallback((id, pct, failed) => setDrafts((d) => {
    if (!failed && d[id] !== pct) return d;
    const { [id]: _settled, ...rest } = d;
    return rest;
  }), []);
  if (isLoading) return <Loading />; if (error) return <ErrorMsg error={error} />;
  const rows = data || [];
  const total = rows.reduce((s, t) => s + ((t.id in drafts ? winNumber(t.registered_voters, drafts[t.id]) : t.votes_needed) || 0), 0);
  return (
    <>
      <PageTitle title="Targets — the win number" sub="Set projected turnout per unit; the win number recomputes on the server." />
      <Card pad={0}><div className="table-scroll">
        <table className="table">
          <thead><tr><th>Unit</th><th className="num">Registered</th><th className="center">Turnout %</th><th className="num">Votes needed</th></tr></thead>
          <tbody>{rows.map((t) => <TargetRow key={t.id} target={t} draft={drafts[t.id]} onDraft={onDraft} onSettle={onSettle} />)}</tbody>
          <tfoot><tr className="total-row"><td className="total-label"  colSpan={3}>TOTAL WIN NUMBER</td><td className="num total-value">{fmt(total)}</td></tr></tfoot>
        </table>
      </div></Card>
      <div className="page-note">Release a slider to save — the server recomputes the win number and the dashboard updates.</div>
    </>
  );
}

