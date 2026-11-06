// src/api/client.js
// One place that talks to Django. Attaches the token, sends/receives JSON,
// turns DRF error payloads into a readable message, and logs you out on a 401.

import { useAuth } from "../store/auth";

const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

// `anonymous` leaves the token off, for the public pages anyone can open.
export async function api(path, { method = "GET", body, anonymous = false, headers = {} } = {}) {
  const token = anonymous ? null : useAuth.getState().token;

  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
      ...headers,
    },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401) {
    useAuth.getState().expire();
    throw Object.assign(new Error("Your session expired — please sign in again."), { status: 401 });
  }

  const data = res.status === 204 ? null : await res.json().catch(() => null);

  if (!res.ok) {
    // DRF errors look like {"detail": "..."} or {"field": ["msg"]}
    const first = data?.detail || (data && Object.values(data)[0]);
    const msg = Array.isArray(first) ? first[0] : first || "Request failed.";
    // `status` and `code` let a screen tell a closed campaign from any other refusal.
    throw Object.assign(new Error(msg), { status: res.status, code: data?.code });
  }
  return data;
}

// Fetches a file with the token and hands it to the browser as a download.
export async function download(path, filename) {
  const token = useAuth.getState().token;
  const res = await fetch(`${BASE}${path}`, {
    headers: token ? { Authorization: `Token ${token}` } : {},
  });
  if (res.status === 401) {
    useAuth.getState().expire();
    throw Object.assign(new Error("Your session expired — please sign in again."), { status: 401 });
  }
  if (!res.ok) {
    const data = await res.json().catch(() => null);
    throw new Error(data?.detail || "Download failed.");
  }
  const url = URL.createObjectURL(await res.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

// Sends one file as multipart form data, with the token; answers with the JSON reply.
export async function upload(path, file, fields = {}) {
  const token = useAuth.getState().token;
  const form = new FormData();
  form.append("file", file);
  for (const [name, value] of Object.entries(fields)) form.append(name, value);
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: token ? { Authorization: `Token ${token}` } : {},
    body: form,
  });
  if (res.status === 401) {
    useAuth.getState().expire();
    throw Object.assign(new Error("Your session expired — please sign in again."), { status: 401 });
  }
  const data = await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(data?.detail || "Upload failed."), { status: res.status });
  return data;
}
