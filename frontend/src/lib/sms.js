// How a text to supporters is built and billed.

// Must match backend/src/backend/services/texting.py FOOTER.
export const FOOTER = "\nReply STOP to opt out.";

/** Parts each recipient is billed: one up to 160 characters, then parts of 153. */
export const partsOf = (text) => (!text ? 0 : text.length <= 160 ? 1 : Math.ceil(text.length / 153));

/** A text's delivery state as [label, badge tone]. */
export const DELIVERY_STATUS = { delivered: ["Delivered", "ok"], sent: ["Waiting", "info"], failed: ["Failed", "bad"], practice: ["Practice", "stone"] };

/** The whole text as sent, footer included, and whether it can go: some words, at most six SMS parts. */
export function composed(body) {
  const text = body.trim() + FOOTER;
  return { text, fits: body.trim().length > 0 && text.length <= 918 };
}
