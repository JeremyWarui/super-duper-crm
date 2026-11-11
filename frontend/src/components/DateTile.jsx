import { formatDay } from "@/lib/format";

/** A date as a tile: `top` (the short month, or a weekday) over the day number; "No date" without one. */
export default function DateTile({ date, top = { month: "short" }, tone = "tint" }) {
  return (
    <span className={`flex h-[72px] w-16 flex-none flex-col items-center justify-center rounded-lg ${tone === "accent" ? "bg-accent text-ink" : "bg-primary-tint text-primary"}`}>
      {date ? (
        <>
          <span className="text-[11px] font-extrabold uppercase tracking-[0.08em]">{formatDay(date, top)}</span>
          <span className="font-display text-[26px] leading-none font-extrabold">{formatDay(date, { day: "numeric" })}</span>
        </>
      ) : <span className="text-meta font-bold">No date</span>}
    </span>
  );
}
