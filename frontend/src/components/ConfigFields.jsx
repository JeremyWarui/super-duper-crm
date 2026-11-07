import { Field, Input, Textarea } from "@/components/ui/input";

/**
 * One labelled box per `[key, label, max, { rows, type, hint }]` field, read from `form` and written
 * by `set(key)(event)`: a text area when `rows` is given, else a one-line box.
 */
export default function ConfigFields({ fields, form, set }) {
  return fields.map(([key, label, max, { rows, type, hint } = {}]) => (
    <Field key={key} label={label} hint={hint}>
      {rows ? (
        <Textarea rows={rows} maxLength={max} value={form[key] ?? ""} onChange={set(key)} />
      ) : (
        <Input type={type || "text"} maxLength={max} value={form[key] ?? ""} onChange={set(key)} />
      )}
    </Field>
  ));
}
