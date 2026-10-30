import { Card } from "./controls";

const StrategyPanel = ({ notes }) => (
  <Card pad={20} className="strategy">
    <div className="card-title">Strategy read</div>
    <div className="card-sub">Computed from your targets, events and mobilizers.</div>
    <div className="notes">
      {(notes || []).map((n, i) => (
        <div key={i} className={`note tone-${n.tone === "go" ? "good" : "warn"}`}>
          <div className="note-title">{n.title}</div>
          <div className="note-text">{n.text}</div>
        </div>
      ))}
      {(!notes || notes.length === 0) && <div className="muted">No flags right now — coverage looks balanced.</div>}
    </div>
  </Card>
);

export default StrategyPanel;
