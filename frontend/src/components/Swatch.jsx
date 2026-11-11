// A colour box with a picker and its contrast against the text that sits on it.
import { Field, Input } from "@/components/ui/input";
import { INK, MIN_CONTRAST, WHITE, contrast, isHex } from "@/lib/contrast";

/** One colour, checked against `against` (the `textOn` text colour) the way the server checks it. */
export function Swatch({ label, value, onChange, against, textOn }) {
  const ok = isHex(value) && contrast(value, against) >= MIN_CONTRAST;
  return (
    <Field label={label} hint={isHex(value) ? `Contrast with ${textOn} text: ${contrast(value, against).toFixed(1)} (needs ${MIN_CONTRAST})` : "Use #rrggbb."}>
      <div className="flex items-center gap-2">
        <input type="color" aria-label={`${label} picker`} value={isHex(value) ? value : "#000000"} onChange={(e) => onChange(e.target.value)} className="h-11 w-14 flex-none cursor-pointer rounded-lg border border-line-control bg-white p-1" />
        <Input value={value ?? ""} maxLength={7} onChange={(e) => onChange(e.target.value)} aria-invalid={!ok} />
        <span className="flex h-11 flex-none items-center rounded-lg px-3 text-ui font-bold" style={{ background: isHex(value) ? value : "#fff", color: against }}>Aa</span>
      </div>
    </Field>
  );
}

/** The site's primary and secondary colours from `form`; `set(key)(value)` writes one. */
export function ColourFields({ form, set }) {
  return (
    <>
      <Swatch label="Primary colour" value={form.primary_colour} onChange={set("primary_colour")} against={WHITE} textOn="white" />
      <Swatch label="Secondary colour" value={form.secondary_colour} onChange={set("secondary_colour")} against={INK} textOn="dark" />
    </>
  );
}
