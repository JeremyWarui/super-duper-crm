import { useState } from "react";
import { Field, Input } from "@/components/ui/input";
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
      <Field label="Full name"><Input aria-label="Full name" value={form.name} onChange={set("name")} /></Field>
      <Field label="Username"><Input aria-label="Username" value={form.username} onChange={set("username")} placeholder="amina" /></Field>
      <Field label="Email"><Input aria-label="Email" type="email" value={form.email} onChange={set("email")} placeholder="amina@example.com" /></Field>
      <Field label="Phone"><Input aria-label="Phone" value={form.phone} onChange={set("phone")} /></Field>
    </>
  );
}
