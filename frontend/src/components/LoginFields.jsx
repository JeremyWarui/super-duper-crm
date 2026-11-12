import { Field, Input } from "@/components/ui/input";
import { isEmail } from "@/lib/email";
import { useForm } from "@/lib/form";

// Name, username, email and phone for a new login; `body` is what the team routes take.
export function useLoginFields() {
  const [form, , set] = useForm({ name: "", username: "", email: "", phone: "" });
  const ok = !!form.name.trim() && loginReady(form);
  const body = loginBody(form);
  return { form, set, ok, body };
}

const LABEL = { name: "Full name", first_name: "First name", last_name: "Last name", username: "Username", email: "Email", phone: "Phone" };
const PLACEHOLDER = { username: "amina", email: "amina@example.com", phone: "0712 345678" };
const MAX = { username: 150, email: 254 };

/**
 * The login boxes named by `fields`, read from `form` and written by `set(key)(event)`; `who` starts
 * each label ("Candidate username"), `emailHint` sits under the email box and `placeholders` replaces the sample text.
 */
export default function LoginFields({ form, set, fields = ["name", "username", "email", "phone"], who, emailHint, placeholders }) {
  return fields.map((key) => (
    <Field key={key} label={who ? `${who} ${LABEL[key].toLowerCase()}` : LABEL[key]} hint={key === "email" ? emailHint : undefined}>
      <Input
        type={key === "email" ? "email" : "text"}
        autoComplete={key === "username" || key === "email" ? "off" : undefined}
        placeholder={{ ...PLACEHOLDER, ...placeholders }[key]}
        maxLength={MAX[key]}
        value={form[key]}
        onChange={set(key)}
      />
    </Field>
  ));
}

/** Whether a new login's username (3 or more characters) and email are usable. */
export const loginReady = ({ username, email }) => username.trim().length >= 3 && isEmail(email);

/** A new login's name, username, email and phone as the team routes take them. */
export function loginBody({ name, username, email, phone }) {
  const [first, ...rest] = name.trim().split(/\s+/);
  return { username: username.trim().toLowerCase(), first_name: first, last_name: rest.join(" "), phone: phone.trim(), email: email.trim() };
}
