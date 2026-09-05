// src/store/auth.js
// Holds the auth token and the logged-in user (with their role), persisted to
// localStorage so a refresh keeps you signed in. React Query handles server data;
// this store handles only "who am I".

import { create } from "zustand";
import { persist } from "zustand/middleware";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export const useAuth = create(
  persist(
    (set) => ({
      token: null,
      user: null, // { id, username, full_name, role }

      async login(username, password) {
        const res = await fetch(`${BASE}/auth/login/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ username, password }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.non_field_errors?.[0] || "Wrong username or password.");
        }
        set({ token: data.token, user: data.user });
        return data.user;
      },

      async register(details) {
        const res = await fetch(`${BASE}/auth/register/`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(details),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
          throw new Error(data?.detail || "Could not create the account.");
        }
        set({ token: data.token, user: data.user });
        return data.user;
      },

      logout: () => set({ token: null, user: null }),
    }),
    { name: "campaign-auth" }
  )
);
