// src/store/auth.js
// Holds the auth token and the logged-in user (with their role), persisted to
// localStorage so a refresh keeps you signed in. React Query handles server data;
// this store handles only "who am I".

import { create } from "zustand";
import { persist } from "zustand/middleware";
import { BASE } from "../api/base";

export function clearDrafts() {
  try {
    Object.keys(localStorage).filter((k) => k.startsWith("draft:")).forEach((k) => localStorage.removeItem(k));
  } catch {
    // Storage blocked: nothing was kept.
  }
}

export const useAuth = create(
  persist(
    (set) => ({
      token: null,
      user: null, // { id, username, full_name, role, kind, member_account }

      async login(email, password) {
        const res = await fetch(`${BASE}/auth/login/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.non_field_errors?.[0] || data?.detail || "Wrong email or password.");
        }
        set({ token: data.token, user: data.user });
        return data.user;
      },

      // Takes the session a sign-in link opened.
      adopt: ({ token, user }) => set({ token, user }),

      // Drafts can hold supporters' names and phones; a shared phone must not keep them.
      logout: () => {
        clearDrafts();
        set({ token: null, user: null });
      },

      // An expired session keeps drafts: the same person signs back in to send them.
      expire: () => set({ token: null, user: null }),
    }),
    { name: "campaign-auth" }
  )
);
