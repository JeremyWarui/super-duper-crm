// How a text to supporters is built and billed.

// Must match backend/src/backend/services/texting.py FOOTER.
export const FOOTER = "\nReply STOP to opt out.";

/** The longest a text may be, footer included: six SMS parts. */
const TEXT_MAX = 918;

/** The longest message a sender may type: the rest is the footer. */
export const BODY_MAX = TEXT_MAX - FOOTER.length;

/** Parts each recipient is billed: one up to 160 characters, then parts of 153. */
export const partsOf = (text) => (!text ? 0 : text.length <= 160 ? 1 : Math.ceil(text.length / 153));

/** A text's delivery state as [label, badge tone]. */
export const DELIVERY_STATUS = { delivered: ["Delivered", "ok"], sent: ["Sent", "info"], failed: ["Failed", "bad"], practice: ["Practice", "stone"] };

// Telkom numbers get no delivery report, so their texts stay "sent" for good.
export const NO_REPORT = "no_report_expected";

/** A log row's status label and badge tone. */
export function deliveryOf(row) {
  if (row.status === "sent" && row.detail === NO_REPORT) return ["Sent (Telkom sends no delivery report)", "info"];
  return DELIVERY_STATUS[row.status] || [row.status, "stone"];
}

/** Ten seconds while any row still waits for its delivery report; otherwise no polling. */
export const pollWhileWaiting = (query) =>
  query.state.data?.some((r) => r.status === "sent" && r.detail !== NO_REPORT) ? 10_000 : false;

/** The whole text as sent, footer included, and whether it can go: some words, at most six SMS parts. */
export function composed(body) {
  const text = body.trim() + FOOTER;
  return { text, fits: body.trim().length > 0 && text.length <= TEXT_MAX };
}
