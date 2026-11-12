// src/api/client.js
// The one place that talks to the API: attaches the token, sends and reads JSON, files and
// downloads, turns a refusal into a readable message, and signs the user out on a 401.

import { useAuth } from "@/store/auth";
import { BASE } from "./base";

/** Signs the user out and throws when the server no longer accepts the token. */
function expireOn401(res) {
  if (res.status !== 401) return;
  useAuth.getState().expire();
  throw Object.assign(new Error("Your session expired — please sign in again."), { status: 401 });
}

/** Fetches `path` with the token unless `anonymous`; a 401 to a request that carried the token signs the user out and throws. */
async function send(path, init = {}, anonymous = false) {
  const token = anonymous ? null : useAuth.getState().token;
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(token ? { Authorization: `Token ${token}` } : {}), ...init.headers },
  });
  if (token) expireOn401(res);
  return res;
}

/**
 * The server's refusal as an Error carrying its `status` and `code`, so a screen can tell a closed
 * campaign from any other refusal. The message is `detail`, else the first field's first message.
 */
function refusal(res, data, fallback) {
  const first = data?.detail || (data && Object.values(data)[0]);
  const text = Array.isArray(first) ? first[0] : first;
  const message = typeof text === "string" && text ? text : fallback;
  return Object.assign(new Error(message), { status: res.status, code: data?.code });
}

// `anonymous` leaves the token off, for the public pages anyone can open.
export async function api(path, { method = "GET", body, anonymous = false, headers = {} } = {}) {
  const res = await send(path, {
    method,
    headers: { "Content-Type": "application/json", ...headers },
    body: body ? JSON.stringify(body) : undefined,
  }, anonymous);
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw refusal(res, data, "Request failed.");
  return data;
}

// Fetches a file with the token and hands it to the browser as a download.
export async function download(path, filename) {
  const res = await send(path);
  if (!res.ok) throw refusal(res, await res.json().catch(() => null), "Download failed.");
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
  const form = new FormData();
  form.append("file", file);
  for (const [name, value] of Object.entries(fields)) form.append(name, value);
  const res = await send(path, { method: "POST", body: form });
  const data = await res.json().catch(() => null);
  if (!res.ok) throw refusal(res, data, "Upload failed.");
  return data;
}
