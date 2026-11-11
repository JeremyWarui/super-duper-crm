// Profession, ways to help and preferred contact: the volunteer questions every sign-up form asks.
import { Field, Input, NativeSelect } from "@/components/ui/input";
import { AREAS, CONTACT_METHODS, PROFESSIONS } from "@/lib/labels";

/** The answers before anything is picked. */
export const NO_VOLUNTEER = { profession: "", profession_other: "", areas: [], area_other: "", preferred_contact: "" };

/** Whether every question is answered, "other" included. */
export const volunteerReady = (v) =>
  Boolean(v.profession && (v.profession !== "other" || v.profession_other.trim()) && v.areas.length > 0 &&
    (!v.areas.includes("other") || v.area_other.trim()) && v.preferred_contact);

/** The answers as sent: the "other" texts trimmed, and blank when "other" is not picked. */
export const volunteerBody = (v) => ({
  profession: v.profession,
  profession_other: v.profession === "other" ? v.profession_other.trim() : "",
  areas: v.areas,
  area_other: v.areas.includes("other") ? v.area_other.trim() : "",
  preferred_contact: v.preferred_contact,
});

/** A checkbox inside a pill-shaped label, tinted once ticked. */
export const CHECK_PILL = "flex min-h-11 cursor-pointer items-center gap-2 rounded-full border-[1.5px] border-line-control bg-white px-3.5 text-small font-semibold has-[:checked]:border-primary has-[:checked]:bg-primary-tint";

/** The questions; `onChange(patch)` gets the changed answers. `pills` shows the ways to help as pills. */
export default function VolunteerFields({ value, onChange, pills = false }) {
  const toggle = (area) => onChange({ areas: value.areas.includes(area) ? value.areas.filter((a) => a !== area) : [...value.areas, area] });
  return (
    <>
      <Field label="Profession">
        <NativeSelect value={value.profession} onChange={(e) => onChange({ profession: e.target.value })}>
          <option value="">Pick your profession</option>
          {PROFESSIONS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </NativeSelect>
      </Field>
      {value.profession === "other" ? (
        <Field label="Your profession"><Input maxLength={100} value={value.profession_other} onChange={(e) => onChange({ profession_other: e.target.value })} /></Field>
      ) : null}
      <fieldset className="flex flex-col gap-2">
        <legend className="mb-2 text-small font-semibold">How would you like to help?</legend>
        <div className={pills ? "flex flex-wrap gap-2" : "grid grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-x-4 gap-y-1"}>
          {AREAS.map(([v, l]) => (
            <label key={v} className={pills ? CHECK_PILL : "flex min-h-11 items-center gap-2.5 text-body"}>
              <input type="checkbox" className="size-[18px] accent-primary" checked={value.areas.includes(v)} onChange={() => toggle(v)} />
              {l}
            </label>
          ))}
        </div>
      </fieldset>
      {value.areas.includes("other") ? (
        <Field label="Other ways to help"><Input maxLength={100} value={value.area_other} onChange={(e) => onChange({ area_other: e.target.value })} /></Field>
      ) : null}
      <Field label="Preferred contact">
        <NativeSelect value={value.preferred_contact} onChange={(e) => onChange({ preferred_contact: e.target.value })}>
          <option value="">Pick a contact method</option>
          {CONTACT_METHODS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </NativeSelect>
      </Field>
    </>
  );
}
