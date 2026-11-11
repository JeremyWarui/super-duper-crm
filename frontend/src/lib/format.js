const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const NAIROBI_OFFSET_MS = 3 * 60 * 60 * 1000;

/** A count with Kenyan thousands separators, as "12,500". */
export function formatNumber(value) {
  return Number(value || 0).toLocaleString("en-KE");
}

/** The calendar date in Nairobi (UTC+3) at `at`, as "2026-11-03". */
export const nairobiDate = (at = new Date()) =>
  new Date(at.getTime() + NAIROBI_OFFSET_MS).toISOString().slice(0, 10);

/** A "2026-11-03" date, or a timestamp read in Nairobi time, as "3 Nov 2026". */
export function formatDate(value) {
  if (!value) return "—";
  const iso = value.length === 10 ? value : nairobiDate(new Date(value));
  const [year, month, day] = iso.split("-").map(Number);
  return `${day} ${MONTHS[month - 1]} ${year}`;
}

/** A timestamp in Nairobi time, as "3 Nov 2026, 14:05". */
export function formatDateTime(value) {
  if (!value) return "—";
  const at = new Date(new Date(value).getTime() + NAIROBI_OFFSET_MS).toISOString();
  return `${formatDate(at.slice(0, 10))}, ${at.slice(11, 16)}`;
}

/** An amount in shillings, as "KES 1,500". */
export const formatKES = (value) => `KES ${Number(value || 0).toLocaleString("en-KE")}`;

/** A count with the word that fits it: "1 recipient", "1,200 recipients". */
export const plural = (n, one, many = `${one}s`) => `${formatNumber(n)} ${n === 1 ? one : many}`;

/** Up to two capitals from the words of a name that start with a letter: "Amina (Mama) Kariuki" is "AK". */
export const initials = (name) =>
  (name || "").split(/\s+/).filter((w) => /^\p{L}/u.test(w)).slice(0, 2).map((w) => w[0]).join("").toUpperCase();

/** A date or timestamp read in Nairobi time, in the parts `opts` names: "3 November 2026" by default. */
export const formatDay = (value, opts = { day: "numeric", month: "long", year: "numeric" }) =>
  value ? new Date(value.length === 10 ? `${value}T00:00:00+03:00` : value).toLocaleDateString("en-GB", { ...opts, timeZone: "Africa/Nairobi" }) : "";

/** A row's ward, constituency and county names, whichever it has, as "Karen / Langata / Nairobi City". */
export const placeOf = (row, sep = " / ") =>
  [row.ward?.name, row.constituency?.name, row.county?.name].filter(Boolean).join(sep);

/** The non-blank lines of `text`, trimmed. */
export const linesOf = (text) => (text || "").split("\n").map((l) => l.trim()).filter(Boolean);

/** The items of a numbered list, each without its "1." or "1)". */
export const listItems = (text) => linesOf(text).map((l) => l.replace(/^\d+[.)]\s*/, "")).filter(Boolean);

/** What to call a login: its full name, else its username. */
export const displayName = (user) => user?.full_name || user?.username || "";

/** The first word of a name. */
export const firstName = (name) => (name || "").trim().split(/\s+/)[0];

/** A candidate's area, then their county unless it is the same place, joined by `sep`. */
export const whereOf = (c, sep) => [c.area, c.county].filter((v, i, all) => v && all.indexOf(v) === i).join(sep);

/** How to reach the office: its email or phone, or both joined by "or"; "" when it lists neither. */
export const contactOf = (site) => [site?.contact_email, site?.contact_phone].filter(Boolean).join(" or ");

/** `path` as a full link on this site, for copying, QR codes and texts. */
export const linkTo = (path) => `${window.location.origin}${path}`;
