// Form drafts kept on the device until they are sent, per signed-in user.
import { useCallback, useState } from "react";
import { useAuth } from "@/store/auth";

export { clearDrafts } from "@/store/auth";

const PREFIX = "draft:";

const read = (key) => {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
};

const write = (key, value) => {
  try {
    if (value === null) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or blocked: the form still works, it just isn't kept.
  }
};

/**
 * Like useState, but the value survives a reload until `clear()` is called.
 * `name` should name the form and what it is for, e.g. `record:<event id>`.
 */
export function useDraft(name, initial) {
  const userId = useAuth((s) => s.user?.id) || "anon";
  const key = `${PREFIX}${userId}:${name}`;
  const [state, setState] = useState(() => ({ key, value: { ...initial, ...read(key) } }));
  const value = state.key === key ? state.value : { ...initial, ...read(key) };
  const set = useCallback((next) => {
    setState((s) => {
      const base = s.key === key ? s.value : { ...initial, ...read(key) };
      const v = typeof next === "function" ? next(base) : next;
      write(key, v);
      return { key, value: v };
    });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  const clear = useCallback(() => {
    write(key, null);
    setState({ key, value: initial });
  }, [key]); // eslint-disable-line react-hooks/exhaustive-deps
  return [value, set, clear];
}

/** A failure with no HTTP status: the request never reached the server. */
export const unsent = (error) => Boolean(error) && !error.status;
