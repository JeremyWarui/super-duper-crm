import { useState } from "react";
import { isEmail } from "../../lib/email";
import { Label } from "./controls";

// Name, username, email and phone for a new login; `body` is what the team routes take.
export function useLoginFields() {
  const [form, setForm] = useState({ name: "", username: "", email: "", phone: "" });
  const ok = !!form.name.trim() && form.username.trim().length >= 3 && isEmail(form.email);
  const [first, ...rest] = form.name.trim().split(/\s+/);
  const body = { username: form.username.trim().toLowerCase(), first_name: first, last_name: rest.join(" "), phone: form.phone.trim(), email: form.email.trim() };
  const set = (key) => (e) => setForm({ ...form, [key]: e.target.value });
  return { form, set, ok, body };
}

export default function LoginFields({ form, set }) {
  return (
    <>
      <Label>Full name</Label><input aria-label="Full name" className="app-field" value={form.name} onChange={set("name")} />
      <div className="field-gap" /><Label>Username</Label><input aria-label="Username" className="app-field" value={form.username} onChange={set("username")} placeholder="amina" />
      <div className="field-gap" /><Label>Email</Label><input aria-label="Email" type="email" className="app-field" value={form.email} onChange={set("email")} placeholder="amina@example.com" />
      <div className="field-gap" /><Label>Phone</Label><input aria-label="Phone" className="app-field" value={form.phone} onChange={set("phone")} />
    </>
  );
}
