import { useState } from "react";
import { Modal } from "../../components/ui";
import { useCentres, useScheduleEvent } from "../../api/hooks";
import { Btn, Label, PrimaryBtn } from "./controls";

// In an MCA race an event is held at one registration centre, which its sign-ups count toward.
export default function ScheduleEventForm({ campaignId, wardOptions, byCentre, onClose }) {
  const schedule = useScheduleEvent();
  const [title, setTitle] = useState(""); const [venue, setVenue] = useState(""); const [date, setDate] = useState("");
  const [ward, setWard] = useState(wardOptions[0]?.id || "");
  const [centre, setCentre] = useState("");
  const centresQuery = useCentres(byCentre ? ward : null);
  const centres = centresQuery.data || [];
  const ok = title.trim() && ward && date && !centresQuery.isFetching && (!byCentre || !centres.length || centre);
  return (
    <Modal title="Schedule event" sub="Attendance is recorded after it happens." onClose={onClose}>
      <Label>Event title</Label><input className="app-field" value={title} onChange={(e) => setTitle(e.target.value)} />
      <div className="field-gap" /><Label>Ward</Label>
      <select className="app-field" value={ward} onChange={(e) => { setWard(e.target.value); setCentre(""); }}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</select>
      {byCentre && centres.length > 0 && (
        <>
          <div className="field-gap" /><Label>Registration centre</Label>
          <select aria-label="Registration centre" className="app-field" value={centre} onChange={(e) => setCentre(e.target.value)}>
            <option value="">Pick the centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </select>
        </>
      )}
      <div className="field-gap" /><Label>Venue</Label><input className="app-field" value={venue} onChange={(e) => setVenue(e.target.value)} />
      <div className="field-gap" /><Label>Date</Label><input type="date" className="app-field" value={date} onChange={(e) => setDate(e.target.value)} />
      {schedule.isError && <div className="form-error">{schedule.error.message}</div>}
      <div className="flex justify-end gap-2 form-actions">
        <Btn onClick={onClose}>Cancel</Btn>
        <PrimaryBtn disabled={!ok || schedule.isPending} onClick={() => schedule.mutate({ campaign: campaignId, ward, registration_centre: centre || null, title: title.trim(), venue: venue.trim(), scheduled_date: date, status: "planned" }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule event"}</PrimaryBtn>
      </div>
    </Modal>
  );
}

