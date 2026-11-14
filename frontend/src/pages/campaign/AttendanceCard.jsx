import { useRecordEvent } from "@/api/hooks";
import { Button } from "@/components/ui/button";
import { useDraft } from "@/lib/draft";
import SendError from "./SendError";
import { TOO_MANY_ATTENDED, attendanceOk } from "./helpers";
import { ErrorText } from "@/components/ui/error-text";

const toCount = (v) => Math.max(0, Math.min(100000, Number.parseInt(String(v).replace(/\D/g, ""), 10) || 0));

function Counter({ label, value, onChange }) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-[14px] bg-ground-app p-2.5">
      <button type="button" aria-label={`Fewer ${label.toLowerCase()}`} onClick={() => onChange(Math.max(0, value - 1))}
        className="size-[52px] flex-none cursor-pointer rounded-xl border border-line-control bg-white text-[26px] font-bold">−</button>
      <label className="flex min-w-0 flex-col items-center">
        <input inputMode="numeric" aria-label={label} value={String(value)} onChange={(e) => onChange(toCount(e.target.value))} onFocus={(e) => e.target.select()}
          className="h-12 w-full min-w-0 bg-transparent text-center font-display text-[40px] leading-none font-extrabold tabular-nums outline-none focus-visible:rounded-md focus-visible:outline-[3px] focus-visible:outline-primary/25" />
        <span className="text-small font-semibold text-muted-foreground">{label.toLowerCase()}</span>
      </label>
      <button type="button" aria-label={`More ${label.toLowerCase()}`} onClick={() => onChange(value + 1)}
        className="size-[52px] flex-none cursor-pointer rounded-xl bg-primary text-[26px] font-bold text-primary-foreground">+</button>
    </div>
  );
}

/** Counts who was reached and who came, kept on the device until saved. Saving marks the event done. */
export default function AttendanceCard({ event }) {
  const record = useRecordEvent();
  const [counts, setCounts, clear] = useDraft(`record:${event.id}`, { reached: 0, attended: 0 });
  const over = counts.attended > counts.reached;
  const ok = attendanceOk(counts.reached, counts.attended);
  const send = () => record.mutateAsync({ id: event.id, number_reached: counts.reached, number_attended: counts.attended }).then(clear, () => {});
  return (
    <div className="flex flex-col gap-3">
      <Counter label="Reached" value={counts.reached} onChange={(reached) => setCounts((c) => ({ ...c, reached }))} />
      <Counter label="Attended" value={counts.attended} onChange={(attended) => setCounts((c) => ({ ...c, attended }))} />
      <ErrorText error={over && TOO_MANY_ATTENDED} className="text-ui" />
      <SendError error={record.error} pending={record.isPending} onRetry={send} />
      <Button loading={record.isPending} variant="accent" size="lg" className="w-full" disabled={!ok || record.isPending} onClick={send}>
        {record.isPending ? "Saving…" : "Save attendance"}
      </Button>
      <p className="text-small text-muted-foreground">Counts are kept on this phone until they are saved. Saving marks the event done.</p>
    </div>
  );
}
