import { useState } from "react";
import { Label } from "./controls";
import { loginBody, loginReady } from "./helpers";

// Name, username, email and phone for a new login; `body` is what the team routes take.
export function useLoginFields() {
  const [form, setForm] = useState({ name: "", username: "", email: "", phone: "" });
  const ok = !!form.name.trim() && loginReady(form);
  const body = loginBody(form);
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
