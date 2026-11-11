// What kind of installation this is, read once from GET /api/site/.
import { useSite } from "@/api/hooks";

/** `type` is "party" or "aspirant", or null until the site settings load. */
export function useInstall() {
  const site = useSite();
  const type = site.data?.organisation_type ?? null;
  const notSetUp = site.error?.code === "not_set_up";
  return { type, party: type === "party", aspirant: type === "aspirant", loading: site.isPending, notSetUp };
}
