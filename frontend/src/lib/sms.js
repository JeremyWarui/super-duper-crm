// How a text to supporters is built and billed.

// Must match backend/src/backend/services/texting.py FOOTER.
export const FOOTER = "\nReply STOP to opt out.";

/** Parts each recipient is billed: one up to 160 characters, then parts of 153. */
export const partsOf = (text) => (!text ? 0 : text.length <= 160 ? 1 : Math.ceil(text.length / 153));
