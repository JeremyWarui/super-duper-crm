import { useState } from "react";

/**
 * Form state from `initial`: [form, setForm, set], where `set(key)` is an input's onChange that
 * writes its value (or a checkbox's checked) under `key`.
 */
export function useForm(initial) {
  const [form, setForm] = useState(initial);
  const set = (key) => (e) => {
    const value = e.target.type === "checkbox" ? e.target.checked : e.target.value;
    setForm((f) => ({ ...f, [key]: value }));
  };
  return [form, setForm, set];
}
