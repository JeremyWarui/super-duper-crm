import { formatNumber as fmt } from "../../lib/format";
import { Badge } from "../../components/ui";
import { Btn, Card } from "./controls";

// ---- events + supporters lists -------------------------------------------
export default function EventList({ events, showActions, onRecord, onInvite, onQr }) {
  return (
    <Card pad={0}><div className="table-scroll">
      <table className="table">
        <thead><tr>
          <th>Event</th><th>Ward</th>
          <th>Date</th><th>Status</th>
          <th className="num">Reached</th><th className="num">Attended</th>
          <th className="num">Turnout</th>
          <th className="num">Signed up</th>
          {showActions && <th className="num">Invite</th>}
          {onQr && <th className="num">Sign-up</th>}
        </tr></thead>
        <tbody>
          {events.map((e) => {
            const done = e.status === "done";
            return (
              <tr key={e.id}>
                <td className="strong">{e.title}<div className="cell-sub">{e.venue || "—"}</div></td>
                <td>{e.ward_name}</td>
                <td>{e.scheduled_date ? new Date(e.scheduled_date).toLocaleDateString("en-GB", { day: "numeric", month: "short" }) : "—"}</td>
                <td><Badge text={done ? "Done" : "Planned"} tone={done ? "good" : "warn"} /></td>
                <td className="num">{done ? fmt(e.number_reached) : (showActions ? <Btn onClick={() => onRecord(e)}>Record</Btn> : "—")}</td>
                <td className="num">{done ? fmt(e.number_attended) : "—"}</td>
                <td className="num">{done ? `${e.turnout_pct}%` : "—"}</td>
                <td className="num">{fmt(e.signups)}{e.number_attended > 0 && <span className="muted"> ({Math.round((e.signups / e.number_attended) * 100)}%)</span>}</td>
                {showActions && <td className="actions-cell"><Btn onClick={() => onInvite(e)}>Invite</Btn></td>}
                {onQr && <td className="actions-cell">{e.signup_code && <Btn onClick={() => onQr(e)}>{e.signups_open ? "Sign-up QR" : "Closed"}</Btn>}</td>}
              </tr>
            );
          })}
          {events.length === 0 && <tr><td colSpan={10} className="empty-row">No events yet.</td></tr>}
        </tbody>
      </table>
    </div></Card>
  );
}

