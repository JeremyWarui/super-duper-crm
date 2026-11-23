/** Where a login starts: the console or its campaign. */
export function homeOf(user) {
  return user?.is_superuser ? "/console" : "/campaign";
}
