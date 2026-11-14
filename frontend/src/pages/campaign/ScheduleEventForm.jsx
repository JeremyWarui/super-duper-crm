import { useState } from "react";
import { useCentres, useScheduleEvent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/dialog";
import { ErrorText } from "@/components/ui/error-text";
import { FormActions } from "@/components/ui/form-actions";
import { Field, Input, NativeSelect } from "@/components/ui/input";

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
    <Dialog title="Schedule event" description="Attendance is recorded after it happens." onClose={onClose}>
      <Field label="Event title"><Input value={title} onChange={(e) => setTitle(e.target.value)} /></Field>
      <Field label="Ward">
        <NativeSelect value={ward} onChange={(e) => { setWard(e.target.value); setCentre(""); }}>{wardOptions.map((w) => <option key={w.id} value={w.id}>{w.name}</option>)}</NativeSelect>
      </Field>
      {byCentre && centres.length > 0 && (
        <Field label="Registration centre">
          <NativeSelect aria-label="Registration centre" value={centre} onChange={(e) => setCentre(e.target.value)}>
            <option value="">Pick the centre</option>
            {centres.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
          </NativeSelect>
        </Field>
      )}
      <Field label="Venue"><Input value={venue} onChange={(e) => setVenue(e.target.value)} /></Field>
      <Field label="Date"><Input type="date" value={date} onChange={(e) => setDate(e.target.value)} /></Field>
      <ErrorText error={schedule.isError && schedule.error} />
      <FormActions>
        <Button variant="quiet" onClick={onClose}>Cancel</Button>
        <Button loading={schedule.isPending} disabled={!ok || schedule.isPending} onClick={() => schedule.mutate({ campaign: campaignId, ward, registration_centre: centre || null, title: title.trim(), venue: venue.trim(), scheduled_date: date, status: "planned" }, { onSuccess: onClose })}>{schedule.isPending ? "Saving…" : "Schedule event"}</Button>
      </FormActions>
    </Dialog>
  );
}
