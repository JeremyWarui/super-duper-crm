/** An address shaped like name@example.com; every login signs in with one. */
export const isEmail = (value) => /^[^@\s]+@[^@\s]+\.[^@\s]+$/.test((value || "").trim());
