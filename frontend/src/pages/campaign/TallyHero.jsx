import { formatNumber as fmt } from "../../lib/format";
import { Card } from "./controls";

export default function TallyHero({ s }) {
  const crossed = s.committed >= s.win_number;
  const cast = s.total_cast || s.win_number * 2;
  const tone = crossed ? "good" : "warn";
  return (
    <>
      <Card pad={20} className={`hero ${crossed ? "hero-crossed" : ""}`.trim()}>
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div className="eyebrow">VOTES TO WIN THE SEAT</div>
          <div className="hero-meta">{s.units.length} units · {fmt(cast)} projected votes cast</div>
        </div>
        <div className="flex flex-wrap items-end gap-6 hero-figures">
          <span className="hero-number">{fmt(s.win_number)}</span>
          <div className="hero-progress">
            <div className={`hero-committed text-${tone}`}>{fmt(s.committed)} committed</div>
            <div className="hero-meta">{s.progress_pct}% there · {fmt(Math.max(s.win_number - s.committed, 0))} to go</div>
          </div>
        </div>
        <div className="winbar">
          <div className="winbar-track" />
          <div className={`winbar-fill tone-${tone}`} style={{width: `${(s.committed / cast) * 100}%`}} />
          <div className="winbar-line" style={{left: `${(s.win_number / cast) * 100}%`}} />
          <div className="winbar-label" style={{left: `${(s.win_number / cast) * 100}%`}}>WIN LINE</div>
        </div>
      </Card>
      <div className="kpi-grid">
        {[["Registered voters", fmt(s.total_registered)], ["Units covered", `${s.units.filter((u) => u.events > 0).length} / ${s.units.length}`],
          ["Mobilizers", `${s.units.filter((u) => u.has_mobilizer).length} / ${s.units.length}`], ["Units behind", String(s.units.filter((u) => u.progress < 0.6).length)]].map(([k, v]) => (
          <Card key={k} pad={20} className="kpi"><div className="kpi-label">{k}</div><div className="kpi-value">{v}</div></Card>
        ))}
      </div>
    </>
  );
}

