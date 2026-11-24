// The field roles' target card: a mobilizer's own ward or centre, or a coordinator's whole area,
// with the set target and progress. Trying scenarios is for the campaign's leads.
import { useMobilizers, useTargets } from "@/api/hooks";
import { formatNumber as fmt } from "@/lib/format";
import { useAuth } from "@/store/auth";

export default function YourWard({ campaign, role }) {
  const user = useAuth((s) => s.user);
  const targets = useTargets(campaign.id).data || [];
  const mobilizers = useMobilizers(role === "mobilizer" ? campaign.id : undefined).data || [];
  let rows = targets;
  let label;
  if (role === "mobilizer") {
    const me = mobilizers.find((m) => m.user === user?.id);
    rows = me
      ? targets.filter((t) => (me.registration_centre ? t.registration_centre === me.registration_centre : t.ward === me.ward && !t.registration_centre))
      : [];
    label = rows[0] ? `Your ${rows[0].centre_name ? "centre" : "ward"}` : null;
  } else {
    label = "Your area";
  }
  if (!rows.length || !label) return null;
  const target = rows.reduce((sum, t) => sum + (t.votes_needed || 0), 0);
  const supporters = rows.reduce((sum, t) => sum + t.votes_committed, 0);
  const name = rows.length === 1 ? rows[0].centre_name || rows[0].ward_name : `${rows.length} ${rows[0].centre_name ? "centres" : "wards"}`;
  const progress = target ? Math.round((supporters / target) * 100) : 0;
  return (
    <section aria-label={label} className="mb-4 grid gap-3 rounded-card bg-ink p-5 text-on-dark sm:grid-cols-3">
      <div className="flex flex-col gap-1">
        <span className="text-small text-on-dark-muted">{label}</span>
        <span className="font-display text-[22px] font-extrabold">{name}</span>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-small text-on-dark-muted">Target</span>
        <span className="font-display text-[28px] font-extrabold tabular-nums text-accent">{fmt(target)}</span>
      </div>
      <div className="flex flex-col gap-1">
        <span className="text-small text-on-dark-muted">Supporters</span>
        <span className="font-display text-[28px] font-extrabold tabular-nums">{fmt(supporters)} <span className="text-ui font-semibold text-on-dark-muted">({progress}%)</span></span>
      </div>
    </section>
  );
}
