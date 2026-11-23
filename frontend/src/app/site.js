// Whether the installation is set up, read once from GET /api/site/.
import { useSite } from "@/api/hooks";

/** `loading` until the site settings arrive; `notSetUp` before first-run setup. */
export function useInstall() {
  const site = useSite();
  return { loading: site.isPending, notSetUp: site.error?.code === "not_set_up" };
}
