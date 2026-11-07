/** A username the server accepts: 3 to 150 letters, digits, dots, dashes or underscores. */
export const isUsername = (value) => /^[A-Za-z0-9._-]{3,150}$/.test(value || "");
