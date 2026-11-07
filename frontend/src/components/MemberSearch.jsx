// Find a party member by name or phone and pick one; the caller runs the search.
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ErrorText } from "@/components/ui/error-text";
import { Field, Input } from "@/components/ui/input";

const detailOf = (m) => m.ward?.name || m.phone;

/**
 * `results` is the matches to offer (undefined while no search runs); `empty` shows when a
 * finished search (`loading` false) matched nobody. `onPick(null)` is "Choose someone else".
 */
export default function MemberSearch({ label, hint, placeholder, query, onQuery, results, loading, error, empty, picked, onPick }) {
  if (picked)
    return (
      <Card variant="tinted" className="items-start gap-2">
        <span className="text-small font-semibold">{label}</span>
        <span className="flex flex-col">
          <span className="font-semibold">{picked.full_name}</span>
          <span className="text-ui text-muted-foreground">{detailOf(picked)}</span>
        </span>
        <Button shape="rounded" variant="quiet" size="sm" onClick={() => onPick(null)}>Choose someone else</Button>
      </Card>
    );
  return (
    <div className="flex flex-col gap-2">
      <Field label={label} hint={hint}>
        <Input placeholder={placeholder} maxLength={100} value={query} onChange={(e) => onQuery(e.target.value)} />
      </Field>
      <ErrorText error={error} className="text-small" />
      {results?.length > 0 && (
        <ul className="flex flex-col divide-y divide-line-soft overflow-hidden rounded-lg border border-line-soft" aria-label="Matching members">
          {results.slice(0, 8).map((m) => (
            <li key={m.id}>
              <Button variant="ghost" className="h-auto min-h-11 w-full flex-wrap justify-between gap-x-2 gap-y-0 rounded-none px-3 py-1.5 text-left font-normal whitespace-normal" onClick={() => onPick(m)}>
                <span className="font-semibold">{m.full_name}</span>
                {detailOf(m) && <><span className="sr-only"> · </span><span className="text-small text-muted-foreground">{detailOf(m)}</span></>}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {results?.length === 0 && !loading && <p className="text-small text-muted-foreground">{empty}</p>}
    </div>
  );
}
