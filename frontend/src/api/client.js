// src/api/client.js
// One place that talks to Django. Attaches the token, sends/receives JSON,
// turns DRF error payloads into a readable message, and logs you out on a 401.

import { useAuth } from "../store/auth";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

export async function api(path, { method = "GET", body } = {}) {
  const { token } = useAuth.getState();

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    useAuth.getState().logout();
    throw new Error("Your session expired — please sign in again.");
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) {
    // DRF errors look like {"detail": "..."} or {"field": ["msg"]}
    const first = data?.detail || (data && Object.values(data)[0]);
    const msg = Array.isArray(first) ? first[0] : first || "Request failed.";
    throw new Error(msg);
  }
  return data;
}
