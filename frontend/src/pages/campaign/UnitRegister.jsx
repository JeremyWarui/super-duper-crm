import { useMemo, useState } from "react";
import { formatNumber as fmt } from "../../lib/format";
import { Badge, Bar } from "../../components/ui";
import { Btn, Card } from "./controls";
import { holderOf, statusOf } from "./helpers";

export default function UnitRegister({ units, mobilizers = [], onAssign }) {
  const [sortKey, setSortKey] = useState("opportunity");
  const sorted = useMemo(() => {
    const a = [...units];
    if (sortKey === "opportunity") a.sort((x, y) => y.gap - x.gap);
    else if (sortKey === "needed") a.sort((x, y) => y.needed - x.needed);
    else a.sort((x, y) => x.progress - y.progress);
    return a;
  }, [units, sortKey]);
  return (
    <Card pad={0}>
      <div className="flex flex-wrap items-center justify-between gap-2 card-head">
        <div className="card-title">Targeting</div>
        <div className="flex gap-1 segmented">
          {[["opportunity", "Biggest gap"], ["needed", "Win number"], ["progress", "Least progress"]].map(([k, l]) => (
            <button key={k} type="button" aria-pressed={sortKey === k} onClick={() => setSortKey(k)} className={`segmented-option ${sortKey === k ? "segmented-option-on" : ""}`.trim()}>{l}</button>
          ))}
        </div>
      </div>
      <div className="table-scroll">
        <table className="table">
          <thead><tr>
            <th>Unit</th>
            <th className="num">Need</th>
            <th>Progress</th>
            <th className="center">Events</th>
            <th>Mobilizer</th>
          </tr></thead>
          <tbody>
            {sorted.map((u) => {
              const st = statusOf(u.progress);
              return (
                <tr key={u.unit}>
                  <td><div className="strong">{u.unit}</div><div className="cell-badge"><Badge text={st.label} tone={st.tone} /></div></td>
                  <td className="num figure">{fmt(u.needed)}</td>
                  <td className="progress-cell"><Bar pct={u.progress * 100} tone={st.tone} /><div className="cell-meta">{fmt(u.committed)} · {Math.round(u.progress * 100)}%</div></td>
                  <td className={`center figure ${u.events === 0 ? "text-bad" : ""}`.trim()}>{u.events}</td>
                  <td><MobilizerCell holder={holderOf(mobilizers, u)} onAssign={onAssign && ((holder) => onAssign(u, holder))} /></td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

function MobilizerCell({ holder, onAssign }) {
  if (holder) {
    return <div className="flex items-center gap-2"><span className="strong">{holder.full_name}</span>{onAssign && <Btn onClick={() => onAssign(holder)}>Change</Btn>}</div>;
  }
  return onAssign ? <Btn onClick={() => onAssign(null)}>Assign</Btn> : <span className="text-bad">None</span>;
}

