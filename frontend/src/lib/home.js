/** Where a login starts: the console, the party portal or its campaign. */
export function homeOf(user) {
  if (user?.is_superuser) return "/console";
  if (user?.role === null && user?.party_roles?.length) return "/party";
  return "/campaign";
}

/** Where sign-in sends a login: a member to its account, a login linked to a member to the chooser. */
export function landingOf(user) {
  if (user?.kind === "member") return "/account";
  if (user?.member_account) return "/signin/where";
  return homeOf(user);
}
