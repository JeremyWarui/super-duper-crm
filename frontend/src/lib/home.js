/** Where a login starts: the console, the party portal or its campaign. */
export function homeOf(user) {
  if (user?.is_superuser) return "/console";
  if (user?.role === null && user?.party_roles?.length) return "/party";
  return "/campaign";
}
