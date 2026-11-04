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
