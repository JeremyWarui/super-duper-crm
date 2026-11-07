/** What happened to a new login's emailed invite, or a reset link: `sent` is "email" or "none". */
export const linkNote = (sent, username) =>
  sent === "email"
    ? `We emailed ${username} a link to choose their password.`
    : `${username} has no email, so no link could be sent. Ask the IT person to add one to their login, then send a reset link from the console.`;
