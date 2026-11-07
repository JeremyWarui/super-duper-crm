const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const NAIROBI_OFFSET_MS = 3 * 60 * 60 * 1000;

export function formatNumber(value) {
  return Number(value || 0).toLocaleString();
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
